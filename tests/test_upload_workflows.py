"""Upload HTTP contracts and bounded offloading, without live storage or AI."""
import asyncio
import inspect
import io
import threading
from unittest.mock import MagicMock

from fastapi import HTTPException, UploadFile
import pytest

import main
from test_integration_workflows import api


PDF = b'%PDF-1.7\nFictional fixture, never sent to AI.'


@pytest.fixture
def upload_api(api, monkeypatch):
    client, db = api
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setattr(main.limiter, 'enabled', False)
    monkeypatch.setattr(main, '_resume_upload_slots', asyncio.Semaphore(2))
    monkeypatch.setattr(main, 'get_company_resources', lambda user: ('fixture-bucket', 'fixture-store'))
    monkeypatch.setattr(main, 'config', {'upload': {'allowed_extensions': ['.pdf', '.doc', '.docx']}})
    db.get_company_stats.return_value = {'max_resumes': 10, 'total_resumes': 2}
    store = MagicMock(return_value=True)
    monkeypatch.setattr(main, '_store_resume_upload', store)
    return client, db, store


def upload(client, **kwargs):
    return client.post('/api/upload-files', files=[('files', ('fixture.pdf', PDF, 'application/pdf'))], **kwargs)


@pytest.mark.parametrize('indexed', [True, False])
def test_file_upload_keeps_saved_and_indexed_outcomes_distinct(upload_api, indexed):
    client, db, store = upload_api
    store.return_value = indexed
    response = upload(client)
    assert response.status_code == 200
    result = response.json()
    assert result['batch_stats'] == {'successful': 1, 'failed': 0, 'total': 1}
    assert result['results'][0]['success'] is True
    assert result['results'][0]['vector_indexed'] is indexed
    assert store.call_args.kwargs['content'] == PDF
    assert store.call_args.kwargs['company_id'] == 1


def test_quota_database_failure_is_503_before_any_writes(upload_api):
    client, db, store = upload_api
    db.get_company_stats.side_effect = RuntimeError('private-database-credentials')
    response = upload(client)
    assert response.status_code == 503
    assert 'private-database' not in response.text
    store.assert_not_called()


def test_missing_tenant_identity_cannot_create_an_unowned_upload(upload_api):
    client, db, store = upload_api
    db.verify_session.return_value['company'] = {'company_code': 'fictional'}
    assert upload(client).status_code == 403
    store.assert_not_called()
    db.get_company_stats.assert_not_called()


@pytest.mark.parametrize('stats', [None, {}, {'max_resumes': -1, 'total_resumes': 0},
    {'max_resumes': False, 'total_resumes': 0}, {'max_resumes': 10, 'total_resumes': -1},
    {'max_resumes': 10, 'total_resumes': 'unknown'}, {'max_resumes': '', 'total_resumes': 0}])
def test_invalid_quota_state_fails_closed(upload_api, stats):
    client, db, store = upload_api
    db.get_company_stats.return_value = stats
    assert upload(client).status_code == 503
    store.assert_not_called()


@pytest.mark.parametrize('current', [10, 11])
def test_full_quota_stays_400_instead_of_becoming_500(upload_api, current):
    client, db, store = upload_api
    db.get_company_stats.return_value['total_resumes'] = current
    response = upload(client)
    assert response.status_code == 400
    assert 'maximum resume storage limit' in response.text
    store.assert_not_called()


def test_private_storage_failure_is_a_sanitized_per_file_error(upload_api):
    client, db, store = upload_api
    store.side_effect = RuntimeError('private-storage-path-and-key')
    response = upload(client)
    assert response.status_code == 200
    assert response.json()['results'][0]['success'] is False
    assert response.json()['batch_stats']['failed'] == 1
    assert 'private-storage' not in response.text


def test_invalid_docx_is_rejected_before_storage_or_indexing(upload_api):
    client, db, store = upload_api
    response = client.post('/api/upload-files', files=[('files', ('fixture.docx', b'PK\x03\x04fake', 'application/octet-stream'))])
    assert response.status_code == 200
    assert response.json()['results'][0]['success'] is False
    store.assert_not_called()


def attachments():
    return [{'id': 'synthetic-mail', 'subject': 'Fictional CV', 'attachments': [
        {'filename': 'fixture.pdf', 'original_filename': 'fixture.pdf', 'content': PDF, 'content_type': 'application/pdf'}]}]


@pytest.mark.parametrize('endpoint', ['/api/scrape-email-attachments', '/api/upload-files'])
def test_both_email_entrypoints_preserve_quota_503(upload_api, monkeypatch, endpoint):
    client, db, store = upload_api
    monkeypatch.setattr(main, 'scrape_outlook_attachments', lambda *args: attachments())
    db.get_company_stats.side_effect = RuntimeError('private-database')
    data = {'email_provider': 'outlook', 'email_address': 'fixture@example.invalid', 'email_limit': 1, 'limit': 1}
    if endpoint.endswith('upload-files'):
        data['scrape_email'] = 'true'
    response = client.post(endpoint, data=data)
    assert response.status_code == 503
    assert 'private-database' not in response.text
    store.assert_not_called()


