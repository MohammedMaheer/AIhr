"""Real private files/SQL and HTTP ingestion-to-results tests; no paid providers."""
import asyncio
import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from docx import Document
from fastapi.testclient import TestClient

import main
from services import calendar_service, graph_mail
from services.resume_filters import record_metadata
from services.task_queue import SearchWorker
from test_durable_search import assessment, queue_db
from vps_local import discovery_shim as index, storage_shim as storage

BUCKET = 'e2e-fixture-bucket'
FOLDER = 'Campaign/November 2026'
FOLDERS = [{'bucket': BUCKET, 'path': FOLDER}]
MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def cv(name, skills='UI designer using Figma and user interface design'):
    document = Document()
    document.add_heading('Fictional candidate ' + name, 0)
    document.add_paragraph(skills)
    document.add_paragraph('Experience: 5 years. Location: Dubai. English. QA fixture only.')
    target = io.BytesIO()
    document.save(target)
    return target.getvalue()


@pytest.fixture
def flow(queue_db, tmp_path, monkeypatch):
    db = queue_db
    with db.get_cursor() as (cur, _):
        cur.execute('''ALTER TABLE search_results ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
            ALTER TABLE tenant_companies ADD COLUMN max_resumes INTEGER,
            ADD COLUMN max_users INTEGER, ADD COLUMN subscription_plan TEXT,
            ADD COLUMN is_active BOOLEAN DEFAULT TRUE, ADD COLUMN gcs_bucket_name TEXT;
            INSERT INTO tenant_companies(id,company_code,company_name,max_searches,max_resumes,max_users,gcs_bucket_name)
                VALUES (1,'e2e-one','Fictional One',1000,1000,10,'e2e-fixture-bucket'),
                       (2,'e2e-two','Fictional Two',1000,1000,10,'e2e-fixture-bucket');
            INSERT INTO users VALUES (7,'one@example.invalid','tenant_user',true),
                                     (8,'two@example.invalid','tenant_user',true);
            INSERT INTO user_companies VALUES (7,1),(8,2);
            CREATE TABLE resume_uploads(id SERIAL PRIMARY KEY,file_name TEXT,file_path TEXT,
                file_size INTEGER,mime_type TEXT,uploaded_by_user_id INTEGER,company_id INTEGER,
                upload_timestamp TIMESTAMP DEFAULT NOW());
            CREATE TABLE resume_embeddings(id SERIAL PRIMARY KEY,filename TEXT,folder TEXT,
                storage_bucket TEXT,company_id INTEGER,file_size INTEGER,content_type TEXT,
                extracted_text TEXT,text_length INTEGER,embedding vector(3),candidate_years NUMERIC,
                candidate_location TEXT,candidate_languages TEXT[],candidate_skills TEXT[],profile_source TEXT,
                profile_updated_at TIMESTAMP,embedded_at TIMESTAMP,embed_model TEXT,extraction_error TEXT,
                search_tags TEXT[] DEFAULT '{}',source_uploaded_at TIMESTAMP,source_received_at TIMESTAMPTZ);
            CREATE UNIQUE INDEX e2e_identity ON resume_embeddings
                (storage_bucket,folder,filename,(COALESCE(company_id,0)));''')
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setenv('SMARTHR_STORAGE_ROOT', str(tmp_path))
    monkeypatch.setenv('USE_CLOUD_TASKS', 'false')
    monkeypatch.setattr(storage, 'STORAGE_ROOT', tmp_path)
    monkeypatch.setattr(index, '_get_pool', lambda: db.pool)
    monkeypatch.setattr(index, '_advanced_schema_ensured', True)
    monkeypatch.setattr(index, '_embed_query', lambda text: [1, 0, 0])
    monkeypatch.setattr(main, 'get_db_manager', lambda: db)
    monkeypatch.setattr(main, '_get_storage_client', storage.Client)
    monkeypatch.setattr(main, 'get_company_resources', lambda user=None: (BUCKET, 'e2e-store'))
    monkeypatch.setattr(main, 'get_search_client', index.SearchServiceClient)
    monkeypatch.setattr(main.limiter, 'enabled', False)
    monkeypatch.setattr(main, '_resume_upload_slots', asyncio.Semaphore(2))
    monkeypatch.setattr(main, 'config', {'upload': {'allowed_extensions': ['.pdf', '.doc', '.docx']}})
    monkeypatch.setattr(db, 'get_oauth_token', lambda *_: {'access_token': 'fictional'})
    monkeypatch.setattr(calendar_service, '_get_valid_token', lambda *_: ('fictional', 'mail@example.invalid'))
    actor = {'user': db.get_hr_task_user(7, 1)}
    main.app.dependency_overrides[main.require_auth] = lambda: actor['user']
    client = TestClient(main.app, base_url='https://testserver')
    client.cookies.set('csrf_token', 'fictional-csrf')
    client.headers['X-CSRF-Token'] = 'fictional-csrf'
    main._search_cache_clear()

    def bulk(folder, files):
        response = client.post('/api/upload-files', data={'folder_path': folder},
            files=[('files', (name, content, MIME)) for name, content in files])
        assert response.status_code == 200, response.text
        assert all(row['success'] and row['vector_indexed'] for row in response.json()['results']), response.text
        return response.json()

    def mail(endpoint='/api/upload-files', status=200):
        payloads = {
            'before': ('2026-04-30T23:59:59Z', 'within.docx'),
            'after': ('2026-05-01T00:00:00Z', 'outside.docx'),
            'unknown': (None, 'unknown-date.docx'),
        }
        session = MagicMock()
        session.__enter__.return_value = session
        def get(url, **kwargs):
            if url.endswith('/me/messages'):
                assert kwargs['params']['$filter'] == graph_mail.ATTACHMENT_MESSAGE_FILTER
                data = {'value': [{'id': key, 'subject': 'Fictional CV application',
                    'receivedDateTime': date, 'body': {'content': 'Please find my CV'}}
                    for key, (date, _) in payloads.items()]}
                return SimpleNamespace(status_code=status, headers={}, json=lambda: data, close=lambda: None)
            key = url.split('/messages/')[1].split('/')[0]
            filename = payloads[key][1]
            data = {'value': [{'id': key, 'name': filename, 'contentType': MIME,
                'contentBytes': base64.b64encode(cv('mail-' + key)).decode()},
                {'id': 'inline', 'name': 'inline.docx', 'isInline': True},
                {'id': 'picture', 'name': 'photo.png'}]}
            return SimpleNamespace(status_code=200, json=lambda: data, close=lambda: None)
        session.get.side_effect = get
        monkeypatch.setattr(graph_mail.requests, 'Session', lambda: session)
        data = {'folder_path': FOLDER, 'email_provider': 'outlook', 'email_address': 'mail@example.invalid',
                'email_limit': '3', 'limit': '3'}
        if endpoint == '/api/upload-files': data['scrape_email'] = 'true'
        return client.post(endpoint, data=data)

    try:
        yield SimpleNamespace(db=db, client=client, actor=actor, bulk=bulk, mail=mail, root=tmp_path)
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)
        main._search_cache_clear()


