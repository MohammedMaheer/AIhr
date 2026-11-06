"""Current dashboard totals must match their lists, including older decisions."""
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

import main
from test_candidate_state import state_db
from test_durable_search import queue_db


STATUSES = ('selected', 'rejected', 'shortlisted', 'interviewed')


@pytest.mark.parametrize('status', STATUSES)
def test_old_active_status_is_counted_without_rewriting_its_timestamp(state_db, status):
    db, ids = state_db
    db.save_candidate_action(ids[0], 'Fictional', status, user_id='7', company_id=1)
    with db.get_cursor() as (cursor, _):
        cursor.execute("UPDATE candidate_actions SET created_at=NOW()-interval '400 days',updated_at=NOW()-interval '200 days' WHERE search_result_id=%s", (ids[0],))
    counts = db.get_candidate_action_stats(7, 1)
    assert counts[status] == 1
    for choice in STATUSES:
        assert counts[choice] == len(db.get_candidates_by_action(7, choice, 1))
    with db.get_cursor() as (cursor, _):
        cursor.execute("SELECT created_at<NOW()-interval '365 days' AS old,action_status FROM candidate_actions WHERE search_result_id=%s", (ids[0],))
        assert dict(cursor.fetchone()) == {'old': True, 'action_status': True}


def test_inactive_previous_status_does_not_inflate_dashboard_totals(state_db):
    db, ids = state_db
    db.save_candidate_action(ids[0], 'Fictional', 'selected', user_id='7', company_id=1)
    db.save_candidate_action(ids[0], 'Fictional', 'shortlisted', user_id='7', company_id=1)
    counts = db.get_candidate_action_stats(7, 1)
    assert counts['selected'] == 0 and counts['shortlisted'] == 1


def test_counts_keep_user_and_canonical_workspace_scope(state_db):
    db, ids = state_db
    db.save_candidate_action(ids[0], 'First', 'selected', user_id='7', company_id=1)
    db.save_candidate_action(ids[1], 'Second', 'selected', user_id='7', company_id=2)
    with db.get_cursor() as (cursor, _):
        cursor.execute('UPDATE search_results SET company_id=2 WHERE id=%s', (ids[0],))
    assert db.get_candidate_action_stats(7, 1)['selected'] == 1
    assert len(db.get_candidates_by_action(7, 'selected', 1)) == 1
    assert db.get_candidate_action_stats(8, 1)['selected'] == 0
    assert db.get_candidate_action_stats(7, 2)['selected'] == 1
    assert len(db.get_candidates_by_action(7, 'selected', 2)) == 1


def test_legacy_unowned_status_remains_workspace_scoped(state_db):
    db, ids = state_db
    with db.get_cursor() as (cursor, _):
        cursor.execute("INSERT INTO candidate_actions(search_result_id,action_type,action_status,created_at) VALUES (%s,'shortlisted',TRUE,NOW()-interval '400 days')", (ids[1],))
    assert db.get_candidate_action_stats(7, 1)['shortlisted'] == 0
    assert db.get_candidate_action_stats(7, 2)['shortlisted'] == 1
    assert len(db.get_candidates_by_action(7, 'shortlisted', 2)) == 1


def test_case_variants_are_aggregated_like_status_lists(state_db):
    db, ids = state_db
    with db.get_cursor() as (cursor, _):
        cursor.execute('SELECT search_id FROM search_results WHERE id=%s', (ids[0],))
        search_id = cursor.fetchone()['search_id']
        cursor.execute("INSERT INTO search_results(search_id,candidate_name,company_id,file_path) VALUES (%s,'Other fictional',1,'other.txt') RETURNING id", (search_id,))
        other = cursor.fetchone()['id']
        cursor.execute("INSERT INTO candidate_actions(search_result_id,action_type,action_status,user_id) VALUES (%s,'Selected',TRUE,'7'),(%s,'selected',TRUE,'7')", (ids[0], other))
    assert db.get_candidate_action_stats(7, 1)['selected'] == 2
    assert len(db.get_candidates_by_action(7, 'selected', 1)) == 2


def test_dashboard_http_totals_equal_clickthrough_lists_for_old_status(state_db, monkeypatch):
    db, ids = state_db
    db.save_candidate_action(ids[0], 'Fictional', 'selected', user_id='7', company_id=1)
    with db.get_cursor() as (cursor, _):
        cursor.execute("UPDATE candidate_actions SET created_at=NOW()-interval '400 days'")
        cursor.execute('CREATE TABLE resume_uploads(company_id INTEGER)')
    monkeypatch.setattr(db, 'get_company_stats', lambda company_id: {'max_resumes': 100, 'total_resumes': 0})
    previous = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[main.require_auth] = lambda: {'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': 1}}
    try:
        with patch.object(main, 'get_db_manager', return_value=db):
            client = TestClient(main.app)
            response = client.get('/api/dashboard-stats')
            assert response.status_code == 200
            counts = response.json()['candidate_stats']
            assert counts['selected'] == 1
            for status in STATUSES:
                listed = client.get('/api/candidates-by-status', params={'status': status})
                assert listed.status_code == 200
                assert listed.json()['count'] == counts[status]
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous)
