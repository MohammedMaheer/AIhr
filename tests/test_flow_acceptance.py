"""Cross-flow HTTP acceptance; external delivery/AI are stubbed, SQL is isolated."""
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from docx import Document
from fastapi.testclient import TestClient

import main
from database import DatabaseManager
from test_integration_workflows import api
from test_durable_search import queue_db


@pytest.fixture
def flow_api(api, monkeypatch):
    client, db = api
    monkeypatch.setattr(main.limiter, 'enabled', False)
    db.verify_session.return_value = {'id': 7, 'email': 'fixture@example.invalid',
        'full_name': 'Fixture Recruiter', 'user_type': 'super_admin', 'company': None}
    return client, db


@pytest.mark.parametrize('path', ['/api/me', '/api/users', '/api/companies', '/api/system-stats',
    '/api/company-stats', '/api/company-resource-usage', '/api/dashboard-stats',
    '/api/upcoming-events', '/api/search-history', '/api/email-templates', '/api/integrations/status',
    '/api/config', '/api/gcs-status', '/api/vector-status', '/api/candidate-state?ids=1'])
def test_anonymous_read_flows_require_login(path):
    client = TestClient(main.app)
    assert client.get(path).status_code == 401


def test_denied_user_directory_stays_403_not_500(flow_api):
    client, db = flow_api
    db.verify_session.return_value.update(user_type='tenant_user', company={'company_id': 1})
    assert client.get('/api/users').status_code == 403
    db.get_all_users.assert_not_called()
    db.get_company_users.assert_not_called()


def test_invalid_new_password_cannot_partially_save_profile(flow_api):
    client, db = flow_api
    db.get_user_by_id.return_value = {'id': 8, 'user_type': 'tenant_user'}
    response = client.put('/api/users/8', data={'full_name': 'Must not save', 'new_password': 'short'})
    assert response.status_code == 400
    db.update_user.assert_not_called()
    db.change_password.assert_not_called()


def test_company_user_query_does_not_select_password_hashes():
    db = DatabaseManager.__new__(DatabaseManager)
    db.get_cursor = MagicMock()
    cursor = MagicMock()
    db.get_cursor.return_value.__enter__.return_value = (cursor, None)
    db.get_company_users(1)
    query = cursor.execute.call_args.args[0].lower()
    assert 'u.*' not in query and 'password_hash' not in query


def test_profile_edit_does_not_copy_password_hash_into_audit():
    db = DatabaseManager.__new__(DatabaseManager)
    db.get_cursor = MagicMock()
    db.log_audit = MagicMock()
    cursor = MagicMock()
    cursor.rowcount = 1
    db.get_cursor.return_value.__enter__.return_value = (cursor, None)
    cursor.fetchone.return_value = {'id': 8, 'full_name': 'Fixture', 'password_hash': 'synthetic-hash-marker'}
    db.update_user(8, {'full_name': 'Updated'}, 7)
    assert 'password_hash' not in db.log_audit.call_args.args[5]


@pytest.mark.parametrize('path,field', [('/api/generate-jd', 'job_title'),
    ('/api/enhance-jd', 'existing_content'), ('/api/extract-jd-keywords', 'content')])
def test_empty_ai_forms_are_rejected_without_provider_calls(flow_api, monkeypatch, path, field):
    client, _db = flow_api
    calls = [MagicMock() for _ in range(3)]
    for name, call in zip(('generate_jd_with_gemini', 'enhance_jd_with_gemini', 'extract_keywords_with_gemini'), calls):
        monkeypatch.setattr(main, name, call)
    assert client.post(path, data={field: '   '}).status_code == 422
    for call in calls:
        call.assert_not_called()


@pytest.mark.parametrize('skills', ['null', '42', '"Python"', '{"Python":true}', '[42]', '[["Python"]]', '[" "]'])
@pytest.mark.parametrize('path,field', [('/api/generate-jd', 'job_title'), ('/api/enhance-jd', 'existing_content')])
def test_malformed_skills_do_not_spend_ai(flow_api, monkeypatch, skills, path, field):
    client, _db = flow_api
    call = MagicMock(return_value={'success': True})
    monkeypatch.setattr(main, 'generate_jd_with_gemini', call)
    monkeypatch.setattr(main, 'enhance_jd_with_gemini', call)
    assert client.post(path, data={field: 'Fictional Engineer', 'skills': skills}).status_code == 422
    call.assert_not_called()


def test_valid_jd_details_are_unchanged_and_run_off_event_loop(flow_api, monkeypatch):
    import threading
    client, _db = flow_api
    seen = {}
    async def record_loop(*args, **kwargs):
        seen['loop_thread'] = threading.get_ident()
        return await original(*args, **kwargs)
    original = main.asyncio.to_thread
    def generate(details):
        seen['worker_thread'] = threading.get_ident()
        seen['details'] = details
        return {'success': True, 'job_description': '<h2>Fictional Engineer</h2>'}
    monkeypatch.setattr(main.asyncio, 'to_thread', record_loop)
    monkeypatch.setattr(main, 'generate_jd_with_gemini', generate)
    response = client.post('/api/generate-jd', data={'job_title': 'Fictional Engineer',
        'company_name': 'Example QA', 'description': 'Build reliable services.', 'skills': '["Python","SQL"]'})
    assert response.status_code == 200 and response.json()['success']
    assert seen['details']['skills'] == ['Python', 'SQL']
    assert seen['details']['description'] == 'Build reliable services.'
    assert seen['worker_thread'] != seen['loop_thread']


