import asyncio
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import threading
import time
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from services import calendar_service as calendar
from test_durable_search import queue_db


def client_for(database, *, company=1, role='tenant_user'):
    database.verify_session.return_value = {'id': 7, 'user_type': role,
        'company': {'company_id': company} if company else None}
    client = TestClient(main.app)
    client.cookies.set('session_token', 'synthetic-session')
    client.cookies.set('csrf_token', 'synthetic-csrf')
    client.headers['X-CSRF-Token']='synthetic-csrf'
    return client


@pytest.mark.parametrize('endpoint,method,data', [
    ('/api/candidate-state?ids=1', 'get', None),
    ('/api/candidate-action', 'post', {'search_result_id':1,'candidate_name':'QA','action_type':'selected'}),
    ('/api/candidate-notes/1', 'patch', {'comments':'QA note'}),
])
def test_candidate_routes_fail_closed_without_tenant(endpoint, method, data):
    db = MagicMock()
    with patch.object(main, 'get_db_manager', return_value=db):
        client = client_for(db, company=None)
        kwargs = {'data':data} if method=='post' else {'json':data} if method=='patch' else {}
        assert getattr(client, method)(endpoint, **kwargs).status_code == 403
    db.save_candidate_action.assert_not_called()
    db.save_candidate_notes.assert_not_called()
    db.get_candidate_states.assert_not_called()


@pytest.mark.parametrize('ids', ['', '0', '-1', '1 OR TRUE', '2147483648', '1,,2', ','.join(['1']*101)])
def test_candidate_state_rejects_invalid_ids_before_query(ids):
    db = MagicMock()
    with patch.object(main, 'get_db_manager', return_value=db):
        response = client_for(db).get('/api/candidate-state', params={'ids':ids})
    assert response.status_code == 422
    db.get_candidate_states.assert_not_called()


def test_candidate_state_is_tenant_scoped_and_deduplicated():
    db = MagicMock()
    db.get_candidate_states.return_value = [{'search_result_id': 1, 'status': None, 'comments': 'QA'}]
    with patch.object(main, 'get_db_manager', return_value=db):
        response = client_for(db, company=27).get('/api/candidate-state?ids=1,1,2')
    assert response.status_code == 200
    db.get_candidate_states.assert_called_once_with([1,2],27)


@pytest.mark.parametrize('method,path', [('get','/api/email-templates'),('post','/api/email-templates'),
    ('put','/api/email-templates/1'),('delete','/api/email-templates/1'),
    ('post','/api/send-candidate-email')])
def test_integrations_cannot_use_global_workspace_when_tenant_is_missing(method,path):
    db=MagicMock()
    data={'kind':'custom','name':'QA','subject':'Hello','body':'Hello',
          'candidate_name':'Synthetic CV','candidate_email':'qa@example.invalid',
          'raw_subject':'Hello','raw_body':'Hello'}
    with patch.object(main,'get_db_manager',return_value=db), \
         patch('services.email_service.send_email') as sender:
        client=client_for(db,company=None)
        response=getattr(client,method)(path,**({'json':data} if method in ('post','put') else {}))
    assert response.status_code==403
    db.upsert_email_template.assert_not_called()
    db.delete_email_template.assert_not_called()
    sender.assert_not_called()


@pytest.mark.parametrize('path',['/api/dashboard-stats','/api/upcoming-events','/api/search-history',
    '/api/oauth/microsoft/start'])
def test_missing_workspace_is_rejected_by_shared_auth_boundary(path):
    db=MagicMock()
    with patch.object(main,'get_db_manager',return_value=db):
        response=client_for(db,company=None).get(path,follow_redirects=False)
    assert response.status_code==403


def test_unknown_account_role_cannot_use_authenticated_resources():
    db=MagicMock()
    with patch.object(main,'get_db_manager',return_value=db):
        response=client_for(db,role='unknown-role').get('/api/search-history')
    assert response.status_code==403


