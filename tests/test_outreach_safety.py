from pathlib import Path
from unittest.mock import MagicMock

import pytest
import main
from services import calendar_service as calendar, email_service as email
from services.outreach_validation import optional_id
from test_integration_workflows import api, interview_body
from test_candidate_state import state_db
from test_durable_search import queue_db


PRIVATE = 'synthetic-private-outreach-error'


@pytest.fixture
def outreach(api, monkeypatch):
    client, db = api
    monkeypatch.setattr(main.limiter, 'enabled', False)
    db.list_email_templates.return_value = [{'id': 1, 'subject': 'Interview for {{ candidate_name }}',
                                           'body': '<p>{{ meeting_join_url }}</p>', 'kind': 'interview_invite'}]
    db.get_candidate_states.return_value = [{'search_result_id': 23}]
    meeting = MagicMock(return_value={'success': True, 'provider': 'teams',
        'join_url': 'https://teams.microsoft.com/synthetic', 'event_id': 'synthetic-event'})
    sender = MagicMock(return_value={'success': True, 'provider': 'microsoft', 'error': None})
    monkeypatch.setattr(calendar, 'create_meeting', meeting)
    monkeypatch.setattr(email, 'send_email', sender)
    return client, db, meeting, sender


def mail_body(**changes):
    return {'candidate_name': 'Synthetic', 'candidate_email': 'fictional@example.invalid',
            'raw_subject': 'Hello {{ candidate_name }}', 'raw_body': '<p>Synthetic</p>', **changes}


@pytest.mark.parametrize('changes', [
    {'interviewer': []}, {'interviewer': 'x' * 501}, {'interview_type': 'unsupported'},
    {'interview_type': {}}, {'duration': True}, {'duration': 0}, {'duration': 1.5},
    {'duration': 60.0}, {'duration': '1e2'}, {'duration': '9' * 5000},
    {'candidate_email': 'a' * 250 + '@example.invalid'}, {'custom_message': 'x' * 8193},
    {'search_result_id': True}, {'search_result_id': -1}, {'search_result_id': 'invalid'},
    {'search_result_id': []}, {'search_result_id': 2147483648},
    {'email_template_id': 'invalid'}, {'email_prefer': 'misspelled-provider'},
])
def test_bad_schedule_inputs_never_reach_provider_or_write(outreach, changes):
    client, db, meeting, sender = outreach
    response = client.post('/api/schedule-interview', json=interview_body(**changes))
    assert response.status_code == 422
    meeting.assert_not_called()
    sender.assert_not_called()
    db.schedule_interview.assert_not_called()
    db.log_email_sent.assert_not_called()


@pytest.mark.parametrize('changes', [
    {'candidate_email': []}, {'candidate_email': 'not-an-email'},
    {'candidate_email': 'a@example.invalid\r\nBcc: victim@example.invalid'},
    {'candidate_email': 'x' * 321}, {'candidate_name': 'x' * 501},
    {'prefer': []}, {'prefer': 'misspelled-provider'}, {'kind': 'x' * 41},
    {'template_id': True}, {'search_result_id': {}}, {'search_result_id': '9' * 5000},
    {'custom_message': 'x' * 8193}, {'interview_location': []},
])
def test_bad_email_inputs_never_send_or_log(outreach, changes):
    client, db, _meeting, sender = outreach
    response = client.post('/api/send-candidate-email', json=mail_body(**changes))
    assert response.status_code == 422
    sender.assert_not_called()
    db.log_email_sent.assert_not_called()


@pytest.mark.parametrize('endpoint,body', [('/api/schedule-interview', interview_body),
                                       ('/api/send-candidate-email', mail_body)])
def test_outreach_links_fail_closed_outside_workspace(outreach, endpoint, body):
    client, db, meeting, sender = outreach
    db.get_candidate_states.return_value = []
    response = client.post(endpoint, json=body(search_result_id=23))
    assert response.status_code == 404
    db.get_candidate_states.assert_called_once_with([23], 1)
    meeting.assert_not_called()
    sender.assert_not_called()
    db.schedule_interview.assert_not_called()
    db.log_email_sent.assert_not_called()


