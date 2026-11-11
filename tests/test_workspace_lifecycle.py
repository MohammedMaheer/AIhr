from datetime import date, timedelta
from pathlib import Path
import re
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import main
from services import calendar_changes, interview_management
from services.workspace_records import SCHEMA_SQL
from test_durable_search import queue_db


@pytest.fixture
def records(queue_db, monkeypatch):
    db=queue_db
    with db.get_cursor() as (cur,_):
        cur.execute('''INSERT INTO users(id,email,user_type,is_active) VALUES (7,'fixture@example.invalid','tenant_user',TRUE),(8,'other@example.invalid','tenant_user',TRUE);
            INSERT INTO tenant_companies(id,company_name) VALUES (1,'Fixture'),(2,'Other');
            CREATE TABLE scheduled_interviews(id SERIAL PRIMARY KEY,candidate_name TEXT,candidate_email TEXT,
                interview_type TEXT,interview_date DATE,interview_time TIME,duration_minutes INTEGER,
                location TEXT,interviewer TEXT,notes TEXT,created_by TEXT,company_id INTEGER,status TEXT,
                meeting_provider TEXT,meeting_join_url TEXT,meeting_event_id TEXT,job_application_id BIGINT);
            CREATE TABLE audit_logs(user_id INTEGER,company_id INTEGER,action TEXT,entity_type TEXT,
                entity_id INTEGER,old_values JSONB,new_values JSONB);
        ''')
        cur.execute(SCHEMA_SQL)
        cur.execute('''INSERT INTO scheduled_interviews(candidate_name,candidate_email,interview_type,interview_date,
            interview_time,duration_minutes,location,interviewer,notes,created_by,company_id,status,time_zone,position)
            VALUES ('Fictional Candidate','fixture@example.invalid','video',%s,'10:00',60,'Office','Recruiter','Private notes','7',1,'scheduled','Asia/Dubai','Engineer') RETURNING id''',
            (date.today()+timedelta(days=30),))
        record_id=cur.fetchone()['id']
    actor={'id':7,'user_type':'tenant_user','company':{'company_id':1},'email':'fixture@example.invalid'}
    monkeypatch.setattr(db,'verify_session',lambda _token: actor)
    monkeypatch.setattr(main,'get_db_manager',lambda:db)
    monkeypatch.setattr(main.limiter,'enabled',False)
    client=TestClient(main.app,base_url='https://testserver')
    client.cookies.set('session_token','synthetic-session');client.cookies.set('csrf_token','synthetic-csrf')
    client.headers['X-CSRF-Token']='synthetic-csrf'
    return client,db,record_id,actor


def read(client,record_id):
    response=client.get(f'/api/interviews/{record_id}')
    assert response.status_code==200
    return response.json()['interview']


def edit_payload(row, **changes):
    return {'version':row['version'],'interview_date':str(date.today()+timedelta(days=31)),
        'interview_time':'11:30','time_zone':'Asia/Dubai','duration':'45','interview_type':'technical',
        'position':'Updated Engineer','location':'Office B','interviewer':'Fixture Recruiter','notes':'Keep private',
        'confirm_calendar_change':True,**changes}


def test_lifecycle_migration_matches_runtime_schema():
    sql=Path('deploy/vps/migrations/20261105_workspace_lifecycle.sql').read_text()
    sql=sql[sql.index('ALTER TABLE'):]
    assert re.sub(r'\s+','',sql)==re.sub(r'\s+','',SCHEMA_SQL)


def test_local_edit_cancel_preserves_booking_and_atomic_audit(records):
    client,db,record_id,_actor=records
    row=read(client,record_id)
    response=client.put(f'/api/interviews/{record_id}',json=edit_payload(row))
    assert response.status_code==200 and response.json()['success']
    row=read(client,record_id)
    assert row['position']=='Updated Engineer' and row['notes']=='Keep private'
    assert str(row['interview_time'])=='11:30:00'
    response=client.request('DELETE',f'/api/interviews/{record_id}',json={'version':row['version']})
    assert response.status_code==200
    assert read(client,record_id)['status']=='cancelled'
    with db.get_cursor() as (cur,_):
        cur.execute('SELECT count(*) AS n FROM scheduled_interviews');assert cur.fetchone()['n']==1
        cur.execute('SELECT action FROM audit_logs ORDER BY action');assert {row['action'] for row in cur.fetchall()}=={'EDIT_INTERVIEW','CANCEL_INTERVIEW'}
        cur.execute("SELECT count(*) AS n FROM interview_operations WHERE state='completed'");assert cur.fetchone()['n']==2


