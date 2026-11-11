"""Scoped reusable messages and durable audit records for interview changes."""
from hashlib import sha256
import json

from fastapi import HTTPException
from psycopg2.extras import Json

SCHEMA_SQL = """
ALTER TABLE scheduled_interviews
    ADD COLUMN IF NOT EXISTS position TEXT,
    ADD COLUMN IF NOT EXISTS time_zone TEXT,
    ADD COLUMN IF NOT EXISTS calendar_account_id TEXT;
CREATE TABLE IF NOT EXISTS outreach_message_templates (
    id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL, subject VARCHAR(998) NOT NULL, message TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1, deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outreach_templates_owner
    ON outreach_message_templates(owner_id,company_id) WHERE NOT deleted;
CREATE TABLE IF NOT EXISTS interview_operations (
    operation_id TEXT PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES scheduled_interviews(id) ON DELETE RESTRICT,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('edit','cancel')),
    state TEXT NOT NULL CHECK (state IN ('pending','unknown','failed','completed')),
    old_data JSONB NOT NULL, target_data JSONB NOT NULL, provider_before JSONB,
    error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_interview_operation_active
    ON interview_operations(interview_id) WHERE state IN ('pending','unknown');
CREATE INDEX IF NOT EXISTS idx_interview_operation_history
    ON interview_operations(interview_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interview_owner_schedule
    ON scheduled_interviews(created_by,company_id,interview_date DESC,id DESC);
"""


def template_values(data):
    from services.email_service import validate_template
    for field, limit in (('name',200),('subject',998),('message',32768)):
        if not isinstance(data.get(field), str) or not data[field].strip() or len(data[field]) > limit:
            raise HTTPException(422, f'Provide {field} of at most {limit} characters')
    if any(c in data['subject'] for c in '\r\n\x00'):
        raise HTTPException(422, 'Subject must be a single line')
    try:
        validate_template(data['subject']); validate_template(data['message'])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return {key: data[key].strip() for key in ('name','subject','message')}


def templates(db, owner_id, company_id, *, template_id=None, data=None, delete=False):
    with db.get_cursor() as (cursor, _):
        if template_id is None and data is None:
            cursor.execute('''SELECT id,name,subject,message,version FROM outreach_message_templates
                WHERE owner_id=%s AND company_id IS NOT DISTINCT FROM %s AND NOT deleted
                ORDER BY updated_at DESC LIMIT 200''',(owner_id,company_id))
            return [dict(row) for row in cursor.fetchall()]
        value = template_values(data) if not delete else None
        if template_id is None:
            cursor.execute('SELECT pg_advisory_xact_lock(724106408,%s)',(owner_id,))
            cursor.execute('SELECT count(*) AS count FROM outreach_message_templates WHERE owner_id=%s AND NOT deleted',(owner_id,))
            if cursor.fetchone()['count'] >= 200:
                raise HTTPException(409, 'Your template limit has been reached')
            cursor.execute('''INSERT INTO outreach_message_templates(owner_id,company_id,name,subject,message)
                VALUES (%s,%s,%s,%s,%s) RETURNING id,name,subject,message,version''',
                (owner_id,company_id,value['name'],value['subject'],value['message']))
        else:
            version = data.get('version') if isinstance(data,dict) else None
            if type(version) is not int or version < 1:
                raise HTTPException(422,'A valid template version is required')
            cursor.execute('''SELECT version FROM outreach_message_templates WHERE id=%s AND owner_id=%s
                AND company_id IS NOT DISTINCT FROM %s AND NOT deleted FOR UPDATE''',(template_id,owner_id,company_id))
            row=cursor.fetchone()
            if not row:raise HTTPException(404,'Template not found')
            if row['version'] != version:raise HTTPException(409,'This template changed. Reload it before saving.')
            if delete:
                cursor.execute('UPDATE outreach_message_templates SET deleted=TRUE,version=version+1,updated_at=NOW() WHERE id=%s',(template_id,))
                return {'deleted':True}
            cursor.execute('''UPDATE outreach_message_templates SET name=%s,subject=%s,message=%s,
                version=version+1,updated_at=NOW() WHERE id=%s RETURNING id,name,subject,message,version''',
                (value['name'],value['subject'],value['message'],template_id))
        return dict(cursor.fetchone())


def interview_version(row):
    return sha256(json.dumps(dict(row),sort_keys=True,default=str).encode()).hexdigest()


def owned_interview(cursor, interview_id, user_id, company_id, *, lock=False):
    cursor.execute('''SELECT * FROM scheduled_interviews WHERE id=%s AND created_by=%s
        AND company_id IS NOT DISTINCT FROM %s''' + (' FOR UPDATE' if lock else ''),
        (interview_id,str(user_id),company_id))
    row=cursor.fetchone()
    if not row:raise HTTPException(404,'Scheduled interview not found')
    return dict(row)


def get_interview(db, interview_id, user_id, company_id):
    with db.get_cursor() as (cursor,_):
        row=owned_interview(cursor,interview_id,user_id,company_id)
        cursor.execute("SELECT operation_id,state FROM interview_operations WHERE interview_id=%s AND state IN ('pending','unknown')",(interview_id,))
        pending=cursor.fetchone()
        cursor.execute('''SELECT action,state,created_at,completed_at FROM interview_operations
            WHERE interview_id=%s ORDER BY created_at DESC LIMIT 20''',(interview_id,))
        history=[dict(item) for item in cursor.fetchall()]
        return {**row,'version':interview_version(row),'pending_change':dict(pending) if pending else None,'history':history}


def list_interviews(db,user_id,company_id,page=1,page_size=25,status='all'):
    if page<1 or not 1<=page_size<=100 or status not in {'all','scheduled','cancelled'}:
        raise HTTPException(422,'Invalid schedule filters')
    where='created_by=%s AND company_id IS NOT DISTINCT FROM %s'
    params=[str(user_id),company_id]
    if status!='all':where+=' AND status=%s';params.append(status)
    with db.get_cursor() as (cursor,_):
        cursor.execute('SELECT count(*) AS count FROM scheduled_interviews WHERE '+where,params)
        total=cursor.fetchone()['count']
        cursor.execute('''SELECT id,candidate_name,position,interview_date,interview_time,time_zone,status,
            job_application_id
            FROM scheduled_interviews WHERE '''+where+' ORDER BY interview_date DESC,id DESC LIMIT %s OFFSET %s',
            params+[page_size,(page-1)*page_size])
        return {'success':True,'interviews':[dict(row) for row in cursor.fetchall()],'total':total,'page':page,'page_size':page_size}