def test_invalid_or_unsafe_invitation_template_is_rejected_before_calendar_creation(outreach):
    client, db, meeting, sender = outreach
    db.get_email_template.return_value = None
    response = client.post('/api/schedule-interview', json=interview_body(email_template_id=99))
    assert response.status_code == 404
    db.get_email_template.return_value = {'subject': 'Synthetic', 'body': '{{ range(5) }}'}
    response = client.post('/api/schedule-interview', json=interview_body(email_template_id=99))
    assert response.status_code == 422
    meeting.assert_not_called()
    sender.assert_not_called()


@pytest.mark.parametrize('failure', ['no_id', 'exception'])
def test_accepted_email_stays_accepted_when_audit_cannot_be_recorded(outreach, caplog, failure):
    client, db, _meeting, sender = outreach
    if failure == 'exception':
        db.log_email_sent.side_effect = RuntimeError(PRIVATE)
    else:
        db.log_email_sent.return_value = None
    response = client.post('/api/send-candidate-email', json=mail_body())
    assert response.status_code == 200 and response.json()['success']
    assert 'audit_warning' in response.json()
    assert PRIVATE not in response.text + caplog.text
    sender.assert_called_once()


def test_invitation_retains_accepted_result_when_audit_fails(outreach):
    client, db, _meeting, sender = outreach
    db.log_email_sent.side_effect = RuntimeError(PRIVATE)
    response = client.post('/api/schedule-interview', json=interview_body())
    assert response.status_code == 200 and response.json()['success']
    assert response.json()['email']['success'] is True
    assert response.json()['email']['audit_warning']
    assert PRIVATE not in response.text
    sender.assert_called_once()


def test_unknown_email_outcome_is_preserved_and_not_logged_as_definite_failure(outreach):
    client, db, _meeting, sender = outreach
    sender.return_value = {'success': False, 'provider': 'microsoft', 'delivery_unknown': True,
                           'error': 'Check Sent Items before retrying.'}
    response = client.post('/api/send-candidate-email', json=mail_body())
    assert response.status_code == 502 and response.json()['delivery_unknown'] is True
    assert db.log_email_sent.call_args.kwargs['status'] == 'unknown'
    sender.assert_called_once()


def test_calendar_creation_followed_by_save_failure_returns_honest_partial_outcome(outreach, caplog):
    client, db, meeting, sender = outreach
    db.schedule_interview.side_effect = RuntimeError(PRIVATE)
    response = client.post('/api/schedule-interview', json=interview_body())
    assert response.status_code == 503
    data = response.json()
    assert data['success'] is False and data['schedule_saved'] is None and data['persistence_unknown'] is True
    assert data['meeting']['event_id'] == 'synthetic-event'
    assert 'calendar event may already exist' in data['detail']
    assert PRIVATE not in response.text + caplog.text
    meeting.assert_called_once()
    sender.assert_not_called()


def test_unexpected_mail_exception_is_redacted_and_treated_as_unknown(outreach, caplog):
    client, _db, _meeting, sender = outreach
    sender.side_effect = RuntimeError(PRIVATE)
    response = client.post('/api/send-candidate-email', json=mail_body())
    assert response.status_code == 502 and response.json()['delivery_unknown'] is True
    assert PRIVATE not in response.text + caplog.text
    sender.assert_called_once()


def test_minimal_legacy_schedule_gets_complete_validated_defaults(outreach):
    client, db, meeting, sender = outreach
    response = client.post('/api/schedule-interview', json={
        'candidate_name': 'Synthetic', 'interview_date': '2030-01-02'})
    assert response.status_code == 200
    saved = db.schedule_interview.call_args.args[0]
    assert saved['duration'] == 30 and saved['interview_time'] == '09:00'
    assert saved['interview_type'] == 'video'
    assert all(saved[field] == '' for field in ('candidate_email', 'location', 'interviewer', 'notes'))
    meeting.assert_not_called()
    sender.assert_not_called()


