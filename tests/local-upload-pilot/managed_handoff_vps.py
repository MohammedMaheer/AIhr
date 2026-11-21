"""Enrollment and signed-result trust experiment, in the isolated stage only."""
import asyncio
import base64
import binascii
import hashlib
import json
import math
import secrets
import struct
import threading
from dataclasses import dataclass
from time import process_time, time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from psycopg2.errors import UniqueViolation

from handoff_vps import Job, clients, db, dispatch, finish, index, jobs, main, measured, serve
from managed_pool_vps import WorkerPool

revision = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
server = Ed25519PrivateKey.generate()
allowed_company = clients['owner'][1]
pool = WorkerPool(db)


def tenant_admin(actor, company):
    email = f'{actor}@desktop-fixtures.invalid'
    password = secrets.token_urlsafe(24)
    user = db.create_user(email, password, actor, 'tenant_admin', company)
    client = TestClient(main.app, base_url='https://testserver')
    assert client.post('/api/login', data={'email': email, 'password': password}).status_code == 200
    client.headers.update({'x-csrf-token': client.cookies['csrf_token'], 'origin': 'https://testserver'})
    return client, company, user, ''


clients['admin'] = tenant_admin('admin', allowed_company)
clients['second-admin'] = tenant_admin('second-admin', clients['second'][1])


@main.app.post('/__qa/pool/enroll')
def enroll_managed(payload: dict, user=Depends(main.require_tenant_admin)):
    if payload.get('model') != revision:
        raise HTTPException(status_code=422, detail='Model revision not allowed')
    try:
        encoded = decode(payload.get('publicKey'))
        key = serialization.load_der_public_key(encoded)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError('Invalid worker identity')
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail='Worker identity not supported') from None
    try:
        worker = pool.enroll(main._get_company_id(user), encoded)
    except UniqueViolation:
        raise HTTPException(status_code=409, detail='Worker already registered') from None
    return {'state': 'enrolled-stage-only', 'workerId': worker}


@main.app.post('/__qa/pool/{worker_id}/revoke')
def revoke_managed(worker_id: str, user=Depends(main.require_tenant_admin)):
    if not pool.revoke(main._get_company_id(user), worker_id):
        raise HTTPException(status_code=404, detail='Worker unavailable')
    return {'state': 'revoked'}


def b64(value):
    return base64.b64encode(value).decode('ascii')


def decode(value):
    return base64.b64decode(value, validate=True)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def signed(key, message, signature):
    try:
        key.verify(decode(signature), message)
        return True
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        return False


@dataclass
class Grant:
    worker: str
    challenge: str
    deadline: float
    binding: str = ''
    entries: tuple = ()
    file_states: tuple = ()


grants = {}


def key_for(worker):
    encoded = pool.public_key(worker)
    return serialization.load_der_public_key(encoded) if encoded else None


def heartbeat(command):
    worker, sequence, ready = command['workerId'], command['sequence'], command['ready']
    key = key_for(worker)
    if not key or type(sequence) is not int or not 0 < sequence < 2**53 or type(ready) is not bool or not signed(
        key, f'presence:{sequence}:{int(ready)}'.encode('ascii'), command.get('signature')
    ):
        return {'state': 'denied'}
    return {'state': 'heartbeat' if pool.heartbeat(worker, sequence, ready) else 'denied'}


async def pressure_sample(saturate):
    if not saturate:
        return main._resume_upload_slots.locked()
    release = threading.Event()
    # Hold the same upload slots as real index work, without stressing the host.
    tasks = [asyncio.create_task(main._run_resume_worker(release.wait, 2)) for _ in range(2)]
    try:
        async with asyncio.timeout(1):
            while not main._resume_upload_slots.locked():
                await asyncio.sleep(0.001)
        return len(main._resume_upload_tasks) == 2
    finally:
        release.set()
        await asyncio.gather(*tasks)


def offer(job_id, saturate):
    job = jobs[job_id]
    if job.finished or job.company != allowed_company:
        return {'state': 'vps'}
    if not asyncio.run(pressure_sample(saturate)):
        return {'state': 'vps'}
    reservation = pool.reserve(job.company, job_id)
    if reservation is None:
        return {'state': 'vps'}
    worker, deadline = reservation
    challenge = secrets.token_hex(32)
    grants[job_id] = Grant(worker, challenge, deadline)
    return {'state': 'offered', 'workerId': worker, 'challenge': challenge,
            'auth': b64(server.sign(b'offer:' + challenge.encode('ascii')))}


def file_state(path):
    stat = path.stat()
    return stat.st_ino, stat.st_mtime_ns, stat.st_size


def claim(job_id, signature):
    job, grant = jobs[job_id], grants.get(job_id)
    key = key_for(grant.worker) if grant else None
    if (key is None or job.company != allowed_company or job.finished or grant.binding or
            grant.deadline <= time() or not signed(key, b'claim:' + grant.challenge.encode('ascii'), signature)):
        return {'state': 'denied'}
    grant.entries = tuple(index._prepare_document_embedding(doc) for doc in job.documents)
    if not all(entry is not None and entry.searchable and entry.company_id == allowed_company for entry in grant.entries):
        return {'state': 'vps'}
    grant.file_states = tuple(file_state(entry.path) for entry in grant.entries)
    texts = [entry.text for entry in grant.entries]
    claims = {'jobId': job_id, 'nonce': grant.challenge, 'workerId': grant.worker, 'tenant': 'owner', 'model': revision,
              'expiresAt': int(grant.deadline * 1000), 'documents': [sha(text.encode('utf-8')) for text in texts]}
    manifest = json.dumps(claims, sort_keys=True, separators=(',', ':')).encode('ascii')
    grant.binding = sha(manifest)
    return {'state': 'leased', 'manifest': b64(manifest), 'binding': grant.binding, 'texts': texts,
            'auth': b64(server.sign(b'lease:' + manifest))}


