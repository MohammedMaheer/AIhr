import csv
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import main
from test_durable_search import queue_db
from vps_local import storage_shim


@pytest.fixture
def job_app_flow(queue_db, tmp_path, monkeypatch):
    db = queue_db
    with db.get_cursor() as (cursor, _):
        cursor.execute('''ALTER TABLE tenant_companies ADD COLUMN is_active BOOLEAN DEFAULT TRUE,
            ADD COLUMN gcs_bucket_name TEXT;
            ALTER TABLE users ADD COLUMN full_name TEXT;
            INSERT INTO tenant_companies(id,company_code,company_name,max_searches,is_active,gcs_bucket_name)
                VALUES (1,'jobs-one','Fictional Hiring Co',1000,TRUE,'jobs-one-bucket'),
                       (2,'jobs-two','Other Company',1000,TRUE,'jobs-two-bucket');
            INSERT INTO users(id,email,user_type,is_active,full_name)
                VALUES (7,'manager@example.invalid','tenant_admin',TRUE,'Fictional Manager'),
                       (8,'other@example.invalid','tenant_admin',TRUE,'Other Manager');
            INSERT INTO user_companies(user_id,company_id) VALUES (7,1),(8,2);
            CREATE TABLE resume_uploads(id SERIAL PRIMARY KEY,file_name TEXT,file_path TEXT,file_size INTEGER,
                mime_type TEXT,uploaded_by_user_id INTEGER,company_id INTEGER,upload_timestamp TIMESTAMPTZ DEFAULT NOW());
            CREATE TABLE resume_embeddings(id SERIAL PRIMARY KEY,storage_bucket TEXT,folder TEXT,filename TEXT,
                company_id INTEGER);
            CREATE TABLE audit_logs(user_id INTEGER,company_id INTEGER,action TEXT,entity_type TEXT,
                entity_id INTEGER,old_values JSONB,new_values JSONB);''')
        migration = Path(__file__).resolve().parents[1] / 'deploy/vps/migrations/20261111_job_applications.sql'
        cursor.execute(migration.read_text(encoding='utf-8'))
    monkeypatch.setattr(db, 'get_company_by_id', lambda company_id: {
        'id': company_id, 'company_code': 'jobs-one' if company_id == 1 else 'jobs-two',
        'company_name': 'Fictional Hiring Co' if company_id == 1 else 'Other Company',
        'gcs_bucket_name': 'jobs-one-bucket' if company_id == 1 else 'jobs-two-bucket',
        'datastore_id': 'fixture-store'})
    monkeypatch.setattr(main, 'get_db_manager', lambda: db)
    monkeypatch.setattr(main.limiter, 'enabled', False)
    monkeypatch.setattr(main, '_check_resume_upload_limit', AsyncMock(return_value=None))
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setenv('SMARTHR_STORAGE_ROOT', str(tmp_path))
    monkeypatch.setattr(storage_shim, 'STORAGE_ROOT', tmp_path)
    monkeypatch.setattr(main, '_get_storage_client', storage_shim.Client)
    actor = {'user': {'id': 7, 'email': 'manager@example.invalid', 'user_type': 'tenant_admin',
                      'company': {'company_id': 1, 'company_code': 'jobs-one'}}}

    async def fake_upload(db, **kwargs):
        blob = storage_shim.Client().bucket(kwargs['bucket_name']).blob(kwargs['blob_name'])
        blob.upload_from_string(kwargs['content'], content_type=kwargs['content_type'])
        with db.get_cursor() as (cursor, _):
            cursor.execute('''INSERT INTO resume_uploads(file_name,file_path,file_size,mime_type,uploaded_by_user_id,company_id)
                VALUES (%s,%s,%s,%s,%s,%s)''', (kwargs['filename'],kwargs['blob_name'],len(kwargs['content']),
                kwargs['content_type'],kwargs['user_id'],kwargs['company_id']))
        return True

    upload = AsyncMock(side_effect=fake_upload)
    monkeypatch.setattr(main, '_run_resume_upload', upload)
    main.app.dependency_overrides[main.require_auth] = lambda: actor['user']
    client = TestClient(main.app, base_url='https://testserver')
    client.headers['X-CSRF-Token'] = 'synthetic-token'
    try:
        yield SimpleNamespace(db=db, client=client, actor=actor, upload=upload, storage=tmp_path)
    finally:
        main.app.dependency_overrides.pop(main.require_auth, None)


def page_payload(**changes):
    return {'title': 'Platform Engineer', 'description': 'Build and maintain services for the product team.',
            'location': 'Abu Dhabi', 'employment_type': 'Full-time',
            'custom_questions': ['What is your notice period?'], **changes}