def test_long_generated_join_url_is_preserved_in_location_and_dedicated_field(outreach):
    client, db, meeting, _sender = outreach
    url = 'https://teams.microsoft.com/' + 'x' * 1000
    meeting.return_value = {'success': True, 'provider': 'teams', 'join_url': url, 'event_id': 'synthetic'}
    assert client.post('/api/schedule-interview', json=interview_body()).status_code == 200
    saved = db.schedule_interview.call_args.args[0]
    assert saved['location'] == saved['meeting_join_url'] == url


@pytest.mark.parametrize('value,expected', [(None, None), ('', None), ('23', 23), (23, 23), (' 23 ', 23)])
def test_optional_ids_have_one_canonical_form(value, expected):
    assert optional_id(value, 'record') == expected


@pytest.fixture
def outreach_db(state_db, monkeypatch):
    db, ids = state_db
    with db.get_cursor() as (cur, _):
        cur.execute('''CREATE TABLE scheduled_interviews (
            id SERIAL PRIMARY KEY, candidate_name VARCHAR(500), candidate_email VARCHAR(255),
            interview_type VARCHAR(100), interview_date DATE, interview_time TIME,
            duration_minutes INTEGER, location VARCHAR(500), interviewer VARCHAR(500), notes TEXT,
            created_by TEXT, company_id INTEGER, status TEXT, meeting_provider TEXT,
            meeting_join_url TEXT, meeting_event_id TEXT, search_result_id INTEGER,
            job_application_id BIGINT);
            CREATE TABLE interview_emails_sent (id SERIAL PRIMARY KEY, company_id INTEGER,
            sent_by_user_id INTEGER, recipient_email TEXT, candidate_name TEXT, kind TEXT,
            subject TEXT, body TEXT, provider TEXT, status TEXT, error_message TEXT,
            search_result_id INTEGER, interview_id INTEGER, job_application_id BIGINT);''')
        migration = Path('deploy/vps/migrations/20261105_outreach_location.sql').read_text()
        cur.execute(migration)
        cur.execute(Path('deploy/vps/migrations/20261105_workspace_lifecycle.sql').read_text())
    monkeypatch.setattr(db, 'ensure_integrations_tables', lambda: None)
    monkeypatch.setattr(db, 'log_audit', lambda *a: None)
    return db, ids


def db_interview(result_id, company=1, location='Synthetic'):
    return {'candidate_name': 'Synthetic', 'candidate_email': 'fictional@example.invalid',
        'interview_type': 'video', 'interview_date': '2030-01-02', 'interview_time': '10:00',
        'duration': 30, 'location': location, 'interviewer': 'Synthetic', 'notes': '',
        'created_by': 7, 'company_id': company, 'search_result_id': result_id}


def test_postgres_outreach_links_are_tenant_scoped_and_long_urls_round_trip(outreach_db):
    db, ids = outreach_db
    with pytest.raises(ValueError):
        db.schedule_interview(db_interview(ids[1]))
    assert db.log_email_sent(company_id=1, sent_by_user_id=7, recipient_email='fictional@example.invalid',
        candidate_name='Synthetic', kind='custom', subject='Synthetic', body='Synthetic',
        provider='microsoft', search_result_id=ids[1]) is None
    location = 'https://teams.microsoft.com/' + 'x' * 1900
    identifier = db.schedule_interview(db_interview(ids[0], location=location))
    with db.get_cursor() as (cur, _):
        cur.execute('SELECT location FROM scheduled_interviews WHERE id=%s', (identifier,))
        assert cur.fetchone()['location'] == location
        cur.execute('SELECT count(*) AS n FROM interview_emails_sent')
        assert cur.fetchone()['n'] == 0


def test_postgres_booking_is_committed_before_secondary_audit_connection(outreach_db, monkeypatch):
    db, ids = outreach_db
    observed = []
    def audit(*args):
        with db.get_cursor() as (cur, _):
            cur.execute('SELECT id FROM scheduled_interviews WHERE id=%s', (args[4],))
            observed.append(cur.fetchone()['id'])
    monkeypatch.setattr(db, 'log_audit', audit)
    identifier = db.schedule_interview(db_interview(ids[0]))
    assert observed == [identifier]