@pytest.mark.parametrize('extension', ['txt', 'docx'])
def test_paperclip_parses_real_fictional_files_without_ai(flow_api, monkeypatch, extension):
    client, _db = flow_api
    text = 'Fictional Python Engineer. Required skills: Python, SQL and automated testing.'
    stream = BytesIO()
    if extension == 'docx':
        document = Document()
        document.add_paragraph(text)
        document.save(stream)
        content = stream.getvalue()
    else:
        content = text.encode()
    ai = MagicMock()
    monkeypatch.setattr(main, 'gemini_client', ai)
    response = client.post('/api/parse-jd-file', files={'file': ('fixture.'+extension, content)})
    assert response.status_code == 200
    assert text in response.json()['text'] and not response.json()['truncated']
    ai.assert_not_called()


@pytest.mark.parametrize('name,content,status', [('fixture.exe', b'not allowed', 400),
    ('fixture.txt', b'', 400), ('fixture.txt', b'x'*(10*1024*1024+1), 400)])
def test_paperclip_rejects_invalid_files(flow_api, name, content, status):
    client, _db = flow_api
    assert client.post('/api/parse-jd-file', files={'file': (name, content)}).status_code == status


@pytest.fixture
def account_db(queue_db):
    db = queue_db
    with db.get_cursor() as (cursor, _):
        cursor.execute('''
            CREATE SEQUENCE fixture_user_ids START 100;
            ALTER TABLE users ALTER COLUMN id SET DEFAULT nextval('fixture_user_ids');
            ALTER TABLE users ADD COLUMN password_hash TEXT, ADD COLUMN full_name TEXT,
                ADD COLUMN created_at TIMESTAMP DEFAULT NOW(), ADD COLUMN last_login TIMESTAMP;
            ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE;
            ALTER TABLE tenant_companies ADD COLUMN subscription_plan TEXT, ADD COLUMN max_users INTEGER,
                ADD COLUMN max_resumes INTEGER, ADD COLUMN created_by INTEGER, ADD COLUMN gcs_bucket_name TEXT,
                ADD COLUMN datastore_id TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE,
                ADD COLUMN created_at TIMESTAMP DEFAULT NOW(), ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
            ALTER TABLE user_companies ADD COLUMN role TEXT, ADD COLUMN joined_at TIMESTAMP DEFAULT NOW();
            CREATE TABLE user_sessions (session_token TEXT PRIMARY KEY, user_id INTEGER, expires_at TIMESTAMP,
                ip_address TEXT, user_agent TEXT);
            CREATE TABLE audit_logs (user_id INTEGER,company_id INTEGER,action TEXT,entity_type TEXT,
                entity_id INTEGER,old_values JSONB,new_values JSONB,ip_address TEXT,user_agent TEXT);
        ''')
    return db


def test_real_sql_account_company_login_profile_password_logout_and_delete(account_db, monkeypatch):
    db = account_db
    monkeypatch.setattr(main, 'get_db_manager', lambda: db)
    monkeypatch.setattr(main.limiter, 'enabled', False)
    monkeypatch.setattr(main, 'create_company_gcs_bucket', lambda *_: 'fixture-bucket')
    monkeypatch.setattr(main, 'create_company_datastore', lambda *_: 'fixture-store')
    password = 'synthetic-fixture-password'
    admin = db.create_user('admin@example.invalid', password, 'Fixture Admin', 'super_admin')
    client = TestClient(main.app, base_url='https://testserver')
    login = client.post('/api/login', data={'email': 'admin@example.invalid', 'password': password})
    assert login.status_code == 200
    assert 'httponly' in login.headers['set-cookie'].lower() and 'secure' in login.headers['set-cookie'].lower()
    client.headers['X-CSRF-Token'] = client.cookies.get('csrf_token')
    assert client.get('/api/me').json()['user']['id'] == admin
    created = client.post('/api/companies', data={'company_name': 'Fictional QA', 'company_code': 'fictional-qa'})
    assert created.status_code == 200
    company = created.json()['company_id']
    assert client.put(f'/api/companies/{company}', data={'company_name': 'Fictional QA Updated'}).status_code == 200
    assert db.get_company_by_id(company)['company_name'] == 'Fictional QA Updated'
    created = client.post('/api/users', data={'email': 'candidate@example.invalid', 'password': password,
        'full_name': 'Fixture User', 'user_type': 'tenant_user', 'company_id': company})
    assert created.status_code == 200
    uid = created.json()['user_id']
    listing = client.get(f'/api/companies/{company}/users')
    assert listing.status_code == 200 and listing.json()['count'] == 1
    assert 'password_hash' not in listing.text
    assert client.put(f'/api/users/{uid}', data={'full_name': 'Updated Fixture'}).status_code == 200
    assert db.get_user_by_id(uid)['full_name'] == 'Updated Fixture'
    assert client.delete(f'/api/users/{admin}').status_code == 400
    tenant = TestClient(main.app, base_url='https://testserver')
    assert tenant.post('/api/login', data={'email': 'candidate@example.invalid', 'password': password}).status_code == 200
    tenant.headers['X-CSRF-Token'] = tenant.cookies.get('csrf_token')
    assert tenant.get('/api/users').status_code == 403
    assert tenant.post('/api/change-password', data={'current_password': password, 'new_password': password+'-new'}).status_code == 200
    assert db.authenticate_user('candidate@example.invalid', password) is None
    assert tenant.post('/api/logout').status_code == 200
    assert tenant.get('/api/me').status_code == 401
    assert client.delete(f'/api/users/{uid}').status_code == 200
    assert db.get_user_by_id(uid) is None
    assert client.post('/api/logout').status_code == 200
    assert client.get('/api/me').status_code == 401
