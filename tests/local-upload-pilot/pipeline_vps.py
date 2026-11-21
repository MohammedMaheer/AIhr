"""Exercise real API routes and the durable scheduler with synthetic files on an isolated VPS network."""
import base64
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import secrets
from threading import Event
from time import process_time
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from handoff_vps import Job, app, clients, db, index, jobs, main, measured, search, serve


class BusyFixture:
    """Force the admission decision, keeping the normal bounded queue execution."""

    def __init__(self, slots):
        self.acquire = slots.acquire
        self.release = slots.release
        self.busy = Event()

    def locked(self):
        return self.busy.is_set()


def upload(client, pdfs, company, owner, bucket, handle):
    folder = 'Synthetic/Pipeline/' + handle
    files = [(f'{i}.pdf', base64.b64decode(data, validate=True), 'application/pdf') for i, data in enumerate(pdfs)]
    cpu = process_time()
    result, stats = measured(lambda: client.post('/api/upload-files', data={'folder_path': folder},
                                                 files=[('files', item) for item in files]))
    assert result.status_code == 200, result.status_code
    rows = result.json()['results']
    assert len(rows) == len(files)
    docs = []
    for row, (_, raw, mime) in zip(rows, files, strict=True):
        assert row['success'] and row['vector_indexed']
        uri = row['gcs_path']
        path = urlsplit(uri).path.lstrip('/')
        assert (Path(os.environ['SMARTHR_STORAGE_ROOT']) / bucket / path).read_bytes() == raw
        docs.append(index.Document(struct_data={'company_id': company}, content=index.Document.Content(uri=uri, mime_type=mime)))
    jobs[handle] = Job(owner, company, bucket, folder, docs, 'indexed', finished=True)
    return {'indexed': len(rows), 'apiCpuMs': round((process_time() - cpu) * 1000, 2), **stats}


def run():
    _, company, _, bucket = clients['owner']
    os.environ.update(SMARTHR_MANAGED_DESKTOP_ENABLED='1', SMARTHR_MANAGED_DESKTOP_COMPANIES=str(company))
    mail = 'pipeline-admin@desktop-fixtures.invalid'
    password = secrets.token_urlsafe(24)
    owner = db.create_user(mail, password, 'Pipeline QA', 'tenant_admin', company)
    slots = BusyFixture(main._resume_upload_slots)
    main._resume_upload_slots = slots
    uploads = {}
    with TestClient(app, base_url='https://testserver') as client, ThreadPoolExecutor(max_workers=1) as executor:
        assert app.state.managed_desktop_scheduler.task is not None
        assert client.post('/api/login', data={'email': mail, 'password': password}).status_code == 200
        client.headers.update({'x-csrf-token': client.cookies['csrf_token'], 'origin': 'https://testserver'})
        worker = TestClient(app, base_url='https://testserver')
        worker.portal = client.portal

        def command(cmd):
            op = cmd['op']
            if op == 'invite':
                result = client.post('/api/managed-desktop/admin/invites')
                assert result.status_code == 201
                return result.json()
            if op == 'http':
                path = cmd['path']
                assert re.fullmatch(r'/api/managed-desktop/(claim|enroll|jobs/[a-f0-9-]{36}/complete)', path)
                result = worker.post(path, json=cmd['body'], headers=cmd['headers'])
                return {'status': result.status_code, 'body': result.text}
            if op == 'upload':
                assert all(item.done() for item in uploads.values()) and 2 <= len(cmd['pdfs']) <= 20
                slots.busy.set() if cmd['busy'] else slots.busy.clear()
                handle = secrets.token_hex(8)
                uploads[handle] = executor.submit(upload, client, cmd['pdfs'], company, owner, bucket, handle)
                return {'jobId': handle}
            if op == 'status':
                folder = 'Synthetic/Pipeline/' + cmd['jobId']
                with db.get_cursor() as (cur, _):
                    cur.execute('''SELECT cardinality(tried) AS attempts, finished_at IS NOT NULL AS published
                                   FROM managed_desktop_jobs WHERE company_id=%s AND documents->0->>'key' LIKE %s
                                   ORDER BY created_at''', (company, folder+'/%'))
                    return {'jobs': cur.fetchall(), 'done': uploads[cmd['jobId']].done()}
            if op == 'results':
                return uploads[cmd['jobId']].result(timeout=45)
            if op == 'search':
                return search(cmd)
            raise ValueError('Unknown pipeline command')

        serve(command)


if __name__ == '__main__':
    run()
