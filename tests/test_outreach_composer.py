from unittest.mock import MagicMock, patch

import pytest
from lxml import html

from services.email_branding import render_plain_message
from services.email_service import send_email
from test_integration_workflows import api
from test_outreach_safety import outreach


def payload(**changes):
    return {'candidate_name': 'Fictional Candidate', 'candidate_email': 'fixture@example.invalid',
            'position': 'Fictional Engineer', 'company': 'Efforts Solutions',
            'message_subject': 'Fictional Engineer - request for details',
            'message_body': 'Hi Fictional Candidate,\n\nPlease share your availability.\n\nRegards,\nRecruitment Team',
            'prefer': 'microsoft', **changes}


@pytest.mark.parametrize('change', [{'message_subject': ''}, {'message_subject': ' \t'},
    {'message_subject': 'Subject\r\nBcc: bad@example.invalid'}, {'message_subject': 'x'*999},
    {'message_body': ''}, {'message_body': '  '}, {'message_body': 'x'*32769},
    {'candidate_email': 'invalid'}, {'message_body': ['not', 'text']}])
@pytest.mark.parametrize('endpoint', ['/api/preview-candidate-email', '/api/send-candidate-email'])
def test_bad_composer_input_never_sends_or_records(outreach, change, endpoint):
    client, db, meeting, sender = outreach
    assert client.post(endpoint, json=payload(**change)).status_code == 422
    sender.assert_not_called()
    meeting.assert_not_called()
    db.log_email_sent.assert_not_called()


def test_preview_and_send_have_identical_branding_without_template_interpretation(outreach):
    client, db, meeting, sender = outreach
    data = payload(message_body='Literal {{ recruiter_email }}\n\n<script>not executable</script>')
    preview = client.post('/api/preview-candidate-email', json=data)
    assert preview.status_code == 200
    sender.assert_not_called()
    db.log_email_sent.assert_not_called()
    tree = html.fromstring(preview.json()['body_html'])
    assert not tree.xpath('//script')
    assert 'Literal {{ recruiter_email }}' in tree.text_content()
    assert tree.xpath('//img[@alt="Efforts Solutions"]')
    response = client.post('/api/send-candidate-email', json=data)
    assert response.status_code == 200 and response.json()['success']
    assert sender.call_args.kwargs['body_html'] == preview.json()['body_html']
    assert sender.call_args.kwargs['strict_transport'] is True
    meeting.assert_not_called()


def test_preview_rejects_foreign_candidate_before_rendering(outreach):
    client, db, _meeting, sender = outreach
    db.get_candidate_states.return_value = []
    assert client.post('/api/preview-candidate-email', json=payload(search_result_id=23)).status_code == 404
    sender.assert_not_called()
    db.log_email_sent.assert_not_called()


def test_explicit_composer_mailbox_does_not_fall_back_to_smtp():
    with patch('services.calendar_service._get_valid_token', return_value=('synthetic', 'me')), \
         patch('services.email_service._send_via_graph', return_value={'success':False,'error':'Synthetic rejection'}), \
         patch('services.email_service._send_via_smtp') as smtp:
        result = send_email(to='fixture@example.invalid', subject='Synthetic', body_html='<p>Fixture</p>',
            prefer='microsoft', strict_transport=True, organizer_user_id=7, db=MagicMock())
    assert result['success'] is False
    smtp.assert_not_called()


def test_plain_email_subject_and_lines_are_preserved():
    subject, body = render_plain_message('R&D role', 'Hello,\n\n- Python\n- SQL\n\nRegards,\nExample')
    assert subject == 'R&D role'
    assert '- Python<br>- SQL' in body
