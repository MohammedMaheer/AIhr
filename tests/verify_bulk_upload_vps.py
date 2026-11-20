"""Synthetic release gate: run inside a disposable VPS app/pgvector network."""
import io
import json
import os
from pathlib import Path
import re
import secrets
from statistics import median
from time import perf_counter
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient


assert os.getenv('DB_NAME') == 'bulk_cv_qa'
assert os.getenv('SMARTHR_STORAGE_ROOT') == '/tmp/smarthr-bulk-storage'
assert os.getenv('HF_HUB_OFFLINE') == '1'
assert os.getenv('SMARTHR_QUERY_EMBED_CACHE_MAX') == '0'

import main
from vps_local import discovery_shim as search


def make_pdf(lines):
    stream = ('BT /F1 10 Tf 14 TL 40 735 Td\n' + '\n'.join(f'({line}) Tj T*' for line in lines) + '\nET').encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Count 1 /Kids [3 0 R] >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream']
    out, offsets = b'%PDF-1.4\n', []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % i + obj + b'\nendobj\n'
    return (out + b'xref\n0 6\n0000000000 65535 f \n' + b''.join(b'%010d 00000 n \n' % x for x in offsets)
            + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % len(out))


def documents():
    verbs = ['Designed', 'Maintained', 'Automated', 'Validated', 'Deployed', 'Integrated', 'Rebuilt', 'Tested']
    for i in range(34):
        if i < 16:
            title = 'Full Stack Software Developer'
            city = 'Dubai' if i != 15 else 'Sharjah'
            years = (i % 3) + 2 if i != 14 else 9
            skills = 'React, Node.js, PostgreSQL, JavaScript, Redis'
            words = ['booking systems', 'payment pipelines', 'accessible storefronts', 'inventory APIs', 'subscriber dashboards']
        elif i < 25:
            title, city, years = 'Data Analyst', 'Abu Dhabi', 5
            skills, words = 'Python, SQL, Tableau', ['reporting workflows', 'statistics', 'demand forecasts']
        else:
            title, city, years = 'Graphic Designer', 'Dubai', 4
            skills, words = 'Figma, Photoshop', ['design systems', 'user interface design', 'brand guidelines']
        lines = [f'Synthetic candidate {i:02d}', title, f'Location: {city}, UAE',
                 f'Total experience: {years} years', f'Skills: {skills}', 'Professional experience']
        for j in range(4 + i % 18):
            lines.append(f'{verbs[(i + 3*j) % len(verbs)]} {words[(i + j) % len(words)]} '
                         f'for fictional department {i+1} and added release documentation and operational support.')
        if i % 9 == 0:
            doc = Document()
            for text in lines[:6]:
                doc.add_paragraph(text)
            for text in lines[6:]:
                doc.add_table(rows=1, cols=1).cell(0, 0).text = text
            data = io.BytesIO()
            doc.save(data)
            yield f'candidate-{i:02d}.docx', data.getvalue(), 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        else:
            yield f'candidate-{i:02d}.pdf', make_pdf(lines), 'application/pdf'


db = main.get_db_manager()
assert db.db_config['database'] == 'bulk_cv_qa'
with db.get_cursor() as (cur, _):
    cur.execute("INSERT INTO tenant_companies(company_name,company_code,gcs_bucket_name,datastore_id) "
                "VALUES ('Synthetic Workspace','bulk-qa','bulk-qa-fixtures','bulk-qa-store') RETURNING id")
    company = cur.fetchone()['id']
    cur.execute("SELECT count(*) AS count FROM resume_uploads")
    assert cur.fetchone()['count'] == 0

app = main.app
client = TestClient(app, base_url='https://testserver')
email, password = 'bulk-cv-qa@example.invalid', secrets.token_urlsafe(30)
db.create_user(email, password, 'Synthetic upload verifier', 'tenant_user', company)
assert client.post('/api/upload-files').status_code == 401
login = client.post('/api/login', data={'email': email, 'password': password})
assert login.status_code == 200, login.status_code
headers = {'x-csrf-token': client.cookies['csrf_token'], 'origin': 'https://testserver'}
search.initialize_search_schema()
search._embed_query('Local release test warm-up')
inputs = list(documents())
expected_files = {name: content for name, content, _ in inputs}
embed_class = search.vertexai_shim.language_models.TextEmbeddingModel
embed = embed_class.get_embeddings
calls = []


