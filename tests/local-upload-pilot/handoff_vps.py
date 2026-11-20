"""Stage an authenticated handoff against real storage and pgvector, never production."""
import base64
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
from time import process_time, time
from urllib.parse import urlsplit
from unittest.mock import patch

from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient

assert os.environ['DB_NAME'] == 'desktop_offload_qa'
assert os.environ['SMARTHR_STORAGE_ROOT'] == '/tmp/smarthr-offload-fixtures'
assert os.environ['HF_HUB_OFFLINE'] == '1'
assert os.environ['SMARTHR_QUERY_EMBED_CACHE_MAX'] == '0'

import main
from vps_local import discovery_shim as index

app = main.app
auth = main.require_auth
db = main.get_db_manager()
assert db.db_config['database'] == 'desktop_offload_qa'
index.initialize_search_schema()
index._embed_query('Warm synthetic desktop handoff benchmark')
main.limiter.enabled = False


def accounts():
    clients = {}
    for name in ('owner', 'second'):
        bucket = f'desktop-fixtures-{name}'
        with db.get_cursor() as (cur, _):
            cur.execute('''INSERT INTO tenant_companies(company_name,company_code,gcs_bucket_name,datastore_id)
                           VALUES (%s,%s,%s,%s) RETURNING id''', (name, name, bucket, f'fixture-{name}'))
            company = cur.fetchone()['id']
        mail = f'{name}@desktop-fixtures.invalid'
        password = secrets.token_urlsafe(24)
        user_id = db.create_user(mail, password, name, 'tenant_user', company)
        client = TestClient(app, base_url='https://testserver')
        assert client.post('/api/login', data={'email': mail, 'password': password}).status_code == 200
        client.headers.update({'x-csrf-token': client.cookies['csrf_token'], 'origin': 'https://testserver'})
        clients[name] = (client, company, user_id, bucket)
    return clients


clients = accounts()


@dataclass
class Job:
    owner: int
    company: int
    bucket: str
    folder: str
    documents: list
    state: str
    lease: str = ''
    deadline: float = 0
    vectors: list = field(default_factory=list)
    finished: bool = False


jobs = {}
embedder = index.vertexai_shim.language_models.TextEmbeddingModel
encode = embedder.get_embeddings


def owned(job_id, user):
    job = jobs.get(job_id)
    if job is None or job.owner != user['id'] or job.company != main._get_company_id(user):
        raise HTTPException(status_code=404, detail='Job unavailable')
    return job


@app.post('/__qa/desktop/{job_id}/claim')
def claim(job_id: str, permission: dict, user=Depends(auth)):
    job = owned(job_id, user)
    if job.finished or job.lease or job.state != 'busy' or permission.get('optedIn') is not True or permission.get('warm') is not True:
        return {'state': job.state, 'saved': True, 'canAssist': False}
    docs = [index._prepare_document_embedding(doc) for doc in job.documents]
    assert all(doc is not None and doc.searchable for doc in docs)
    job.lease = secrets.token_urlsafe(20)
    job.deadline = time() + 12.0
    return {'state': 'busy', 'saved': True, 'canAssist': True, 'jobId': job_id, 'lease': job.lease,
            'expiresAt': int(job.deadline * 1000), 'texts': [entry.text for entry in docs]}


@app.post('/__qa/desktop/{job_id}/submit')
def submit(job_id: str, candidate: dict, user=Depends(auth)):
    job = owned(job_id, user)
    if job.finished or job.vectors or not job.lease or candidate.get('lease') != job.lease or job.deadline <= time():
        raise HTTPException(status_code=409, detail='Lease unavailable')
    vectors = candidate.get('vectors')
    if not isinstance(vectors, list) or len(vectors) != len(job.documents) or any(
        not isinstance(v, list) or len(v) != 384 or any(type(x) not in (int, float) or not -1 <= x <= 1 for x in v)
        or not 0.99 <= math.fsum(x*x for x in v) <= 1.01 for v in vectors
    ):
        raise HTTPException(status_code=422, detail='Invalid embedding result')
    job.vectors = vectors
    return {'state': 'waiting-for-verification'}


def measured(function):
    calls = []
    cpu_ms = 0.0

    def timed(model, texts, **kwargs):
        nonlocal cpu_ms
        calls.append(len(texts) if isinstance(texts, list) else 1)
        start = process_time()
        try:
            return encode(model, texts, **kwargs)
        finally:
            cpu_ms += (process_time() - start) * 1000

    with patch.object(embedder, 'get_embeddings', timed):
        result = function()
    return result, {'inferenceBatches': calls, 'embeddingCpuMs': round(cpu_ms, 2)}