def publish(flow):
    response = flow.client.post('/api/job-application-pages', json={**page_payload(), 'status':'published'})
    assert response.status_code == 200, response.text
    return response.json()['page']


def submit(flow, url, **changes):
    data = {'candidate_name':'Fictional Candidate','email':'candidate@example.invalid','phone':'+971 50 000 0000',
            'location':'Abu Dhabi','years_experience':'5.5','linkedin_url':'https://www.linkedin.com/in/fictional',
            'answers':json.dumps({'0':'Thirty days'}),'consent':'true', **changes}
    return flow.client.post(url, data=data, files={'file':('candidate.pdf',b'%PDF-1.7\nfixture CV', 'application/pdf')})


def test_published_page_submission_indexes_cv_and_tenant_manager_reviews(job_app_flow):
    flow = job_app_flow
    page = publish(flow)
    token = page['public_url'].rsplit('/', 1)[1]
    public = flow.client.get('/api/public/application-pages/' + token)
    assert public.status_code == 200
    assert set(public.json()['page']) == {'title','description','location','employment_type','custom_questions','company_name'}
    response = submit(flow, '/api/public/application-pages/' + token + '/applications')
    assert response.status_code == 200, response.text
    assert response.json()['message'] == 'Your application has been received.'
    flow.upload.assert_awaited_once()
    arguments = flow.upload.await_args.kwargs
    assert arguments['company_id'] == 1 and arguments['bucket_name'] == 'jobs-one-bucket'
    assert arguments['blob_name'].startswith(f"Applications/{page['id']}/")
    assert arguments['content'] == b'%PDF-1.7\nfixture CV'

    listed = flow.client.get(f"/api/job-application-pages/{page['id']}/applications")
    assert listed.status_code == 200, listed.text
    result = listed.json()['applications'][0]
    assert result['candidate_name'] == 'Fictional Candidate' and result['normalized_email'] == 'candidate@example.invalid'
    assert result['answers'] == {'0':'Thirty days'} and result['vector_indexed'] is True
    assert result['resume_upload_id'] and result['file_name'] == 'candidate.pdf'
    blob_key = Path(flow.storage / 'jobs-one-bucket' / arguments['blob_name'])
    assert blob_key.is_file()

    changed = flow.client.patch(f"/api/job-applications/{result['id']}/status",
        json={'status':'shortlisted','version':result['version']})
    assert changed.status_code == 200 and changed.json()['application']['status'] == 'shortlisted'
    csv_response = flow.client.get(f"/api/job-application-pages/{page['id']}/applications.csv")
    assert csv_response.status_code == 200 and 'text/csv' in csv_response.headers['content-type']
    records = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert records[0]['Email'] == 'candidate@example.invalid' and records[0]['Status'] == 'shortlisted'


def test_page_edit_publish_pause_close_and_audit_use_optimistic_versions(job_app_flow):
    flow = job_app_flow
    page = flow.client.post('/api/job-application-pages', json=page_payload()).json()['page']
    assert page['status'] == 'draft' and page['public_url'] is None
    stale = flow.client.put(f"/api/job-application-pages/{page['id']}", json={**page_payload(), 'version':99})
    assert stale.status_code == 409
    edit = flow.client.put(f"/api/job-application-pages/{page['id']}", json={**page_payload(title='Senior Platform Engineer'), 'version':page['version']})
    assert edit.status_code == 200 and edit.json()['page']['title'] == 'Senior Platform Engineer'
    current = edit.json()['page']
    published = flow.client.patch(f"/api/job-application-pages/{page['id']}/status", json={'status':'published','version':current['version']})
    assert published.status_code == 200 and published.json()['page']['public_url']
    token = published.json()['page']['public_url'].rsplit('/',1)[1]
    paused = flow.client.patch(f"/api/job-application-pages/{page['id']}/status", json={'status':'paused','version':published.json()['page']['version']})
    assert paused.status_code == 200 and flow.client.get('/api/public/application-pages/' + token).status_code == 404
    closed = flow.client.patch(f"/api/job-application-pages/{page['id']}/status", json={'status':'closed','version':paused.json()['page']['version']})
    assert closed.status_code == 200
    deleted = flow.client.request('DELETE', f"/api/job-application-pages/{page['id']}",
        json={'version':closed.json()['page']['version']})
    assert deleted.status_code == 200
    assert flow.client.get('/api/job-application-pages').json()['pages'] == []
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT action FROM audit_logs ORDER BY action')
        actions = [row['action'] for row in cursor.fetchall()]
    assert actions.count('CREATE_JOB_APPLICATION_PAGE') == 1
    assert actions.count('EDIT_JOB_APPLICATION_PAGE') == 1
    assert actions.count('CHANGE_JOB_APPLICATION_PAGE_STATUS') == 3
    assert actions.count('DELETE_EMPTY_JOB_APPLICATION_PAGE') == 1


