import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

import main
from services import task_auth
from services.interview_time import utc_start


def test_interview_time_respects_browser_timezone():
    start, duration = utc_start({"interview_date": "2026-11-10", "interview_time": "10:00", "time_zone": "Asia/Dubai", "duration": 45})
    assert start == "2026-11-10T06:00:00+00:00"
    assert duration == 45
    assert utc_start({"interview_date": "2026-11-10", "interview_time": "10:00"})[0] == "2026-11-10T10:00:00+00:00"


@pytest.mark.parametrize("change", [{"interview_date": "bad"}, {"interview_time": "25:99"},
    {"time_zone": "Invalid/Zone"}, {"duration": -5}, {"duration": 999999},
    {"interview_date": "2026-03-08", "interview_time": "02:30", "time_zone": "America/New_York"}])
def test_invalid_interview_time_rejected_before_side_effects(change):
    data = {"interview_date": "2026-11-10", "interview_time": "10:00"}
    with pytest.raises(ValueError):
        utc_start({**data, **change})


def test_internal_task_requires_signature_even_behind_proxy():
    with patch.object(main, "get_db_manager") as db:
        response = TestClient(main.app).post('/api/process-hr-scorecard-task', json={"task_id": "fake"},
                                             headers={"X-Internal-Task": "1"})
    assert response.status_code == 401
    db.assert_not_called()


def test_internal_task_signature_binding_and_expiry(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-task-secret-" * 3)
    body, headers = task_auth.encode({"task_id": "synthetic"})
    task_auth.verify(body, Headers(headers))
    with pytest.raises(main.HTTPException):
        task_auth.verify(body + b" ", Headers(headers))
    with patch.object(task_auth.time, "time", return_value=task_auth.time.time() + 301):
        with pytest.raises(main.HTTPException):
            task_auth.verify(body, Headers(headers))


def test_duplicate_task_is_not_reprocessed(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-task-secret-" * 3)
    body, headers = task_auth.encode({"task_id": "synthetic", "query": "QA", "result_count": 10,
                                      "user_data": {"id": 7, "user_type": "super_admin"}})
    db = MagicMock()
    db.claim_hr_scorecard_task.return_value = None
    db.get_task_status.return_value = {"status": "completed"}
    with patch.object(main, "get_db_manager", return_value=db), patch.object(main, "gemini_client") as llm:
        response = TestClient(main.app).post('/api/process-hr-scorecard-task', content=body, headers=headers)
    assert response.status_code == 200 and response.json()["skipped"]
    llm.assert_not_called()
