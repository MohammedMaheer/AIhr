from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class ProbeDatabase:
    @contextmanager
    def get_cursor(self, **kwargs):
        class Cursor:
            def execute(self, *args):
                pass

            def fetchone(self):
                return (1,)
        yield Cursor(), None


def test_simultaneous_readiness_probes_do_not_collide_or_call_ai(tmp_path, monkeypatch):
    monkeypatch.setenv('SMARTHR_STORAGE_ROOT', str(tmp_path))
    monkeypatch.delenv('GCS_BUCKET_NAME', raising=False)
    with patch('database.get_db_manager', return_value=ProbeDatabase()), \
         patch.object(main, 'load_config', return_value={}), \
         patch.object(main.time, 'time', return_value=1793733268.0), \
         patch.object(main, 'gemini_client') as provider:
        def probe(_):
            return TestClient(main.app).get('/health/deep?llm=1')
        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(probe, range(40)))
        assert all(response.status_code == 200 for response in responses)
        assert all(response.json()['checks']['llm']['status'] == 'skipped' for response in responses)
        provider.assert_not_called()
    assert list((tmp_path / '_healthcheck').iterdir()) == []