def seed(flow):
    bulk = flow.bulk(FOLDER, [('same-name.docx', cv('bulk-good')), ('wrong-tag.docx', cv('finance', 'Accountant with accounts payable experience'))])
    flow.bulk(FOLDER + '/sub', [('child.docx', cv('child', 'Web designer using WordPress and Webflow'))])
    flow.bulk(FOLDER + '-old', [('sibling.docx', cv('sibling'))])
    flow.bulk('Other folder', [('same-name.docx', cv('different-original'))])
    flow.actor['user'] = flow.db.get_hr_task_user(8, 2)
    flow.bulk(FOLDER, [('other-tenant.docx', cv('other-tenant'))])
    flow.actor['user'] = flow.db.get_hr_task_user(7, 1)
    response = flow.mail()
    assert response.status_code == 200, response.text
    assert response.json()['email_stats']['successful_uploads'] == 3
    with flow.db.get_cursor() as (cur, _):
        cur.execute("UPDATE resume_uploads SET upload_timestamp='2026-04-15' WHERE file_name='same-name.docx'")
        cur.execute('''SELECT e.id,e.filename,e.folder,e.company_id,e.search_tags,e.source_received_at,
            u.file_name AS original_filename FROM resume_embeddings e JOIN resume_uploads u
            ON u.company_id IS NOT DISTINCT FROM e.company_id
            AND u.file_path=concat_ws('/',NULLIF(e.folder,''),e.filename)''')
        rows = [dict(row) for row in cur.fetchall()]
    key = bulk['results'][0]['gcs_path'].removeprefix('gs://' + BUCKET + '/')
    record_metadata(flow.db, BUCKET, key, 1)
    return rows


