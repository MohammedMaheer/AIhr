from copy import deepcopy

import pytest
from lxml import html

from services.email_branding import branded_html, display_time
from services.email_service import DEFAULT_TEMPLATES, build_default_context, render_candidate_email
from test_outreach_safety import outreach, mail_body
from test_integration_workflows import api, interview_body


def test_legacy_default_invite_gets_logo_readable_time_and_short_join_button():
    template = next(t for t in DEFAULT_TEMPLATES if t['kind'] == 'interview_invite')
    before = deepcopy(template)
    ctx = build_default_context(candidate_name='Fictional Candidate', candidate_email='fixture@example.invalid',
        position='Backend Engineer', recruiter_name='Super Admin', interview_date='2030-01-02',
        interview_time='10:00', time_zone='Asia/Dubai', duration_minutes=60,
        meeting_join_url='https://teams.microsoft.com/long-synthetic-meeting?context=example')
    subject, body = render_candidate_email(template['subject'], template['body'], ctx)
    document = html.fromstring(body)
    assert subject == 'Interview invitation: Backend Engineer at Efforts Solutions'
    assert 'Efforts Solutions' in document.text_content()
    assert document.xpath('//img[@alt="Efforts Solutions"]')
    assert '2 January 2030' in document.text_content()
    assert '10:00 AM (Asia/Dubai, UTC+04:00)' in document.text_content()
    assert '60 minutes' in document.text_content()
    assert 'Recruitment Team' in document.text_content()
    assert 'our company' not in document.text_content()
    assert ctx['meeting_join_url'] not in document.text_content()
    assert document.xpath('//a[text()="Join interview"]')[0].get('href') == ctx['meeting_join_url']
    assert template == before, 'Existing stored or module templates must not be overwritten'


def test_custom_content_is_preserved_but_active_html_and_links_are_removed():
    ctx=build_default_context(candidate_name='<img onerror=bad()>', candidate_email='fixture@example.invalid')
    subject, body = render_candidate_email('Custom', '<p>Custom <strong>{{ candidate_name }}</strong></p><script>bad()</script><a href="javascript:bad()">Unsafe</a>',ctx)
    tree=html.fromstring(body)
    assert subject=='Custom' and 'Custom' in tree.text_content()
    assert '<img onerror=bad()>' in tree.text_content()
    assert not tree.xpath('//script|//*[@onerror]|//a[starts-with(@href,"javascript:")]')


@pytest.mark.parametrize('body',['','<script>bad()</script>','<html><head><style>p{color:red}</style></head></html>'])
def test_empty_or_active_only_body_is_rejected(body):
    with pytest.raises(ValueError):branded_html(body)


def test_timezone_display_matches_offset_on_date():
    assert 'UTC+05:30' in display_time('2030-01-02','10:00','Asia/Kolkata')[1]
    assert 'UTC-05:00' in display_time('2030-01-02','10:00','America/New_York')[1]
    assert display_time('2030-01-02', 'T10:00', 'UTC') == display_time('2030-01-02', '10:00', 'UTC')


@pytest.mark.parametrize('changes',[
    {'position':''},{'interview_date':'2000-01-02'},{'company':['bad']},
    {'position':'Backend\nBcc: victim@example.invalid'}, {'time_zone':'Invalid/Zone'},
])
def test_popup_schedule_validation_happens_before_provider_side_effects(outreach, changes):
    client,db,meeting,sender=outreach
    response=client.post('/api/schedule-interview',json=interview_body(**changes))
    assert response.status_code==422
    meeting.assert_not_called();sender.assert_not_called();db.schedule_interview.assert_not_called()


@pytest.mark.parametrize('changes',[
    {'interview_date':'tomorrow'}, {'interview_time':'bad'}, {'time_zone':'Bad/Zone'},
    {'company':'x'*256}, {'meeting_join_url':'javascript:alert(1)'},
    {'meeting_join_url':'https://user:password@example.invalid/meeting'},
    {'meeting_join_url':'http://example.invalid/meeting'},
])
def test_bad_email_context_is_rejected_before_sending(outreach, changes):
    client,db,_meeting,sender=outreach
    assert client.post('/api/send-candidate-email',json=mail_body(**changes)).status_code==422
    sender.assert_not_called();db.log_email_sent.assert_not_called()


def test_render_failure_is_known_unsent_not_unknown_delivery(outreach):
    client,db,_meeting,sender=outreach
    db.list_email_templates.return_value=[{'subject':'Synthetic','body':'<script>bad()</script>','kind':'interview_invite'}]
    response=client.post('/api/schedule-interview',json=interview_body())
    assert response.status_code==200
    assert response.json()['email']['skipped'] is True
    assert not response.json()['email'].get('delivery_unknown')
    sender.assert_not_called()