def upload(folder, size, files, *, fail=False):
    os.environ['SMARTHR_BULK_EMBED_BATCH_SIZE'] = str(size)
    assert main._manual_upload_batch_size() == size
    calls.clear()

    def counted(model, texts, **kwargs):
        count = 1 if isinstance(texts, str) else len(texts)
        calls.append(count)
        if fail and count > 1:
            raise RuntimeError('Synthetic batch failure')
        return embed(model, texts, **kwargs)

    with patch.object(embed_class, 'get_embeddings', counted):
        start = perf_counter()
        response = client.post('/api/upload-files', headers=headers, data={'folder_path': folder, 'batch_info': '1/1'},
                               files=[('files', item) for item in files])
        duration = perf_counter() - start
    assert response.status_code == 200, (response.status_code, response.text[:300])
    data = response.json()
    assert [row['filename'] for row in data['results']] == [item[0] for item in files]
    assert data['batch_stats']['total'] == len(files)
    if not fail:
        assert data['batch_stats']['successful'] == len(files)
        assert all(row['vector_indexed'] for row in data['results'])
        assert calls == ([1] * len(files) if size == 1 else [size] * (len(files) // size) + [len(files) % size])
    for row in data['results']:
        if row['success'] and row['filename'] in expected_files:
            key = row['gcs_path'].removeprefix('gs://')
            assert (Path(os.environ['SMARTHR_STORAGE_ROOT']) / key).read_bytes() == expected_files[row['filename']]
    return duration, data


def compare_index(before, after):
    with db.get_cursor() as (cur, _):
        cur.execute('''SELECT max(1 - (a.embedding <=> b.embedding)) AS max_cos,
                    min(1 - (a.embedding <=> b.embedding)) AS min_cos, count(*) AS count,
                    bool_and(a.extracted_text = b.extracted_text AND a.candidate_skills = b.candidate_skills
                        AND a.search_tags = b.search_tags AND a.source_uploaded_at IS NOT NULL
                        AND b.source_uploaded_at IS NOT NULL) AS same
                FROM resume_embeddings a JOIN resume_embeddings b ON a.extracted_text=b.extracted_text
                    AND a.company_id=b.company_id AND a.storage_bucket=b.storage_bucket
                WHERE a.folder=%s AND b.folder=%s AND a.company_id=%s''', (before, after, company))
        row = cur.fetchone()
        assert row['count'] == len(inputs) and row['same'] and row['min_cos'] >= 0.999999, row
        return row['min_cos']


def get_ranked(folder, query, count, filters=None):
    rows = search._vector_search(query, count, f'company_id: ANY("{company}")',
                               [{'bucket': 'bulk-qa-fixtures', 'path': folder}], filters)
    assert all(row['folder'] == folder and row['storage_bucket'] == 'bulk-qa-fixtures' for row in rows)
    return [(re.search(r'Synthetic candidate (\d+)', row['text']).group(1),
             row.get('criteria_profile_status'), row['score']) for row in rows]


with db.get_cursor() as (cur, _):
    cur.execute('SELECT CURRENT_DATE AS today')
    today = cur.fetchone()['today'].isoformat()

queries = [
    ('Full Stack Developer based in Dubai with 2-4 years of experience. Required skills: React, Node.js.', 10, None),
    ('Data Analyst based in Abu Dhabi with 4-6 years of experience. Required skills: Python, SQL.', 8, None),
    ('Graphic Designer based in Dubai with 3-5 years of experience. Required skills: Figma.', 7,
     {'tags': ['Graphic design'], 'date_basis': 'uploaded', 'date_from': today, 'date_to': today}),
    ('forecasting and demand dashboards', 10, None),
]
timings = {1: [], 8: []}
cosines = []
for attempt in range(3):
    folders = {size: f'Synthetic/Run-{attempt}/{size}' for size in timings}
    for size in ((1, 8) if attempt % 2 == 0 else (8, 1)):
        duration, _ = upload(folders[size], size, inputs)
        timings[size].append(duration)
    cosines.append(compare_index(folders[1], folders[8]))
    for i, query in enumerate(queries):
        before, after = get_ranked(folders[1], *query), get_ranked(folders[8], *query)
        assert before and [row[:2] for row in before] == [row[:2] for row in after], (i, before, after)
        assert max(abs(a[2] - b[2]) for a, b in zip(before, after, strict=True)) <= 1e-5
        if i == 0:
            assert len(after) == 10 and all(item[1] == 'exact' for item in after), after

negative = [('blank.pdf', make_pdf([]), 'application/pdf'), ('broken.pdf', b'not a pdf', 'application/pdf')]
_, failed = upload('Synthetic/Forced-Fallback', 8, [*inputs[:3], *negative], fail=True)
assert calls == [3, 1, 1, 1], calls
assert failed['batch_stats'] == {'successful': 4, 'failed': 1, 'total': 5}
assert [(item['success'], item.get('vector_indexed')) for item in failed['results']] == [
    (True, True), (True, True), (True, True), (True, False), (False, None)]
with db.get_cursor() as (cur, _):
    cur.execute("SELECT count(*) AS count FROM resume_embeddings WHERE folder=%s AND embedding IS NOT NULL",
                ('Synthetic/Forced-Fallback',))
    assert cur.fetchone()['count'] == 3
    cur.execute('SELECT count(*) AS count FROM llm_call_log')
    assert cur.fetchone()['count'] == 0

averages = {size: round(median(values), 3) for size, values in timings.items()}
print('BULK_GATE:' + json.dumps({'files_per_upload': len(inputs), 'timed_runs': 6,
    'verified_searchable_uploads': len(inputs) * 6 + 3, 'ordered_search_comparisons': len(queries) * 3,
    'min_same_document_cosine': min(cosines), 'vps_batch_calls': [8, 8, 8, 8, 2],
    'synthetic_fallback': True, 'folder_tag_and_date_scope': True, 'paid_ai_calls': 0,
    'sequential_median_seconds': averages[1], 'batch_median_seconds': averages[8],
    'batch_faster': averages[8] < averages[1]}))
