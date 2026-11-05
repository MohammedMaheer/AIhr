"""Owner-scoped changes with durable pending/uncertain states and atomic local audit."""
from datetime import datetime, timezone
import json
import secrets

from fastapi import HTTPException
from psycopg2.extras import Json

from services.workspace_records import get_interview, interview_version, owned_interview
from services.outreach_validation import validate_interview, validate_future
from services.interview_time import utc_start
from services import calendar_changes


def serial(value):
    return json.loads(json.dumps(value,default=str))


def _finish(db, operation):
    old,target=operation['old_data'],operation['target_data']
    with db.get_cursor() as (cursor,_):
        row=owned_interview(cursor,operation['interview_id'],operation['actor_id'],old.get('company_id'),lock=True)
        if interview_version(row)!=interview_version(old):
            raise HTTPException(409,'The booking changed while the calendar was being updated. Check the calendar before continuing.')
        if operation['action']=='cancel':
            cursor.execute("UPDATE scheduled_interviews SET status='cancelled' WHERE id=%s",(row['id'],))
        else:
            cursor.execute('''UPDATE scheduled_interviews SET interview_date=%s,interview_time=%s,duration_minutes=%s,
                interview_type=%s,location=%s,interviewer=%s,notes=%s,position=%s,time_zone=%s WHERE id=%s''',
                (target['interview_date'],target['interview_time'],target['duration'],target['interview_type'],
                 target['location'],target['interviewer'],target['notes'],target['position'],target['time_zone'],row['id']))
        cursor.execute("UPDATE interview_operations SET state='completed',completed_at=NOW(),error=NULL WHERE operation_id=%s",(operation['operation_id'],))
        cursor.execute('''INSERT INTO audit_logs(user_id,company_id,action,entity_type,entity_id,old_values,new_values)
            VALUES (%s,%s,%s,'scheduled_interviews',%s,%s,%s)''',
            (operation['actor_id'],old.get('company_id'),'CANCEL_INTERVIEW' if operation['action']=='cancel' else 'EDIT_INTERVIEW',
             row['id'],Json(serial(old)),Json({'status':'cancelled'} if operation['action']=='cancel' else target)))
    return {'success':True,'status':'cancelled' if operation['action']=='cancel' else 'scheduled'}


def change(db, interview_id, user_id, company_id, action, data):
    if action not in ('edit','cancel') or not isinstance(data,dict):raise HTTPException(422,'Invalid interview change')
    with db.get_cursor() as (cursor,_):
        row=owned_interview(cursor,interview_id,user_id,company_id,lock=True)
        if row.get('status')=='cancelled' and action=='cancel':return {'success':True,'status':'cancelled'}
        if row.get('status')!='scheduled':raise HTTPException(409,'This interview is no longer scheduled')
        if data.get('version')!=interview_version(row):raise HTTPException(409,'This booking changed. Reload it before saving.')
        cursor.execute("SELECT 1 FROM interview_operations WHERE interview_id=%s AND state IN ('pending','unknown')",(interview_id,))
        if cursor.fetchone():raise HTTPException(409,'A previous calendar change needs confirmation. Use Check calendar first.')
        external=bool(row.get('meeting_provider') not in (None,'','none','in_person','in-person','phone'))
        if external and data.get('confirm_calendar_change') is not True:raise HTTPException(422,'Confirm the linked calendar update')
        if action=='edit':
            fields=('interview_date','interview_time','duration','interview_type','location','interviewer','notes','position','time_zone')
            target={key:data.get(key) for key in fields}
            target.update(candidate_name=row['candidate_name'],candidate_email=row.get('candidate_email') or '',send_invite_email=False)
            try:
                validate_interview(target)
                start,duration=utc_start(target);validate_future(start)
                if not target.get('time_zone'):raise ValueError('Choose the interview time zone')
            except ValueError as exc:raise HTTPException(422,str(exc)) from None
            target.update(start_iso=start,duration=duration)
        else:target={'status':'cancelled'}
        operation={'operation_id':secrets.token_urlsafe(24),'interview_id':interview_id,'actor_id':user_id,
                   'action':action,'old_data':serial(row),'target_data':serial(target)}
        cursor.execute('''INSERT INTO interview_operations(operation_id,interview_id,actor_id,action,state,old_data,target_data)
            VALUES (%s,%s,%s,%s,'pending',%s,%s)''',
            (operation['operation_id'],interview_id,user_id,action,Json(operation['old_data']),Json(operation['target_data'])))
    # The intent is committed before any provider write; crashes cannot silently allow duplicate updates.
    def before(snapshot):
        with db.get_cursor() as (cursor,_):
            cursor.execute('UPDATE interview_operations SET provider_before=%s WHERE operation_id=%s',
                           (Json(snapshot),operation['operation_id']))
    try:
        result=calendar_changes.change_event(row,action,target,user_id,db,before) if external else {'success':True}
    except Exception:
        result={'success':False,'error':'The calendar could not be checked. No change was confirmed.'}
    if result.get('success'):
        try:return _finish(db,operation)
        except Exception:
            result={'success':False,'uncertain':True,'error':'The calendar update was accepted but the local save could not be confirmed. Use Check calendar before retrying.'}
    with db.get_cursor() as (cursor,_):
        cursor.execute('UPDATE interview_operations SET state=%s,error=%s WHERE operation_id=%s',
            ('unknown' if result.get('uncertain') else 'failed',result.get('error'),operation['operation_id']))
    return {'success':False,'sync_unknown':bool(result.get('uncertain')),'error':result.get('error') or 'Interview change was not confirmed.'}