@pytest.mark.parametrize('changes',[{'interview_date':'2000-01-01'},{'time_zone':'Bad/Zone'},
    {'duration':0},{'position':'x\nBcc: bad'},{'version':'stale'}])
def test_invalid_or_stale_edits_never_create_operation(records,changes):
    client,db,record_id,_actor=records
    response=client.put(f'/api/interviews/{record_id}',json=edit_payload(read(client,record_id),**changes))
    assert response.status_code in (409,422)
    with db.get_cursor() as (cur,_):
        cur.execute('SELECT count(*) AS n FROM interview_operations');assert cur.fetchone()['n']==0


def test_ownership_fails_closed_for_reads_edits_cancels_and_reconciliation(records):
    client,_db,record_id,actor=records
    row=read(client,record_id);actor['id']=8
    for method,path,body in [('GET',f'/api/interviews/{record_id}',None),('PUT',f'/api/interviews/{record_id}',edit_payload(row)),
        ('DELETE',f'/api/interviews/{record_id}',{'version':row['version']}),('POST',f'/api/interviews/{record_id}/reconcile',{})]:
        assert client.request(method,path,json=body).status_code==404


def linked(db,record_id):
    with db.get_cursor() as (cur,_):
        cur.execute("UPDATE scheduled_interviews SET meeting_provider='teams',meeting_event_id='synthetic-event',calendar_account_id='stable-account' WHERE id=%s",(record_id,))


def test_calendar_cancellation_is_confirmed_once_and_retains_history(records,monkeypatch):
    client,db,record_id,_actor=records;linked(db,record_id)
    call=MagicMock(return_value={'success':True});monkeypatch.setattr(calendar_changes,'change_event',call)
    body={'version':read(client,record_id)['version']}
    assert client.request('DELETE',f'/api/interviews/{record_id}',json=body).status_code==422
    call.assert_not_called()
    body['confirm_calendar_change']=True
    assert client.request('DELETE',f'/api/interviews/{record_id}',json=body).status_code==200
    assert client.request('DELETE',f'/api/interviews/{record_id}',json=body).status_code==200
    assert call.call_count==1 and read(client,record_id)['status']=='cancelled'


def test_uncertain_calendar_outcome_blocks_retry_then_read_reconciles(records,monkeypatch):
    client,db,record_id,_actor=records;linked(db,record_id)
    def uncertain(row,action,target,user,db,before):
        before({'account_id':'stable-account','start':'2030-01-01T10:00:00+00:00','end':'2030-01-01T11:00:00+00:00','subject':'Synthetic','cancelled':False})
        return {'success':False,'uncertain':True,'error':'Check calendar before retrying'}
    call=MagicMock(side_effect=uncertain);monkeypatch.setattr(calendar_changes,'change_event',call)
    body={'version':read(client,record_id)['version'],'confirm_calendar_change':True}
    assert client.request('DELETE',f'/api/interviews/{record_id}',json=body).json()['sync_unknown']
    assert client.request('DELETE',f'/api/interviews/{record_id}',json=body).status_code==409
    assert call.call_count==1
    assert client.post(f'/api/interviews/{record_id}/reconcile').status_code==409
    with db.get_cursor() as (cur,_):cur.execute("UPDATE interview_operations SET created_at=NOW()-interval '5 minutes'")
    inspect=MagicMock(return_value={'success':True,'snapshot':{'cancelled':True,'account_id':'stable-account'}})
    monkeypatch.setattr(calendar_changes,'inspect_event',inspect)
    assert client.post(f'/api/interviews/{record_id}/reconcile').json()['success']
    assert read(client,record_id)['status']=='cancelled' and call.call_count==1