def test_index_includes_versioned_state_module_and_accessible_account_control():
    db=MagicMock()
    with patch.object(main,'get_db_manager',return_value=db):
        response=client_for(db).get('/')
    assert response.status_code==200
    html=response.text
    assert '/static/js/candidate-state.js?v=0' not in html
    assert html.index('/static/js/security.js?') < html.index('/static/js/candidate-state.js?') < html.index('/static/js/main.js?')
    assert 'aria-label="Account menu"' in html and 'aria-expanded="false"' in html


@pytest.mark.parametrize('payload', [None, [], {}, {'comments':123}, {'comments':'x'*10001}])
def test_notes_validate_before_write(payload):
    db = MagicMock()
    with patch.object(main, 'get_db_manager', return_value=db):
        response = client_for(db).patch('/api/candidate-notes/1', json=payload)
    assert response.status_code == 422
    db.save_candidate_notes.assert_not_called()


def test_notes_save_without_implying_any_candidate_decision():
    db = MagicMock()
    db.save_candidate_notes.return_value = True
    with patch.object(main, 'get_db_manager', return_value=db):
        response = client_for(db).patch('/api/candidate-notes/12', json={'comments':'Synthetic note'})
    assert response.status_code == 200 and response.json()['success']
    db.save_candidate_notes.assert_called_once_with(12,'Synthetic note','7',1)
    db.save_candidate_action.assert_not_called()


def test_task_results_include_saved_record_id_for_workflow_controls():
    db = MagicMock()
    db.get_task_status.return_value = {'user_id':'7','status':'completed','progress':{'search_id':5}}
    db.get_search_results.return_value = [{'id':123,'candidate_name':'Synthetic CV','gemini_analysis':{}}]
    with patch.object(main, 'get_db_manager', return_value=db):
        result = asyncio.run(main.get_hr_scorecard_task_results('qa-task', {'id':'7','user_type':'super_admin'}))
    assert result['results'][0]['id'] == '123'


def test_authentication_database_does_not_block_other_async_work():
    async def scenario():
        db = MagicMock()
        db.verify_session.side_effect = lambda token: (time.sleep(.05) or {'id':7})
        with patch.object(main, 'get_db_manager', return_value=db):
            task = asyncio.create_task(main.get_current_user(None,'synthetic'))
            await asyncio.sleep(.005)
            assert not task.done()
            assert (await task)['id'] == 7
    asyncio.run(scenario())


@pytest.mark.parametrize('reader',[main.get_hr_scorecard_task_status,main.get_hr_scorecard_task_results])
@pytest.mark.parametrize('company,task_company',[(None,None),(None,1),(1,None),(1,2)])
def test_task_reads_reject_missing_or_other_tenant(reader,company,task_company):
    db=MagicMock()
    db.get_task_status.return_value={'user_id':'7','company_id':task_company,'status':'completed'}
    user={'id':7,'user_type':'tenant_user','company':{'company_id':company} if company else None}
    with patch.object(main,'get_db_manager',return_value=db), pytest.raises(main.HTTPException) as exc:
        asyncio.run(reader('qa-task',user))
    assert exc.value.status_code==403
    db.get_search_results.assert_not_called()


@pytest.fixture
def state_db(queue_db):
    db = queue_db
    with db.get_cursor() as (cur,_):
        cur.execute('''CREATE TABLE candidate_actions (
            id SERIAL PRIMARY KEY, search_result_id INTEGER, candidate_name TEXT, action_type TEXT,
            action_status BOOLEAN, comments TEXT, user_id TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());
            INSERT INTO tenant_companies(id,company_name,company_code) VALUES (1,'First','first'),(2,'Second','second');''')
    db.ensure_candidate_state_schema()
    ids=[]
    for company_id in (1,2):
        search=db.save_search_history('Fictional JD','QA',1,7,company_id)
        db.save_search_results(search,[{'file_path':f'qa-{company_id}.txt','gemini_analysis':{}}],company_id,7)
        with db.get_cursor() as (cur,_):
            cur.execute('SELECT id FROM search_results WHERE search_id=%s',(search,))
            ids.append(cur.fetchone()['id'])
    return db,ids


