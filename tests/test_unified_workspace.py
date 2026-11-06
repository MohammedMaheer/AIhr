from unittest.mock import MagicMock

import pytest
import main
from test_integration_workflows import api


@pytest.mark.parametrize('role', ['super_admin', 'tenant_admin', 'tenant_user'])
def test_old_dashboard_route_always_returns_to_recruiter_workspace(api, role):
    client, db = api
    db.verify_session.return_value['user_type'] = role
    response = client.get('/dashboard?integration=microsoft&status=connected', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == '/?integration=microsoft&status=connected'
    assert 'Dashboard Overview' not in response.text


@pytest.mark.parametrize('role', ['super_admin', 'tenant_admin', 'tenant_user'])
def test_login_uses_one_workspace_for_every_role(api, role):
    client, db = api
    db.authenticate_user.return_value = {'id': 7, 'user_type': role}
    db.create_session.return_value = 'synthetic-new-session'
    response = client.post('/api/login', data={'email':'fictional@example.invalid', 'password':'synthetic-password'})
    assert response.status_code == 200
    assert response.json()['redirect'] == '/'


def test_super_admin_can_update_monthly_search_limit(api):
    client, db = api
    db.verify_session.return_value['user_type'] = 'super_admin'
    cursor = MagicMock()
    cursor.rowcount = 1
    db.get_cursor.return_value.__enter__.return_value = (cursor, None)
    response = client.put('/api/companies/1', data={'max_searches': 1234})
    assert response.status_code == 200
    query, values = cursor.execute.call_args.args
    assert 'max_searches = %s' in query
    assert values == [1234, 1]


@pytest.mark.parametrize('limit', [0, -1, 1000000001])
def test_monthly_search_limits_require_positive_bounded_values(api, limit):
    client, db = api
    db.verify_session.return_value['user_type'] = 'super_admin'
    assert client.put('/api/companies/1', data={'max_searches':limit}).status_code == 422
    db.get_cursor.assert_not_called()


@pytest.mark.parametrize('role', ['tenant_admin', 'tenant_user'])
def test_unified_navigation_does_not_grant_company_administration(api, role):
    client, db = api
    db.verify_session.return_value['user_type'] = role
    assert client.put('/api/companies/1', data={'max_searches': 1234}).status_code == 403
    db.get_cursor.assert_not_called()