def search(flow, folders, filters):
    response = flow.client.post('/api/search-vector', data={'query': 'candidate profiles', 'result_count': '25',
        'folders': json.dumps(folders), 'filters': json.dumps(filters)})
    assert response.status_code == 200, response.text
    return {int(row['id']) for row in response.json()['results']}


@pytest.mark.parametrize('advanced', [True, False])
def test_real_bulk_graph_ingestion_and_scoped_retrieval(flow, monkeypatch, advanced):
    monkeypatch.setattr(index, 'ADVANCED_SEARCH_ENABLED', advanced)
    rows = seed(flow)
    assert len(list(flow.root.rglob('*.docx'))) == 9
    good = next(row for row in rows if row['folder'] == FOLDER and row['original_filename'] == 'same-name.docx')
    emails = {row['original_filename']: row for row in rows if row['filename'].startswith('graph_')}
    assert good['search_tags'] == ['UI design']
    assert emails['within.docx']['source_received_at'].isoformat() == '2026-04-30T23:59:59+00:00'
    assert emails['unknown-date.docx']['source_received_at'] is None
    april = {'date_basis': 'received', 'date_from': '2026-04-01', 'date_to': '2026-04-30', 'tags': ['UI design']}
    assert search(flow, FOLDERS, april) == {emails['within.docx']['id']}
    uploaded = {**april, 'date_basis': 'uploaded'}
    assert search(flow, FOLDERS, uploaded) == {good['id']}
    assert search(flow, FOLDERS, {**april, 'tags': ['Finance and accounting']}) == set()
    allowed = {row['id'] for row in rows if row['company_id'] == 1 and row['folder'] in (FOLDER, FOLDER + '/sub')
               and set(row['search_tags']) & {'UI design', 'Web design'}}
    assert search(flow, FOLDERS, {'tags': ['UI design', 'Web design']}) == allowed
    sibling = [{'bucket': BUCKET, 'path': FOLDER + '-old'}]
    assert search(flow, sibling, {'tags': ['UI design']}) == {row['id'] for row in rows if row['folder'] == FOLDER + '-old'}
    assert search(flow, FOLDERS + sibling, {'tags': ['UI design', 'Web design']}) == allowed | search(flow, sibling, {'tags': ['UI design']})
    assert search(flow, [{'bucket': BUCKET, 'path': 'Missing'}], {}) == set()
    assert search(flow, FOLDERS, april) == {emails['within.docx']['id']}, 'A prior broad/different-scope cache entry must not leak'
    response = flow.client.post('/api/search-vector', data={'query': 'candidate profiles', 'folders': '[]'})
    assert response.status_code == 422


@pytest.mark.parametrize('endpoint', ['/api/upload-files', '/api/scrape-email-attachments'])
def test_real_graph_adapter_to_import_and_no_partial_success_on_auth_failure(flow, endpoint):
    response = flow.mail(endpoint)
    assert response.status_code == 200, response.text
    assert response.json()['email_stats']['total_attachments'] == 3
    with flow.db.get_cursor() as (cur, _):
        cur.execute('SELECT count(*) AS count FROM resume_embeddings WHERE folder=%s AND source_received_at IS NOT NULL', (FOLDER,))
        assert cur.fetchone()['count'] == 2
    before = len(list(flow.root.rglob('*.docx')))
    failure = flow.mail(endpoint, status=403)
    assert failure.status_code != 200
    assert len(list(flow.root.rglob('*.docx'))) == before