def test_postgres_candidate_actions_are_exclusive_under_concurrent_writes(state_db):
    from concurrent.futures import ThreadPoolExecutor
    db,ids=state_db
    choices=['selected','shortlisted','rejected','interviewed']*3
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(pool.map(lambda status: db.save_candidate_action(ids[0],'QA',status,user_id='7',company_id=1),choices))
    with db.get_cursor() as (cur,_):
        cur.execute('SELECT count(*) AS n FROM candidate_actions WHERE search_result_id=%s AND action_status=TRUE',(ids[0],))
        assert cur.fetchone()['n']==1
        cur.execute('SELECT count(*) AS n FROM candidate_actions WHERE search_result_id=%s',(ids[0],))
        assert cur.fetchone()['n']==4


def test_postgres_notes_and_same_name_candidates_are_tenant_isolated(state_db):
    db,ids=state_db
    assert db.save_candidate_notes(ids[0],'First note','7',1)
    assert not db.save_candidate_notes(ids[1],'Wrong tenant','7',1)
    assert not db.save_candidate_action(ids[1],'QA','selected',user_id='7',company_id=1)
    assert db.get_candidate_states(ids,1)==[{'search_result_id':ids[0],'status':None,'comments':'First note'}]
    assert db.get_candidate_states([ids[1]],2)[0]['comments']==''
    assert db.save_candidate_action(ids[0],'QA','selected',user_id='7',company_id=1)
    assert db.save_candidate_action(ids[0],'QA','interviewed',user_id='7',company_id=1)
    assert db.get_candidate_states([ids[0]],1)[0]['comments']=='First note'
    assert next(row for row in db.get_candidate_actions(ids[0]) if row['action_status'])['comments']=='First note'


def test_postgres_legacy_notes_read_without_migration_or_decision_write(state_db):
    db,ids=state_db
    with db.get_cursor() as (cur,_):
        cur.execute("INSERT INTO candidate_actions(search_result_id,action_type,action_status,comments) VALUES (%s,'shortlisted',TRUE,'Legacy note')",(ids[0],))
    assert db.get_candidate_states([ids[0]],1)[0]['comments']=='Legacy note'
    assert db.save_candidate_notes(ids[0],'','7',1)
    assert db.get_candidate_states([ids[0]],1)[0]['comments']==''
    assert db.get_candidate_states([ids[0]],1)[0]['status']=='shortlisted'


def test_postgres_status_change_preserves_latest_legacy_note(state_db):
    db,ids=state_db
    with db.get_cursor() as (cur,_):
        cur.execute("""INSERT INTO candidate_actions(search_result_id,action_type,action_status,comments,updated_at)
            VALUES (%s,'selected',FALSE,'Old note',NOW()-interval '2 days'),
                   (%s,'shortlisted',TRUE,'Latest note',NOW()-interval '1 day')""",(ids[0],ids[0]))
    assert db.save_candidate_action(ids[0],'QA','selected',user_id='7',company_id=1)
    state=db.get_candidate_states([ids[0]],1)[0]
    assert state['status']=='selected' and state['comments']=='Latest note'


def test_postgres_api_candidate_workflow_round_trip_and_tenant_boundary(state_db):
    db,ids=state_db
    user={'id':7,'user_type':'tenant_user','company':{'company_id':1}}
    previous=dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.require_auth]=lambda:user
    try:
        with patch.object(main,'get_db_manager',return_value=db):
            client=TestClient(main.app)
            assert client.patch(f'/api/candidate-notes/{ids[0]}',json={'comments':'Fictional API note'}).status_code==200
            state=client.get('/api/candidate-state',params={'ids':','.join(map(str,ids))}).json()['candidates']
            assert state==[{'search_result_id':ids[0],'status':None,'comments':'Fictional API note'}]
            for status in ('shortlisted','selected'):
                response=client.post('/api/candidate-action',data={'search_result_id':ids[0],
                    'candidate_name':'Synthetic CV','action_type':status,'action_status':'true'})
                assert response.status_code==200
            state=client.get('/api/candidate-state',params={'ids':ids[0]}).json()['candidates'][0]
            assert state['status']=='selected' and state['comments']=='Fictional API note'
            assert client.patch(f'/api/candidate-notes/{ids[1]}',json={'comments':'forbidden'}).status_code==404
            with db.get_cursor() as (cur,_):
                cur.execute('SELECT count(*) AS n FROM candidate_actions WHERE action_status=TRUE')
                assert cur.fetchone()['n']==1
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)