def upload(command):
    state = command['state']
    assert state in {'reference', 'healthy', 'busy'}
    client, company, owner, bucket = clients['owner']
    folder = 'Synthetic/Offload/' + secrets.token_hex(5)
    data = [(f'{i}.pdf', base64.b64decode(item, validate=True), 'application/pdf')
            for i, item in enumerate(command['pdfs'])]
    assert 1 <= len(data) <= 50

    def save_one(database, *, bucket_name, company_id, user_id, company_code, **upload):
        main._persist_resume_upload(database, bucket_name=bucket_name, company_id=company_id, user_id=user_id, **upload)
        return False

    def save_group(database, bucket_name, company_id, company_code, user_id, uploads):
        return [save_one(database, bucket_name=bucket_name, company_id=company_id, company_code=company_code,
                         user_id=user_id, **item) for item in uploads]

    def request():
        return client.post('/api/upload-files', data={'folder_path': folder}, files=[('files', item) for item in data])

    if state == 'reference':
        result, measure = measured(request)
    else:
        with patch.object(main, '_store_resume_upload', save_one), patch.object(main, '_store_resume_upload_batch', save_group):
            result, measure = measured(request)
    assert result.status_code == 200, result.status_code
    files = result.json()['results']
    assert len(files) == len(data) and all(row['success'] is True for row in files)
    assert all(row['vector_indexed'] is (state == 'reference') for row in files)
    docs = []
    for row, (_, raw, _) in zip(files, data, strict=True):
        uri = row['gcs_path']
        key = urlsplit(uri).path.lstrip('/')
        assert (Path(os.environ['SMARTHR_STORAGE_ROOT']) / bucket / key).read_bytes() == raw
        docs.append(index.Document(struct_data={'company_id': company}, content=index.Document.Content(
            uri=uri, mime_type='application/pdf')))
    job_id = secrets.token_hex(16)
    jobs[job_id] = Job(owner, company, bucket, folder, docs, state, finished=state == 'reference')
    return {'jobId': job_id, 'folder': folder, 'saved': len(docs), **measure}


def finish(job_id):
    job = jobs[job_id]
    if job.finished:
        return {'state': 'already-indexed', 'inferenceBatches': []}
    # Use the same production path, even with a well-formed desktop result. No
    # client vector is permitted to become the authoritative version.
    batch_size = index.MAX_RESUME_EMBED_BATCH
    docs = job.documents
    def canonical_index():
        return [item for offset in range(0, len(docs), batch_size)
                for item in index.index_resume_batch(docs[offset:offset+batch_size])]
    outcomes, measure = measured(canonical_index)
    assert all(result.indexed for result in outcomes)
    for doc in docs:
        uri = doc.content.uri
        main._record_resume_upload_metadata(db, job.bucket, urlsplit(uri).path.lstrip('/'), job.company)
    matches = None
    if job.vectors:
        similarities = []
        with db.get_cursor() as (cur, _):
            for doc, vec in zip(docs, job.vectors, strict=True):
                cur.execute('''SELECT 1-(embedding <=> %s::vector) AS similarity FROM resume_embeddings
                    WHERE storage_bucket=%s AND folder=%s AND company_id=%s AND filename=%s''',
                    (index._vec_lit(vec), job.bucket, job.folder, job.company, Path(urlsplit(doc.content.uri).path).name))
                similarities.append(cur.fetchone()['similarity'])
        matches = min(similarities) >= 0.9999
    job.finished = True
    return {'state': 'indexed', 'desktopAgreed': matches, 'indexed': len(outcomes), **measure}


def search(command):
    job = jobs[command['jobId']]
    with db.get_cursor() as (cur, _):
        cur.execute('''SELECT count(*) AS n FROM resume_embeddings WHERE company_id=%s AND folder=%s
                       AND storage_bucket=%s AND embedding IS NOT NULL''', (job.company, job.folder, job.bucket))
        count = cur.fetchone()['n']
        cur.execute('SELECT CURRENT_DATE AS today')
        today = cur.fetchone()['today'].isoformat()
        cur.execute('SELECT count(*) AS n FROM llm_call_log')
        assert cur.fetchone()['n'] == 0
    ranked = []
    for query in command['queries']:
        filters = {'tags': [query['tag']], 'date_basis': 'uploaded', 'date_from': today, 'date_to': today} if query.get('tag') else None
        rows = index._vector_search(query['text'], query['limit'], f'company_id: ANY("{job.company}")',
                                    [{'bucket': job.bucket, 'path': job.folder}], filters)
        assert all(row['folder'] == job.folder and row['storage_bucket'] == job.bucket for row in rows)
        ranked.append([[re.match(r'Synthetic CV ([\w-]+)', row['text']).group(1),
                        row.get('criteria_profile_status'), row['score']] for row in rows])
    return {'count': count, 'ranks': ranked}


def dispatch(command):
    op = command['op']
    if op == 'upload':
        return upload(command)
    if op == 'http':
        path = command['path']
        assert re.fullmatch(r'/__qa/desktop/[a-f0-9]{32}/(claim|submit)', path)
        response = clients[command['actor']][0].post(path, json=command['body'])
        return {'status': response.status_code, 'json': response.json()}
    if op == 'search':
        return search(command)
    if op == 'expire':
        jobs[command['jobId']].deadline = 0
        return {'state': 'expired'}
    if op == 'finish':
        return finish(command['jobId'])
    raise ValueError('Unknown stage command')


def output(value):
    sys.stdout.write('HANDOFF:' + json.dumps(value, allow_nan=False) + '\n')
    sys.stdout.flush()


output({'ready': True})
for line in sys.stdin:
    request = json.loads(line)
    if request['op'] == 'close':
        break
    output(dispatch(request))
