import csv
import io
import json
from datetime import date, timedelta
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
                entity_id INTEGER,old_values JSONB,new_values JSONB,ip_address TEXT,user_agent TEXT);
            CREATE TABLE scheduled_interviews(id SERIAL PRIMARY KEY,candidate_name TEXT NOT NULL,
                candidate_email TEXT,interview_type TEXT NOT NULL,interview_date DATE NOT NULL,
                interview_time TIME,duration_minutes INTEGER DEFAULT 60,location TEXT,interviewer TEXT,
                notes TEXT,status TEXT DEFAULT 'scheduled',created_by TEXT,company_id INTEGER,
                meeting_provider TEXT,meeting_join_url TEXT,meeting_event_id TEXT,search_result_id INTEGER,
                position TEXT,time_zone TEXT,calendar_account_id TEXT);
            CREATE TABLE interview_emails_sent(id SERIAL PRIMARY KEY,company_id INTEGER,sent_by_user_id INTEGER,
                recipient_email TEXT NOT NULL,candidate_name TEXT,kind TEXT,subject TEXT,body TEXT,provider TEXT,
                status TEXT,error_message TEXT,search_result_id INTEGER,interview_id INTEGER,created_at TIMESTAMP DEFAULT NOW());''')
        migration = Path(__file__).resolve().parents[1] / 'deploy/vps/migrations/20261111_job_applications.sql'
        cursor.execute(migration.read_text(encoding='utf-8'))
        workflow_migration = Path(__file__).resolve().parents[1] / 'deploy/vps/migrations/20261111_job_application_workflow.sql'
        cursor.execute(workflow_migration.read_text(encoding='utf-8'))
    monkeypatch.setattr(db, 'get_company_by_id', lambda company_id: ({
        'id': company_id, 'company_code': 'jobs-one' if company_id == 1 else 'jobs-two',
        'company_name': 'Fictional Hiring Co' if company_id == 1 else 'Other Company',
        'gcs_bucket_name': 'jobs-one-bucket' if company_id == 1 else 'jobs-two-bucket',
        'datastore_id': 'fixture-store'} if company_id in (1, 2) else None))
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


@pytest.mark.parametrize('questions', [
    ['What is your notice period?', ' what   is your NOTICE period? '],
    ['x' * 181],
    ['A valid question?', ''],
    ['A valid question?', 7],
    ['Question'] * 7,
])
def test_job_page_rejects_invalid_custom_questions(job_app_flow, questions):
    response = job_app_flow.client.post('/api/job-application-pages',
        json=page_payload(custom_questions=questions))
    assert response.status_code == 422


def test_ai_application_questions_are_company_scoped_and_review_ready(job_app_flow, monkeypatch):
    flow = job_app_flow
    related = flow.client.post('/api/job-application-pages', json=page_payload(
        title='Cloud Platform Engineer', description='Build and operate secure cloud services.'))
    assert related.status_code == 200
    flow.actor['user'] = {'id':8,'email':'other@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':2,'company_code':'jobs-two'}}
    isolated = flow.client.post('/api/job-application-pages', json=page_payload(
        title='Confidential Other Tenant Role', description='Other company data must stay private.'))
    assert isolated.status_code == 200
    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':1,'company_code':'jobs-one'}}
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text=json.dumps({'questions':[
                'Describe a production incident you resolved.',
                'Which infrastructure tools have you used in production?',
            ]}))

    monkeypatch.setattr(main, 'gemini_client', lambda: SimpleNamespace(models=FakeModels()))
    response = flow.client.post('/api/job-application-pages/generate-questions', json={
        'title':'Senior Platform Engineer',
        'description':'Design and run reliable infrastructure for our product team.',
        'location':'Remote', 'employment_type':'Full-time',
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['company_name'] == 'Fictional Hiring Co'
    assert len(data['questions']) == 2
    assert calls and calls[0]['config'].max_output_tokens == 500
    prompt = calls[0]['contents']
    assert 'Fictional Hiring Co' in prompt and 'Cloud Platform Engineer' in prompt
    assert 'Confidential Other Tenant Role' not in prompt
    assert 'untrusted reference data' in calls[0]['config'].system_instruction
    assert 'candidate@example.invalid' not in prompt
    assert calls[0]['config'].response_mime_type == 'application/json'

    flow.actor['user'] = {'id':8,'email':'other@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':2,'company_code':'jobs-two'}}
    forbidden = flow.client.post('/api/job-application-pages/generate-questions', json={
        'company_id':1, 'title':'Other role', 'description':'A detailed role description for testing.'})
    assert forbidden.status_code == 403
    assert len(calls) == 1


def test_ai_application_question_output_is_rejected_when_invalid(job_app_flow, monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text=json.dumps({'questions':['What is your age?']}))

    monkeypatch.setattr(main, 'gemini_client', lambda: SimpleNamespace(models=FakeModels()))
    response = job_app_flow.client.post('/api/job-application-pages/generate-questions', json={
        'title':'Platform Engineer', 'description':'Build reliable services for the product team.'})
    assert response.status_code == 502


def test_ai_application_question_provider_failure_is_distinct_from_bad_output(job_app_flow, monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            raise TimeoutError('synthetic provider timeout')

    monkeypatch.setattr(main, 'gemini_client', lambda: SimpleNamespace(models=FakeModels()))
    response = job_app_flow.client.post('/api/job-application-pages/generate-questions', json={
        'title':'Platform Engineer', 'description':'Build reliable services for the product team.'})
    assert response.status_code == 503


def test_ai_application_question_allows_technical_race_condition_language(job_app_flow, monkeypatch):
    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text=json.dumps({'questions':[
                'How do you detect and resolve race conditions in concurrent services?'
            ]}))

    monkeypatch.setattr(main, 'gemini_client', lambda: SimpleNamespace(models=FakeModels()))
    response = job_app_flow.client.post('/api/job-application-pages/generate-questions', json={
        'title':'Platform Engineer', 'description':'Build reliable services for the product team.'})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize('answer', [['not text'], 'x' * 1001])
def test_application_answer_rejects_non_text_or_oversized_values(job_app_flow, answer):
    page = publish(job_app_flow)
    token = page['public_url'].rsplit('/', 1)[1]
    response = submit(job_app_flow, '/api/public/application-pages/' + token + '/applications',
                      answers=json.dumps({'0':answer}))
    assert response.status_code == 422
    job_app_flow.upload.assert_not_awaited()


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


def test_applicant_email_preview_is_canonical_and_auditable(job_app_flow):
    flow = job_app_flow
    page = publish(flow)
    submitted = submit(flow, '/api/public/application-pages/' + page['public_url'].rsplit('/',1)[1] + '/applications')
    assert submitted.status_code == 200, submitted.text
    applicant = flow.client.get(f"/api/job-application-pages/{page['id']}/applications").json()['applications'][0]
    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'super_admin','company':None}
    response = flow.client.post('/api/preview-candidate-email', json={
        'job_application_id': applicant['id'], 'company_id':1, 'candidate_name':'Spoofed Name',
        'candidate_email':'attacker@example.invalid', 'position':'Wrong Role',
        'message_subject':'Application update', 'message_body':'A reviewed message.'})
    assert response.status_code == 200, response.text
    assert response.json()['recipient'] == 'candidate@example.invalid'
    assert 'attacker@example.invalid' not in response.text
    message_id = flow.db.log_email_sent(company_id=1, sent_by_user_id=7,
        recipient_email='candidate@example.invalid', candidate_name='Fictional Candidate',
        kind='custom', subject='Application update', body='Reviewed', provider='smtp',
        job_application_id=applicant['id'])
    assert message_id
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT job_application_id FROM interview_emails_sent WHERE id=%s', (message_id,))
        assert cursor.fetchone()['job_application_id'] == applicant['id']


def test_applicant_interview_is_tenant_checked_and_linked_to_application(job_app_flow):
    flow = job_app_flow
    page = publish(flow)
    submitted = submit(flow, '/api/public/application-pages/' + page['public_url'].rsplit('/',1)[1] + '/applications')
    assert submitted.status_code == 200, submitted.text
    applicant = flow.client.get(f"/api/job-application-pages/{page['id']}/applications").json()['applications'][0]
    payload = {'job_application_id':applicant['id'],'candidate_name':'Spoofed Name',
        'candidate_email':'spoofed@example.invalid','position':'Wrong Role','company':'Fictional Hiring Co',
        'company_id':1,
        'interview_type':'video','interview_date':(date.today()+timedelta(days=30)).isoformat(),
        'interview_time':'10:00','time_zone':'Asia/Kolkata','duration':30,'meeting_provider':'none',
        'send_invite_email':False,'interviewer':'Fictional Manager','location':'Video call'}
    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'super_admin','company':None}
    response = flow.client.post('/api/schedule-interview', json=payload)
    assert response.status_code == 200, response.text
    interview_id = response.json()['interview_id']
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('''SELECT candidate_name,candidate_email,position,job_application_id
            FROM scheduled_interviews WHERE id=%s''', (interview_id,))
        interview = cursor.fetchone()
    assert interview['candidate_name'] == 'Fictional Candidate'
    assert interview['candidate_email'] == 'candidate@example.invalid'
    assert interview['position'] == 'Platform Engineer' and interview['job_application_id'] == applicant['id']
    listed = flow.client.get(f"/api/job-application-pages/{page['id']}/applications?company_id=1").json()['applications'][0]
    assert listed['interview_id'] == interview_id and listed['interview_status'] == 'scheduled'

    flow.actor['user'] = {'id':8,'email':'other@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':2,'company_code':'jobs-two'}}
    rejected = flow.client.post('/api/schedule-interview', json=payload)
    assert rejected.status_code == 403
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT COUNT(*) AS count FROM scheduled_interviews')
        assert cursor.fetchone()['count'] == 1


def test_super_admin_can_select_company_without_weakening_tenant_scope(job_app_flow):
    flow = job_app_flow
    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'super_admin','company':None}
    response = flow.client.get('/api/job-application-pages?company_id=2')
    assert response.status_code == 200 and response.json()['pages'] == []
    response = flow.client.post('/api/job-application-pages', json={
        **page_payload(title='Other Company Role'), 'company_id':2})
    assert response.status_code == 200, response.text
    page_id = response.json()['page']['id']
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('SELECT company_id FROM job_application_pages WHERE id=%s', (page_id,))
        assert cursor.fetchone()['company_id'] == 2
    assert flow.client.get('/api/job-application-pages?company_id=999').status_code == 404
    assert flow.client.get('/api/job-application-pages?company_id=0').status_code == 403

    flow.actor['user'] = {'id':7,'email':'manager@example.invalid','user_type':'tenant_admin',
                          'company':{'company_id':1,'company_code':'jobs-one'}}
    assert flow.client.get('/api/job-application-pages?company_id=2').status_code == 403


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
