from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main
from database import DatabaseManager


@pytest.fixture
def client():
    main.app.dependency_overrides[main.require_auth] = lambda: {"id": 7, "user_type": "super_admin"}
    yield TestClient(main.app)
    main.app.dependency_overrides.pop(main.require_auth, None)


@pytest.mark.parametrize("path", ["../file.txt", "a/../file.txt", "folder/..", "a\\file.txt", "/file.txt", "a\x00.txt"])
def test_download_rejects_invalid_object_path_before_storage(client, path):
    with patch.object(main, "_get_storage_client") as storage:
        response = client.get('/api/download-resume', params={"file_path": path})
    assert response.status_code == 400
    storage.assert_not_called()


def test_bucket_qualified_download_keeps_bucket_identity(client):
    storage = MagicMock()
    storage.bucket.return_value.blob.return_value.download_as_bytes.return_value = b"Synthetic resume"
    with patch.object(main, "_get_storage_client", return_value=storage):
        response = client.get('/api/download-resume', params={"file_path": "gs://qa-bucket/nested/qa.txt"})
    assert response.status_code == 200 and response.content == b"Synthetic resume"
    storage.bucket.assert_called_once_with('qa-bucket')


def test_upload_ownership_query_handles_bucket_qualified_legacy_paths():
    db = DatabaseManager.__new__(DatabaseManager)
    db.get_cursor = MagicMock()
    cursor = MagicMock()
    db.get_cursor.return_value.__enter__.return_value = (cursor, None)
    assert db.resume_belongs_to_company('legacy/qa.pdf', 27)
    sql, params = cursor.execute.call_args.args
    assert 'c.gcs_bucket_name' in sql
    assert 'u.company_id = %s' in sql
    assert params == ('legacy/qa.pdf', 'legacy/qa.pdf', 27)