def test_template_create_edit_render_soft_delete_and_scope(records):
    client,db,_record_id,actor=records
    body={'name':'Fictional details','subject':'{{ position }} at {{ company }}','message':'Hi {{ candidate_name }},\n\nPlease share your availability.'}
    response=client.post('/api/outreach-templates',json=body)
    assert response.status_code==200
    template=response.json()['template'];template_id=template['id']
    assert len(client.get('/api/outreach-templates').json()['templates'])==1
    assert client.put(f'/api/outreach-templates/{template_id}',json={**body,'version':99}).status_code==409
    response=client.put(f'/api/outreach-templates/{template_id}',json={**body,'name':'Updated','version':template['version']})
    assert response.status_code==200;template=response.json()['template']
    draft=client.post(f'/api/outreach-templates/{template_id}/draft',json={'candidate_name':'Fixture','position':'Engineer','company':'Example'}).json()
    assert draft['subject']=='Engineer at Example' and 'Hi Fixture,' in draft['message']
    actor['id']=8
    assert client.get('/api/outreach-templates').json()['templates']==[]
    assert client.request('DELETE',f'/api/outreach-templates/{template_id}',json={'version':template['version']}).status_code==404
    actor['id']=7
    assert client.request('DELETE',f'/api/outreach-templates/{template_id}',json={'version':template['version']}).status_code==200
    assert client.get('/api/outreach-templates').json()['templates']==[]
    with db.get_cursor() as (cur,_):
        cur.execute('SELECT deleted,message FROM outreach_message_templates WHERE id=%s',(template_id,))
        row=cur.fetchone();assert row['deleted'] and row['message']==body['message']


@pytest.mark.parametrize('field,value',[('name',''),('subject','x\r\nBcc: invalid'),('message','{{ "".__class__ }}')])
def test_template_validation_rejects_unsafe_input(records,field,value):
    client,_db,_record_id,_actor=records
    body={'name':'Fixture','subject':'Hello','message':'Hello {{ candidate_name }}',field:value}
    assert client.post('/api/outreach-templates',json=body).status_code==422


def test_schedule_history_is_scoped_paginated_and_retains_cancelled_records(records):
    client,db,record_id,actor=records
    response=client.get('/api/interviews?page=1&page_size=1').json()
    assert response['total']==1 and response['interviews'][0]['id']==record_id
    assert client.get('/api/interviews?page=2&page_size=1').json()['interviews']==[]
    for query in ('page=0','page_size=101','status=invalid'):
        assert client.get('/api/interviews?'+query).status_code==422
    client.request('DELETE',f'/api/interviews/{record_id}',json={'version':read(client,record_id)['version']})
    assert client.get('/api/interviews?status=scheduled').json()['total']==0
    assert client.get('/api/interviews?status=cancelled').json()['total']==1
    assert read(client,record_id)['history'][0]['action']=='cancel'
    actor['company']={'company_id':2}
    assert client.get('/api/interviews').json()['total']==0
    actor['company']={'company_id':1};actor['id']=8
    assert client.get('/api/interviews').json()['total']==0


def test_location_only_uncertain_edit_is_not_falsely_reconciled(records,monkeypatch):
    client,db,record_id,_actor=records;linked(db,record_id)
    previous={}
    desired={}
    def uncertain(row,action,target,user,db,before):
        desired.update(calendar_changes.target_snapshot(target))
        previous.update(desired,location='Office A',account_id='stable-account')
        before(previous)
        return {'success':False,'uncertain':True,'error':'Check calendar'}
    monkeypatch.setattr(calendar_changes,'change_event',uncertain)
    payload=edit_payload(read(client,record_id),location='Office B')
    assert client.put(f'/api/interviews/{record_id}',json=payload).json()['sync_unknown']
    with db.get_cursor() as (cur,_):cur.execute("UPDATE interview_operations SET created_at=NOW()-interval '5 minutes'")
    monkeypatch.setattr(calendar_changes,'inspect_event',lambda *args,**kwargs:{'success':True,'snapshot':previous})
    result=client.post(f'/api/interviews/{record_id}/reconcile').json()
    assert result['success'] and 'unchanged' in result['message']
    assert read(client,record_id)['location']=='Office'
    with db.get_cursor() as (cur,_):
        cur.execute('SELECT state FROM interview_operations');assert cur.fetchone()['state']=='failed'
        cur.execute('SELECT count(*) AS n FROM audit_logs');assert cur.fetchone()['n']==0