@pytest.mark.parametrize('fallback', [True, False])
def test_durable_worker_scores_and_persists_only_the_selected_cohort(flow, monkeypatch, fallback):
    rows = seed(flow)
    expected = next(row for row in rows if row['filename'].endswith('_within.docx'))
    filters = {'tags': ['UI design'], 'date_basis': 'received', 'date_from': '2026-04-01', 'date_to': '2026-04-30'}
    seen, requests = [], []
    client = index.SearchServiceClient()
    def retrieve(request):
        requests.append(request)
        if request.query == 'fictional-empty-optimization': return SimpleNamespace(results=[])
        return client.search(request)
    monkeypatch.setattr(main, 'get_search_client', lambda: SimpleNamespace(search=retrieve))
    monkeypatch.setattr(main, '_prepare_search_input', lambda kind, *args: {'all_keywords': ['Figma']} if kind == 'keywords'
        else {'optimized_query': 'fictional-empty-optimization' if fallback else 'candidate profiles'})
    monkeypatch.setattr(flow.db, 'get_cached_resume_analysis', lambda *args, **kwargs: None)
    monkeypatch.setattr(flow.db, 'save_cached_resume_analysis', lambda *args, **kwargs: None)
    async def analyze(text, *args, **kwargs):
        assert 'Fictional candidate mail-before' in text
        seen.append(kwargs['file_path'])
        value = assessment()
        value['hr_scorecard']['candidate_overview'].update(position_applied_for='Designer', experience_years=5)
        return value
    monkeypatch.setattr(main, 'analyze_resume_with_hr_scorecard', analyze)
    monkeypatch.setattr(main, 'using_deepseek', lambda: True)
    response = flow.client.post('/api/hr-scorecard-search', data={'query': 'candidate profiles', 'result_count': '10',
        'folders': json.dumps(FOLDERS), 'filters': json.dumps(filters)})
    assert response.status_code == 200, response.text
    task_id = response.json()['task_id']
    job = flow.db.claim_next_hr_task()
    assert job['task_id'] == task_id
    asyncio.run(SearchWorker(lambda: flow.db, main.run_hr_scorecard_task).process(flow.db, job))
    status = flow.db.get_task_status(task_id)
    assert status['status'] == 'completed', status
    assert seen == [FOLDER + '/' + expected['filename']]
    assert len(requests) == (2 if fallback else 1)
    assert all(request.folder_filters == FOLDERS and request.resume_filters == filters for request in requests)
    response = flow.client.get('/api/search-results/' + str(status['search_id']))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['folder_filters'] == FOLDERS and data['resume_filters'] == filters
    assert len(data['results']) == 1
    assert data['results'][0]['file_path'] == seen[0]


def test_same_named_bulk_cvs_have_distinct_searchable_objects_and_dates(flow):
    first = flow.bulk(FOLDER, [('candidate.docx', cv('first-candidate'))])
    second = flow.bulk(FOLDER, [('candidate.docx', cv('second-candidate'))])
    expected = {batch['results'][0]['gcs_path'] for batch in (first, second)}
    assert len(expected) == 2
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT id,filename,folder,storage_bucket,source_uploaded_at FROM resume_embeddings')
        rows = [dict(row) for row in cursor.fetchall()]
        cursor.execute('SELECT file_name FROM resume_uploads')
        assert [row['file_name'] for row in cursor.fetchall()] == ['candidate.docx', 'candidate.docx']
    assert len(rows) == 2, 'Display-name collisions must not overwrite a different CV vector'
    assert all(row['source_uploaded_at'] is not None for row in rows)
    locations = {index._row_to_result(row).document.content.uri for row in rows}
    assert locations == expected
    for uri in locations:
        assert (flow.root / BUCKET / uri.removeprefix('gs://' + BUCKET + '/')).is_file()
