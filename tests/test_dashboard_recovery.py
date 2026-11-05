import asyncio
from contextlib import contextmanager
import time
from unittest.mock import MagicMock

import pytest
import main
from database import DatabaseManager
from test_integration_workflows import api


PRIVATE = 'synthetic-private-schedule-query-marker'


@pytest.mark.parametrize('failed_query', [1, 2])
def test_database_schedule_failures_are_not_successful_empty_results(caplog, failed_query):
    database = DatabaseManager.__new__(DatabaseManager)
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    cursor.execute.side_effect = [RuntimeError(PRIVATE)] if failed_query == 1 else [None, RuntimeError(PRIVATE)]
    @contextmanager
    def get_cursor():
        yield cursor, None
    database.get_cursor = get_cursor
    with pytest.raises(RuntimeError, match='Upcoming schedule unavailable') as error:
        database.get_upcoming_events(7, 1)
    assert PRIVATE not in str(error.value) + caplog.text


def test_upcoming_api_returns_unavailable_instead_of_false_empty_state(api, caplog):
    client, database = api
    database.get_upcoming_events.side_effect = RuntimeError(PRIVATE)
    response = client.get('/api/upcoming-events')
    assert response.status_code == 503
    assert response.json() == {'detail': 'Upcoming schedule is temporarily unavailable'}
    assert PRIVATE not in response.text + caplog.text


def test_upcoming_database_work_does_not_block_the_api_event_loop(monkeypatch):
    database = MagicMock()
    database.get_upcoming_events.side_effect = lambda *args: (time.sleep(.05) or [])
    monkeypatch.setattr(main, 'get_db_manager', lambda: database)
    async def scenario():
        task = asyncio.create_task(main.get_upcoming_events({'id': 7, 'company': {'company_id': 1}}))
        await asyncio.sleep(.005)
        assert not task.done()
        assert (await task) == {'success': True, 'events': []}
    asyncio.run(scenario())
