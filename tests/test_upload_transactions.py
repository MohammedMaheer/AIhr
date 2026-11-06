"""Cross-connection upload quota safety in an isolated PostgreSQL schema."""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import MagicMock

from fastapi import HTTPException
import pytest

import main
from test_durable_search import queue_db


@pytest.fixture
def uploads_db(queue_db, monkeypatch):
    # Quota/rollback tests isolate indexing metadata, which has its own SQL fixtures.
    monkeypatch.setattr('services.resume_filters.record_metadata', MagicMock())
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('''
            ALTER TABLE tenant_companies ADD COLUMN max_resumes INTEGER,
                ADD COLUMN max_users INTEGER, ADD COLUMN subscription_plan TEXT,
                ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
            INSERT INTO tenant_companies(id,company_code,max_resumes,max_users) VALUES (1,'fictional',1,10);
            CREATE TABLE resume_uploads (id SERIAL PRIMARY KEY, file_name TEXT, file_path TEXT,
                file_size INTEGER, mime_type TEXT, uploaded_by_user_id INTEGER, company_id INTEGER);
        ''')
    return queue_db


def store(database, name):
    return main._store_resume_upload(database, bucket_name='fixture-bucket', blob_name=name,
        filename=name, content=b'fictional fixture', content_type='application/pdf',
        user_id=7, company_id=1, company_code='fictional')


def test_concurrent_uploads_cannot_both_claim_the_last_company_slot(uploads_db, monkeypatch):
    storage = MagicMock()
    ready = threading.Barrier(2)
    writes = []
    def blob(name):
        ready.wait(timeout=3)
        result = MagicMock()
        result.upload_from_string.side_effect = lambda *args, **kwargs: writes.append(name)
        return result
    storage.bucket.return_value.blob.side_effect = blob
    monkeypatch.setattr(main, '_get_storage_client', lambda: storage)
    index = MagicMock(return_value=True)
    monkeypatch.setattr(main, 'upload_to_vector_datastore', index)
    def attempt(name):
        try:
            return store(uploads_db, name)
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, ['first.pdf', 'second.pdf']))
    assert outcomes.count(True) == 1 and outcomes.count(400) == 1
    assert len(writes) == 1 and index.call_count == 1
    assert uploads_db.get_company_stats(1)['total_resumes'] == 1


def test_storage_failure_rolls_back_tracking_and_releases_company_lock(uploads_db, monkeypatch):
    storage = MagicMock()
    blob = storage.bucket.return_value.blob.return_value
    blob.upload_from_string.side_effect = RuntimeError('synthetic storage failure')
    monkeypatch.setattr(main, '_get_storage_client', lambda: storage)
    index = MagicMock(return_value=True)
    monkeypatch.setattr(main, 'upload_to_vector_datastore', index)
    with pytest.raises(RuntimeError):
        store(uploads_db, 'failure.pdf')
    assert uploads_db.get_company_stats(1)['total_resumes'] == 0
    index.assert_not_called()
    blob.upload_from_string.side_effect = None
    assert store(uploads_db, 'retry.pdf') is True
    assert uploads_db.get_company_stats(1)['total_resumes'] == 1


def test_inactive_workspace_is_rejected_before_storage_write(uploads_db, monkeypatch):
    with uploads_db.get_cursor() as (cursor, _):
        cursor.execute('UPDATE tenant_companies SET is_active=FALSE WHERE id=1')
    storage = MagicMock()
    monkeypatch.setattr(main, '_get_storage_client', lambda: storage)
    with pytest.raises(ValueError):
        store(uploads_db, 'fixture.pdf')
    storage.bucket.return_value.blob.return_value.upload_from_string.assert_not_called()
    assert uploads_db.get_company_stats(1)['total_resumes'] == 0


def test_indexing_runs_after_upload_transaction_commits(uploads_db, monkeypatch):
    storage = MagicMock()
    monkeypatch.setattr(main, '_get_storage_client', lambda: storage)
    def index(**kwargs):
        # A different pooled connection must already see the committed tracking row.
        assert uploads_db.get_company_stats(1)['total_resumes'] == 1
        return False
    monkeypatch.setattr(main, 'upload_to_vector_datastore', index)
    assert store(uploads_db, 'fixture.pdf') is False
    assert uploads_db.get_company_stats(1)['total_resumes'] == 1
