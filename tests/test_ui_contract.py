import pytest
import main
from unittest.mock import patch
from test_integration_workflows import api


@pytest.mark.parametrize('search_limit,email_limit', [(7, 23), (1, 1), (25, 50)])
def test_authenticated_page_publishes_the_actual_backend_limits(api, monkeypatch, search_limit, email_limit):
    client, _db = api
    monkeypatch.setattr(main, 'MAX_HR_SCORECARD_RESULTS', search_limit)
    monkeypatch.setattr(main, 'MAX_EMAIL_SCRAPE_LIMIT', email_limit)
    with patch.object(main.templates, 'TemplateResponse', wraps=main.templates.TemplateResponse) as render:
        response = client.get('/')
    assert response.status_code == 200
    assert render.call_args.args[2]['ui_limits'] == {'search_results': search_limit, 'email_scan': email_limit}
    assert 'window.SMART_HR_LIMITS =' in response.text


def test_admin_ui_asset_is_versioned_and_served(api):
    client, _db = api
    assert main._ASSET_VERSIONS.get('dashboard_ui_js') not in (None, '', '0')
    response = client.get('/static/js/dashboard-ui.js')
    assert response.status_code == 200
    assert 'window.AdminUI = {openDialog, closeDialog}' in response.text


def test_recruiter_keeps_original_application_logo(api):
    client, _db = api
    response = client.get('/')
    assert response.status_code == 200
    assert 'src="/static/img/ai-logo.png" alt="AI Agent Recruiter"' in response.text
    assert 'Your AI Agent for Seamless Recruitment' in response.text
    assert 'efforts-solutions-logo.png' not in response.text
