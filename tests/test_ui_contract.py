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


def test_charts_are_local_integrity_checked_and_unused_script_origin_removed(api):
    import base64
    import hashlib
    from html.parser import HTMLParser
    client,_db=api
    response=client.get('/')
    class Scripts(HTMLParser):
        def __init__(self):super().__init__();self.scripts=[]
        def handle_starttag(self,tag,attrs):
            if tag=='script':self.scripts.append(dict(attrs))
    parser=Scripts();parser.feed(response.text)
    script=next(s for s in parser.scripts if '/chartjs/' in s.get('src',''))
    asset=client.get(script['src'])
    assert asset.status_code==200
    assert script['integrity']=='sha384-'+base64.b64encode(hashlib.sha384(asset.content).digest()).decode()
    policy=response.headers['Content-Security-Policy']
    scripts=next(item.strip() for item in policy.split(';') if item.strip().startswith('script-src '))
    assert 'cdn.jsdelivr.net' not in scripts
