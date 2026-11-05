from unittest.mock import MagicMock

import pytest

from services import calendar_changes as calendar


@pytest.fixture
def provider(monkeypatch):
    db=MagicMock()
    db.get_oauth_token.return_value={'email':'fixture@example.invalid','extra':{'account_id':'stable-account'}}
    monkeypatch.setattr(calendar,'_get_valid_token',lambda *args,**kwargs:('synthetic-access','me'))
    response=MagicMock(status_code=200)
    event={'id':'event/one','subject':'Synthetic','summary':'Synthetic','isOrganizer':True,
        'organizer':{'email':'fixture@example.invalid','self':True},
        'start':{'dateTime':'2030-01-02T06:00:00Z'},'end':{'dateTime':'2030-01-02T07:00:00Z'},
        '@odata.etag':'synthetic-etag','etag':'synthetic-etag'}
    response.json.return_value=event
    get=MagicMock(return_value=response);patch=MagicMock(return_value=MagicMock(status_code=200));delete=MagicMock(return_value=MagicMock(status_code=204))
    monkeypatch.setattr(calendar.requests,'get',get);monkeypatch.setattr(calendar.requests,'patch',patch);monkeypatch.setattr(calendar.requests,'delete',delete)
    row={'meeting_provider':'teams','meeting_event_id':'event/one','calendar_account_id':'stable-account'}
    target={'candidate_name':'Fixture','position':'Engineer','start_iso':'2030-01-03T06:00:00+00:00','duration':45,'location':'Office B','notes':'Must stay private'}
    return db,event,response,get,patch,delete,row,target


@pytest.mark.parametrize('provider_name',['teams','meet'])
def test_update_preserves_meeting_body_attendees_and_private_notes(provider,provider_name):
    db,event,response,get,patch,delete,row,target=provider;row['meeting_provider']=provider_name
    before=MagicMock()
    result=calendar.change_event(row,'edit',target,7,db,before)
    assert result['success']
    before.assert_called_once();patch.assert_called_once();delete.assert_not_called()
    body=patch.call_args.kwargs['json']
    assert all(field not in body for field in ('body','attendees','description','conferenceData','notes'))
    assert patch.call_args.kwargs['headers']['If-Match']=='synthetic-etag'
    assert get.call_args.args[0].endswith('event%2Fone')
    if provider_name=='meet':assert patch.call_args.kwargs['params']=={'sendUpdates':'all'}


@pytest.mark.parametrize('provider_name',['teams','meet'])
def test_calendar_cancellation_uses_existing_event_and_notifies_guests(provider,provider_name):
    db,event,response,get,patch,delete,row,target=provider;row['meeting_provider']=provider_name
    assert calendar.change_event(row,'cancel',target,7,db,MagicMock())['success']
    assert delete.call_args.args[0].endswith('event%2Fone')
    assert delete.call_args.kwargs['allow_redirects'] is False
    if provider_name=='meet':assert delete.call_args.kwargs['params']=={'sendUpdates':'all'}
    patch.assert_not_called()


def test_reconnected_different_account_cannot_touch_original_calendar(provider):
    db,event,response,get,patch,delete,row,target=provider
    row['calendar_account_id']='different-account'
    assert not calendar.change_event(row,'cancel',target,7,db,MagicMock())['success']
    get.assert_not_called();patch.assert_not_called();delete.assert_not_called()


@pytest.mark.parametrize('changes',[{'isOrganizer':False,'organizer':{'emailAddress':{'address':'other@example.invalid'}}},
    {'type':'seriesMaster'},{'recurrence':['RRULE:FREQ=WEEKLY']}])
def test_foreign_or_recurring_events_fail_before_mutation(provider,changes):
    db,event,response,get,patch,delete,row,target=provider;event.update(changes)
    assert not calendar.change_event(row,'cancel',target,7,db,MagicMock())['success']
    patch.assert_not_called();delete.assert_not_called()


def test_transport_timeout_is_uncertain_and_never_retried(provider):
    db,event,response,get,patch,delete,row,target=provider
    delete.side_effect=TimeoutError('synthetic-private-marker')
    result=calendar.change_event(row,'cancel',target,7,db,MagicMock())
    assert not result['success'] and result['uncertain']
    assert delete.call_count==1 and 'synthetic-private-marker' not in str(result)


def test_failure_to_persist_before_snapshot_never_sends_change(provider):
    db,event,response,get,patch,delete,row,target=provider
    with pytest.raises(RuntimeError):calendar.change_event(row,'cancel',target,7,db,MagicMock(side_effect=RuntimeError('DB unavailable')))
    patch.assert_not_called();delete.assert_not_called()


@pytest.mark.parametrize('provider_name',['teams','meet'])
def test_reconciliation_snapshot_includes_location_and_active_status(provider,provider_name):
    db,event,response,get,patch,delete,row,target=provider
    row['meeting_provider']=provider_name
    event['location']={'displayName':'Office B'} if provider_name=='teams' else 'Office B'
    snapshot=calendar.inspect_event(row,7,db)['snapshot']
    assert snapshot['location']=='Office B' and snapshot['cancelled'] is False
    desired=calendar.target_snapshot(target)
    assert desired['location']=='Office B' and desired['cancelled'] is False