def accept(job_id, message):
    job, grant = jobs[job_id], grants.get(job_id)
    key = key_for(grant.worker) if grant else None
    if (key is None or job.company != allowed_company or job.finished or not grant.binding or
            grant.deadline <= time() or message.get('binding') != grant.binding):
        return {'state': 'denied'}
    packed = message.get('packed')
    size = len(grant.entries) * 384 * 4
    if not isinstance(packed, str) or len(packed) != 4 * ((size + 2) // 3) or not packed.isascii() or not signed(
        key, f'result:{grant.binding}:{packed}'.encode('ascii'), message.get('signature')
    ):
        return {'state': 'denied'}
    try:
        data = decode(packed)
    except ValueError:
        return {'state': 'denied'}
    if len(data) != size:
        return {'state': 'denied'}
    vectors = list(struct.iter_unpack('<384f', data))
    if any(not all(map(math.isfinite, row)) or not 0.99 <= math.fsum(x*x for x in row) <= 1.01 for row in vectors):
        return {'state': 'denied'}
    try:
        unchanged = tuple(file_state(entry.path) for entry in grant.entries) == grant.file_states
    except OSError:
        unchanged = False
    if not unchanged:
        return {'state': 'vps'}

    def write():
        return [index._write_document_embedding(entry, vector) for entry, vector in zip(grant.entries, vectors, strict=True)]

    results, timing = measured(write)
    assert all(result.indexed for result in results)
    for entry in grant.entries:
        main._record_resume_upload_metadata(db, job.bucket, f'{entry.folder}/{entry.filename}', job.company)
    job.finished = True
    pool.finish(job_id)
    grants.pop(job_id)
    return {'state': 'indexed-by-managed-worker', 'indexed': len(results), **timing}


def compare(before_id, after_id):
    before, after = jobs[before_id], jobs[after_id]
    assert before.company == after.company
    with db.get_cursor() as (cursor, _):
        cursor.execute('''SELECT min(1-(a.embedding <=> b.embedding)) AS cosine,
              bool_and(a.search_tags=b.search_tags AND a.candidate_skills=b.candidate_skills
                AND a.source_uploaded_at IS NOT NULL AND b.source_uploaded_at IS NOT NULL) AS same,
              count(*) AS compared FROM resume_embeddings a JOIN resume_embeddings b
                ON a.company_id=b.company_id AND a.storage_bucket=b.storage_bucket AND a.extracted_text=b.extracted_text
              WHERE a.company_id=%s AND a.folder=%s AND b.folder=%s''', (before.company, before.folder, after.folder))
        return dict(cursor.fetchone())


def rebuild_from_storage():
    # Simulate the coordinator losing RAM while the stored originals and leases survive.
    jobs.clear()
    grants.clear()
    for row in pool.jobs():
        docs = [index.Document(struct_data={'company_id': row['company_id']},
                content=index.Document.Content(uri=uri, mime_type='application/pdf')) for uri in row['uris']]
        jobs[row['id']] = Job(row['owner_id'], row['company_id'], row['bucket'], row['folder'], docs,
                             row['state'], finished=row['finished'])


def handle(command):
    start = process_time()
    op = command['op']
    if op == 'coordinator':
        result = {'publicKey': b64(server.public_key().public_bytes(serialization.Encoding.DER,
                                                                  serialization.PublicFormat.SubjectPublicKeyInfo))}
    elif op == 'enroll':
        reply = clients[command.get('actor', 'admin')][0].post('/__qa/pool/enroll', json={
            'publicKey': command['publicKey'], 'model': command['model']})
        result = {'status': reply.status_code, **reply.json()}
    elif op == 'heartbeat':
        result = heartbeat(command)
    elif op == 'revoke':
        reply = clients[command.get('actor', 'admin')][0].post(f"/__qa/pool/{command['workerId']}/revoke")
        result = {'status': reply.status_code, **reply.json()}
    elif op == 'offer':
        result = offer(command['jobId'], command['saturate'])
    elif op == 'prove':
        result = claim(command['jobId'], command.get('signature'))
    elif op == 'accept':
        result = accept(command['jobId'], command['result'])
    elif op == 'compare':
        result = compare(command['before'], command['after'])
    elif op == 'reset-coordinator-memory':
        rebuild_from_storage()
        result = {'state': 'reloaded', 'savedJobs': len(jobs)}
    elif op == 'remaining-lease':
        result = {'remainingMs': pool.remaining(command['jobId'])}
    elif op == 'recover':
        job_id = command['jobId']
        if pool.remaining(job_id) > 0:
            result = {'state': 'lease-active'}
        else:
            result = finish(job_id)
            pool.finish(job_id)
    else:
        result = dispatch(command)
        if op == 'upload':
            pool.save_job(result['jobId'], jobs[result['jobId']])
    return {**result, 'vpsCpuMs': round((process_time() - start) * 1000, 3)}


serve(handle)
