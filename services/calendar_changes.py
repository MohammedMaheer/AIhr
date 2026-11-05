"""Conditional changes to the existing organizer event, never a replacement booking."""
from datetime import datetime, timedelta, timezone
import logging
from urllib.parse import quote

import requests

from services.calendar_service import _get_valid_token

log = logging.getLogger(__name__)


def iso(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def inspect_event(row, user_id, db, *, expected_account=None):
    provider='microsoft' if row.get('meeting_provider') in {'teams','microsoft','ms_teams','ms-teams'} else 'google'
    if row.get('meeting_provider') not in {'teams','microsoft','ms_teams','ms-teams','meet','google','google_meet','google-meet'}:
        return {'success':False,'error':'The linked calendar provider is not supported.'}
    saved=db.get_oauth_token(user_id,provider)
    account=(saved.get('extra') or {}).get('account_id') if isinstance(saved,dict) else None
    if not account or not saved.get('email'):
        return {'success':False,'error':'Reconnect the original organizer account before changing this interview.'}
    expected=expected_account or row.get('calendar_account_id')
    if expected and expected != account:
        return {'success':False,'error':'The original organizer account is not connected.'}
    token,actor=_get_valid_token(provider,user_id,db,delegated_actor=True)
    if not token or (provider=='microsoft' and actor!='me'):
        return {'success':False,'error':'The organizer account needs to be reconnected.'}
    event_id=row.get('meeting_event_id')
    if not isinstance(event_id,str) or not event_id:
        return {'success':False,'error':'This booking has no linked event ID. Check the organizer calendar before changing it.'}
    base='https://graph.microsoft.com/v1.0/me/events/' if provider=='microsoft' else 'https://www.googleapis.com/calendar/v3/calendars/primary/events/'
    url=base+quote(event_id,safe='')
    headers={'Authorization':'Bearer '+token,'Prefer':'outlook.timezone="UTC"'}
    try:
        response=requests.get(url,headers=headers,timeout=15,allow_redirects=False)
        if response.status_code in (404,410):
            if expected:
                return {'success':True,'snapshot':{'cancelled':True,'account_id':account},'url':url,'headers':headers,'provider':provider}
            return {'success':False,'error':'The original event could not be verified. Check the organizer calendar.'}
        if response.status_code!=200:
            return {'success':False,'error':'The connected account could not read this calendar event.'}
        event=response.json()
        if event.get('recurrence') or event.get('recurringEventId') or event.get('type')=='seriesMaster':
            return {'success':False,'error':'Recurring meetings must be managed in the organizer calendar.'}
        if expected and (event.get('isCancelled') or event.get('status')=='cancelled'):
            return {'success':True,'snapshot':{'cancelled':True,'account_id':account},'url':url,'headers':headers,'provider':provider}
        organizer=event.get('organizer') or {}
        email=(organizer.get('emailAddress') or {}).get('address') if provider=='microsoft' else organizer.get('email')
        owner=event.get('isOrganizer') is True if provider=='microsoft' else organizer.get('self') is True
        if not owner and str(email or '').casefold()!=saved['email'].casefold():
            return {'success':False,'error':'Only the original event organizer can change this interview.'}
        snapshot={'account_id':account,'cancelled':bool(event.get('isCancelled') or event.get('status')=='cancelled'),
            'start':iso(event['start']['dateTime']),'end':iso(event['end']['dateTime']),
            'subject':event.get('subject') if provider=='microsoft' else event.get('summary'),
            'location':(event.get('location') or {}).get('displayName','') if provider=='microsoft' else event.get('location') or '',
            'etag':event.get('@odata.etag') or event.get('etag')}
        return {'success':True,'snapshot':snapshot,'url':url,'headers':headers,'provider':provider}
    except Exception as exc:
        log.warning('Calendar read unavailable: %s',type(exc).__name__)
        return {'success':False,'error':'The calendar could not be checked. No change was sent.'}


def target_snapshot(target):
    start=datetime.fromisoformat(target['start_iso'])
    return {'start':iso(target['start_iso']),'end':(start+timedelta(minutes=int(target['duration']))).astimezone(timezone.utc).isoformat(),
            'subject':f"Interview: {target['candidate_name']} - {target.get('position') or 'Role'}",
            'location':target.get('location') or '', 'cancelled':False}


def change_event(row, action, target, user_id, db, before_mutation):
    inspected=inspect_event(row,user_id,db)
    if not inspected['success']:return inspected
    snapshot=inspected['snapshot']
    if snapshot['cancelled']:
        return {'success':action=='cancel','error':'This event has already been cancelled.'}
    headers={**inspected['headers'],'Content-Type':'application/json'}
    if snapshot.get('etag'):headers['If-Match']=snapshot['etag']
    before_mutation(snapshot)
    provider=inspected['provider']
    params={'sendUpdates':'all'} if provider=='google' else None
    try:
        if action=='cancel':
            response=requests.delete(inspected['url'],headers=headers,params=params,timeout=20,allow_redirects=False)
        else:
            desired=target_snapshot(target)
            body=({'subject':desired['subject'],'start':{'dateTime':desired['start'],'timeZone':'UTC'},
                   'end':{'dateTime':desired['end'],'timeZone':'UTC'},'location':{'displayName':target.get('location') or ''}}
                  if provider=='microsoft' else {'summary':desired['subject'],'start':{'dateTime':desired['start']},
                   'end':{'dateTime':desired['end']},'location':target.get('location') or ''})
            # Leave attendee lists, private notes and online-meeting bodies untouched.
            response=requests.patch(inspected['url'],headers=headers,params=params,json=body,timeout=20,allow_redirects=False)
        if 200<=response.status_code<300:return {'success':True}
        return {'success':False,'uncertain':response.status_code>=500,
            'error':'The calendar rejected this change. Reload the booking before trying again.' if response.status_code<500 else 'The calendar change could not be confirmed. Check the calendar before retrying.'}
    except Exception as exc:
        log.warning('Calendar change outcome unavailable: %s',type(exc).__name__)
        return {'success':False,'uncertain':True,'error':'The calendar change could not be confirmed. Check the calendar before retrying.'}