@pytest.mark.parametrize('changes,expected', [
    ({'consent':'false'}, 422),
    ({'email':'invalid'}, 422),
    ({'years_experience':'999'}, 422),
    ({'linkedin_url':'https://example.invalid/in/person'}, 422),
    ({'answers':'not-json'}, 422),
])
def test_public_form_rejects_bad_candidate_data_before_upload(job_app_flow, changes, expected):
    flow = job_app_flow
    token = publish(flow)['public_url'].rsplit('/',1)[1]
    response = submit(flow, '/api/public/application-pages/' + token + '/applications', **changes)
    assert response.status_code == expected
    flow.upload.assert_not_awaited()


def test_public_form_rejects_invalid_cv_duplicate_email_and_unpublished_page(job_app_flow):
    flow = job_app_flow
    page = publish(flow); token = page['public_url'].rsplit('/',1)[1]
    invalid = flow.client.post('/api/public/application-pages/' + token + '/applications',
        data={'candidate_name':'Fictional Person','email':'fictional@example.invalid','consent':'true'},
        files={'file':('fake.pdf',b'not a PDF','application/pdf')})
    assert invalid.status_code == 422
    assert flow.upload.await_count == 0
    assert submit(flow, '/api/public/application-pages/' + token + '/applications').status_code == 200
    duplicate = submit(flow, '/api/public/application-pages/' + token + '/applications')
    assert duplicate.status_code == 200
    assert flow.upload.await_count == 1
    draft = flow.client.post('/api/job-application-pages', json=page_payload()).json()['page']
    assert flow.client.get('/apply/' + 'x' * 42).status_code == 200
    missing = flow.client.get('/api/public/application-pages/' + 'x' * 42)
    assert missing.status_code == 404
    assert flow.client.get(f"/api/job-application-pages/{draft['id']}/applications").status_code == 200


def test_failed_cv_ingestion_removes_upload_and_processing_reservation(job_app_flow):
    flow = job_app_flow
    token = publish(flow)['public_url'].rsplit('/', 1)[1]
    persist_upload = flow.upload.side_effect

    async def fail_after_persist(**kwargs):
        await persist_upload(**kwargs)
        raise OSError('synthetic storage acknowledgement failure')

    flow.upload.side_effect = fail_after_persist
    response = submit(flow, '/api/public/application-pages/' + token + '/applications')
    assert response.status_code == 503
    blob_name = flow.upload.await_args.kwargs['blob_name']
    assert not Path(flow.storage / 'jobs-one-bucket' / blob_name).exists()
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT COUNT(*) AS count FROM job_applications WHERE status = %s', ('processing',))
        assert cursor.fetchone()['count'] == 0
        cursor.execute('SELECT COUNT(*) AS count FROM resume_uploads WHERE file_path = %s', (blob_name,))
        assert cursor.fetchone()['count'] == 0


def test_job_pages_applicants_and_status_changes_are_company_scoped(job_app_flow):
    flow = job_app_flow
    page = publish(flow)
    response = submit(flow, '/api/public/application-pages/' + page['public_url'].rsplit('/',1)[1] + '/applications')
    assert response.status_code == 200
    paused = flow.client.patch(f"/api/job-application-pages/{page['id']}/status",
        json={'status':'paused','version':page['version']})
    assert paused.status_code == 200
    cannot_delete = flow.client.request('DELETE', f"/api/job-application-pages/{page['id']}",
        json={'version':paused.json()['page']['version']})
    assert cannot_delete.status_code == 409
    flow.actor['user'] = {'id':8,'email':'other@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':2,'company_code':'jobs-two'}}
    assert flow.client.get('/api/job-application-pages').json()['pages'] == []
    assert flow.client.get(f"/api/job-application-pages/{page['id']}/applications").status_code == 404
    assert flow.client.get(f"/api/job-application-pages/{page['id']}/applications.csv").status_code == 404
    assert flow.client.patch('/api/job-applications/1/status', json={'status':'hired','version':1}).status_code == 404
    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':1,'company_code':'jobs-one'}}
    assert flow.client.get('/api/job-application-pages').json()['pages'][0]['applicant_count'] == 1


def test_application_creator_requires_company_context_and_authenticated_manager(job_app_flow):
    flow = job_app_flow
    flow.actor['user'] = {'id':1,'email':'root@example.invalid','user_type':'super_admin','company':None}
    assert flow.client.get('/api/job-application-pages').status_code == 403
    flow.client.cookies.clear()
    main.app.dependency_overrides.pop(main.require_auth, None)
    try:
        assert flow.client.get('/api/job-application-pages').status_code == 401
    finally:
        main.app.dependency_overrides[main.require_auth] = lambda: flow.actor['user']