def reconcile(db,interview_id,user_id,company_id):
    with db.get_cursor() as (cursor,_):
        row=owned_interview(cursor,interview_id,user_id,company_id)
        cursor.execute("SELECT * FROM interview_operations WHERE interview_id=%s AND state IN ('pending','unknown')",(interview_id,))
        operation=cursor.fetchone()
    if not operation:return {'success':True,'pending_change':False}
    operation=dict(operation)
    created=operation['created_at'].replace(tzinfo=timezone.utc) if operation['created_at'].tzinfo is None else operation['created_at']
    if (datetime.now(timezone.utc)-created).total_seconds()<120:raise HTTPException(409,'The change may still be processing. Check again in two minutes.')
    before=operation.get('provider_before')
    if not row.get('meeting_provider') or row.get('meeting_provider') in {'none','phone','in_person','in-person'}:
        if interview_version(row)!=interview_version(operation['old_data']):raise HTTPException(409,'The booking has changed. Review its audit record.')
        with db.get_cursor() as (cursor,_):
            cursor.execute("UPDATE interview_operations SET state='failed',error='Local transaction not applied' WHERE operation_id=%s",(operation['operation_id'],))
        return {'success':True,'pending_change':False,'message':'The original booking is unchanged. You may review and retry.'}
    if not before:
        with db.get_cursor() as (cursor,_):
            cursor.execute("UPDATE interview_operations SET state='failed',error='No provider write was started' WHERE operation_id=%s",(operation['operation_id'],))
        return {'success':True,'pending_change':False,'message':'No calendar change was sent. You may review and retry.'}
    result=calendar_changes.inspect_event(row,user_id,db,expected_account=before.get('account_id'))
    if not result.get('success'):return result
    current=result['snapshot']
    matches=current.get('cancelled') if operation['action']=='cancel' else all(
        current.get(key)==value for key,value in calendar_changes.target_snapshot(operation['target_data']).items())
    if matches:return _finish(db,operation)
    if all(current.get(key)==before.get(key) for key in ('start','end','subject','location','cancelled')):
        with db.get_cursor() as (cursor,_):
            cursor.execute("UPDATE interview_operations SET state='failed',error='Calendar unchanged; retry permitted after review' WHERE operation_id=%s",(operation['operation_id'],))
        return {'success':True,'pending_change':False,'message':'The original calendar event is unchanged. You may review and retry the change.'}
    raise HTTPException(409,'The calendar differs from both versions. Review it with the organizer before continuing.')