def test_invalid_ai_scorecard_never_logs_the_full_cv_response(caplog):
    secret='QA_PRIVATE_CV_TEXT_DO_NOT_LOG'
    client=MagicMock()
    client.models.generate_content.return_value=SimpleNamespace(text=secret+'{')
    from unittest.mock import AsyncMock
    with patch.object(main,'gemini_client',return_value=client), \
         patch.object(main.asyncio,'sleep',new=AsyncMock()), pytest.raises(Exception):
        asyncio.run(main.analyze_resume_with_hr_scorecard('Fictional CV', 'Fictional JD'))
    assert secret not in caplog.text


@pytest.fixture
def oauth_db(queue_db,monkeypatch):
    monkeypatch.setenv('SECRET_KEY','synthetic-oauth-encryption-key-'*3)
    db=queue_db
    db.ensure_integrations_tables=lambda:None
    with db.get_cursor() as (cur,_):
        cur.execute('''CREATE TABLE oauth_tokens(id SERIAL PRIMARY KEY,user_id INTEGER,provider TEXT,
            access_token TEXT,refresh_token TEXT,expires_at TIMESTAMP,scope TEXT,email TEXT,extra JSONB,
            updated_at TIMESTAMP,UNIQUE(user_id,provider))''')
    db.save_oauth_token(7,'microsoft',access_token='qa-expired',refresh_token='qa-refresh',
                       expires_at=datetime.now(timezone.utc)-timedelta(hours=1),email='qa@example.invalid')
    return db


def test_postgres_cross_worker_refresh_rotates_once_and_encrypts(oauth_db):
    from concurrent.futures import ThreadPoolExecutor
    def refresh(*args):
        time.sleep(.1)
        return {'access_token':'qa-fresh','refresh_token':'qa-rotated','expires_in':3600}
    # Bypass process-local locks to exercise the actual cross-process boundary.
    with patch.object(calendar,'_refresh_locks',[nullcontext()]), \
         patch.object(calendar,'calendar_config',return_value={}), \
         patch.object(calendar,'_refresh_microsoft_token',side_effect=refresh) as provider:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:calendar._get_valid_token('microsoft',7,oauth_db),range(4)))
    assert results==[('qa-fresh','qa@example.invalid')]*4
    assert provider.call_count==1
    assert oauth_db.get_oauth_token(7,'microsoft')['refresh_token']=='qa-rotated'
    with oauth_db.get_cursor() as (cur,_):
        cur.execute('SELECT access_token,refresh_token FROM oauth_tokens')
        row=cur.fetchone()
        assert row['access_token']!='qa-fresh' and row['refresh_token']!='qa-rotated'


def test_postgres_disconnect_during_refresh_does_not_resurrect_credentials(oauth_db):
    from concurrent.futures import ThreadPoolExecutor
    started,release=threading.Event(),threading.Event()
    def refresh(*args):
        started.set()
        assert release.wait(5)
        return {'access_token':'qa-fresh','expires_in':3600}
    with patch.object(calendar,'calendar_config',return_value={}), \
         patch.object(calendar,'_refresh_microsoft_token',side_effect=refresh):
        with ThreadPoolExecutor(max_workers=2) as pool:
            token=pool.submit(calendar._get_valid_token,'microsoft',7,oauth_db)
            assert started.wait(5)
            delete=pool.submit(oauth_db.delete_oauth_token,7,'microsoft')
            try:
                time.sleep(.05)
                assert not delete.done()
            finally:
                release.set()
            assert token.result(timeout=5)[0]=='qa-fresh'
            assert delete.result(timeout=5)
    assert oauth_db.get_oauth_token(7,'microsoft') is None


def test_oauth_storage_failure_does_not_fall_back_to_shared_mailbox():
    db=MagicMock()
    db.get_oauth_token.side_effect=RuntimeError('unavailable')
    with patch.object(calendar,'_microsoft_app_only_token') as shared:
        assert calendar._get_valid_token('microsoft',7,db)==(None,None)
    shared.assert_not_called()