def test_email_attachment_contract_survives_worker_offload(upload_api, monkeypatch):
    client, db, store = upload_api
    monkeypatch.setattr(main, 'scrape_outlook_attachments', lambda *args: attachments())
    response = client.post('/api/scrape-email-attachments', data={'email_provider': 'outlook', 'email_address': 'fixture@example.invalid', 'limit': 1})
    assert response.status_code == 200
    assert response.json()['email_stats']['successful_uploads'] == 1
    assert response.json()['results'][0]['source'] == 'email_attachment'
    assert store.call_args.kwargs['content'] == PDF


def test_unknown_file_size_is_read_with_a_hard_bound(upload_api, monkeypatch):
    client, db, store = upload_api
    monkeypatch.setattr(main, 'MAX_FILE_SIZE', 32)
    file = UploadFile(io.BytesIO(PDF*10), filename='fixture.pdf', size=None)
    user = db.verify_session.return_value
    result = asyncio.run(inspect.unwrap(main.upload_files)(request=None, files=[file], folder_path=None,
        batch_info=None, scrape_email=False, email_provider=None, email_address=None,
        email_password=None, email_limit=1, user=user))
    assert result['results'][0]['success'] is False
    assert file.file.tell() == 33
    store.assert_not_called()


def test_shared_store_preserves_metadata_and_call_order(monkeypatch):
    db, storage = MagicMock(), MagicMock()
    records = db.resume_upload_lock.return_value.__enter__.return_value
    records.get_company_stats.return_value = {'max_resumes': 10, 'total_resumes': 0}
    calls = []
    storage.bucket.return_value.blob.return_value.upload_from_string.side_effect = lambda *a, **k: calls.append('storage')
    records.track_resume_upload.side_effect = lambda **k: calls.append('tracking')
    monkeypatch.setattr(main, '_get_storage_client', lambda: storage)
    index = MagicMock(side_effect=lambda **k: calls.append('index') or False)
    monkeypatch.setattr(main, 'upload_to_vector_datastore', index)
    result = main._store_resume_upload(db, bucket_name='fixture-bucket', blob_name='resume/fixture.pdf',
        filename='fixture.pdf', content=PDF, content_type='application/pdf', user_id=7, company_id=1, company_code='fixture')
    assert result is False and calls == ['storage', 'tracking', 'index']
    assert records.track_resume_upload.call_args.kwargs['file_path'] == 'resume/fixture.pdf'
    assert index.call_args.kwargs['user_id'] == '7'
    db.resume_upload_lock.return_value.__exit__.assert_called_once()


def test_offloaded_indexing_keeps_loop_responsive_and_capacity_bounded(monkeypatch):
    async def run():
        slots = asyncio.Semaphore(2)
        monkeypatch.setattr(main, '_resume_upload_slots', slots)
        both_started, release = threading.Event(), threading.Event()
        active = 0
        peak = 0
        lock = threading.Lock()

        def work(*args, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 2:
                    both_started.set()
            try:
                assert release.wait(3)
                return True
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(main, '_store_resume_upload', work)
        tasks = [asyncio.create_task(main._run_resume_upload(None)) for _ in range(4)]
        try:
            assert await asyncio.to_thread(both_started.wait, 1)
            await asyncio.sleep(0)
            assert peak == 2 and not all(task.done() for task in tasks)
        finally:
            release.set()
        assert all(await asyncio.gather(*tasks))
        assert peak == 2 and active == 0
        await asyncio.sleep(0)
        assert not main._resume_upload_tasks
    asyncio.run(run())


def test_disconnected_caller_does_not_release_a_running_worker_slot(monkeypatch):
    async def run():
        slots = asyncio.Semaphore(1)
        monkeypatch.setattr(main, '_resume_upload_slots', slots)
        started, release = threading.Event(), threading.Event()
        def work(*args, **kwargs):
            started.set()
            assert release.wait(3)
            return True
        monkeypatch.setattr(main, '_store_resume_upload', work)
        caller = asyncio.create_task(main._run_resume_upload(None))
        assert await asyncio.to_thread(started.wait, 1)
        caller.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await caller
            assert slots.locked()
            workers = list(main._resume_upload_tasks)
            assert workers and all(not task.done() for task in workers)
        finally:
            release.set()
            await asyncio.gather(*list(main._resume_upload_tasks))
            await asyncio.sleep(0)
        assert not slots.locked() and not main._resume_upload_tasks
    asyncio.run(run())
