import base64
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import main
from services.managed_desktop import DesktopPool, REVISION, configured_companies, result_message
from test_durable_search import queue_db  # noqa: F401
from test_integration_workflows import api  # noqa: F401
from vps_local import discovery_shim as search


BASE = '/api/managed-desktop'
VECTOR = [1.] + [0.] * 383


@pytest.fixture
def pool(queue_db, tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    folder = tmp_path/'fixture'/'engineering'
    folder.mkdir(parents=True)
    for number in range(2):
        (folder/f'{number}.txt').write_text(f'Synthetic Python developer {number} with 5 years. Location: Dubai, UAE.', encoding='utf-8')
    with queue_db.get_cursor() as (cur, _):
        cur.execute('''INSERT INTO tenant_companies(id) VALUES (1),(2);
            CREATE TABLE resume_uploads (company_id integer,file_path text,upload_timestamp timestamp DEFAULT now());
            INSERT INTO resume_uploads(company_id,file_path) VALUES (1,'engineering/0.txt'),(1,'engineering/1.txt');''')
        schema = (root/'deploy/vps/schema-local-mode.sql').read_text()
        cur.execute('\n'.join(line for line in schema.splitlines() if not line.startswith('\\')))
        cur.execute((root/'deploy/vps/migrations/20261121_managed_desktop.sql').read_text())
        monkeypatch.setattr(search, '_advanced_schema_ensured', False)
        search._ensure_advanced_search_schema(cur)
    monkeypatch.setenv('SMARTHR_STORAGE_ROOT', str(tmp_path))
    monkeypatch.setattr(search, '_get_pool', lambda: queue_db.pool)
    return DesktopPool(queue_db, {1, 2})


def identity(pool, company=1):
    key = Ed25519PrivateKey.generate()
    public = base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    code = pool.invite(company)
    worker = pool.enroll(code, 'Device fixture', public)
    assert worker and pool.enroll(code, 'Duplicate', public) is None
    return worker['workerId'], worker['credential'], key


def documents():
    return [{'key': f'engineering/{i}.txt', 'mime': 'text/plain'} for i in range(2)]


def expire(pool, job, *, worker_only=False):
    with pool.db.get_cursor() as (cur, _):
        cur.execute("UPDATE managed_desktop_jobs SET lease_until=now()-interval '2 seconds' WHERE id=%s", (job,))
        if not worker_only:
            cur.execute("UPDATE managed_desktop_jobs SET expires_at=now()-interval '1 second' WHERE id=%s", (job,))


def ready(pool, worker, model=REVISION):
    with pool.db.get_cursor() as (cur, _):
        cur.execute("UPDATE managed_desktop_workers SET last_seen=now()-interval '2 seconds' WHERE id=%s", (worker[0],))
    return pool.reserve(worker[0], worker[1], model, True)


def submit(pool, worker, lease, *, altered=False):
    data = base64.b64encode(struct.pack('<768f', *(VECTOR*2))).decode()
    proof = worker[2].sign(result_message(lease['jobId'], lease['leaseId'], lease['digest'], data))
    if altered:
        data = ('A' if data[0] != 'A' else 'B') + data[1:]
    return pool.complete(worker[0], worker[1], lease['jobId'], lease['leaseId'], data, base64.b64encode(proof).decode())


def test_pg_lease_reassigns_to_another_worker_without_a_second_publish(pool, monkeypatch):
    a, b, other = identity(pool), identity(pool), identity(pool, 2)
    assert ready(pool, a) == (None, True)
    assert ready(pool, b) == (None, True)
    assert ready(pool, other) == (None, True)
    job = pool.enqueue(1, 'fixture', documents())
    assert job and ready(pool, other) == (None, True)
    first = pool.materialize(ready(pool, a)[0])
    assert first['jobId'] == job
    assert 0 < first['leaseMs'] <= 7000
    assert ready(pool, b) == (None, True)
    expire(pool, job, worker_only=True)
    assert submit(pool, a, first) is False and ready(pool, a) == (None, True)
    # A newly created coordinator has no in-memory job state.
    restarted = DesktopPool(pool.db, {1, 2})
    second = restarted.materialize(ready(restarted, b)[0])
    assert second['jobId'] == job and second['leaseId'] != first['leaseId']
    assert submit(restarted, b, second, altered=True) is False
    assert submit(restarted, b, second) is True and submit(restarted, b, second) is False
    monkeypatch.setattr(search, 'embed_resume_entries', lambda _: pytest.fail('VPS re-embedded an accepted batch'))
    assert restarted.publish_next() is True and restarted.publish_next() is False
    assert restarted.status(job) == [True, True]
    with pool.db.get_cursor() as (cur, _):
        cur.execute('SELECT count(*) AS n FROM resume_embeddings WHERE embedding IS NOT NULL AND source_uploaded_at IS NOT NULL')
        assert cur.fetchone()['n'] == 2
        cur.execute('SELECT vectors,input_digest FROM managed_desktop_jobs WHERE id=%s', (job,))
        assert cur.fetchone() == {'vectors': None, 'input_digest': None}


@pytest.mark.parametrize('reason', ['expired', 'revoked', 'disabled', 'text-changed'])
def test_fallback_uses_canonical_index_and_rolls_back_partial_publish(pool, monkeypatch, reason):
    worker = identity(pool)
    ready(pool, worker)
    job = pool.enqueue(1, 'fixture', documents())
    lease = pool.materialize(ready(pool, worker)[0])
    if reason == 'expired':
        expire(pool, job)
    elif reason == 'revoked':
        assert submit(pool, worker, lease) and not pool.revoke(2, worker[0])
        assert pool.revoke(1, worker[0])
        expire(pool, job)
    elif reason == 'disabled':
        assert submit(pool, worker, lease)
        pool = DesktopPool(pool.db, set())
    else:
        assert submit(pool, worker, lease)
        entry = pool.prepare({'company_id': 1, 'bucket': 'fixture', 'documents': documents()})[0]
        entry.path.write_text('Synthetic updated Python developer with relevant experience.', encoding='utf-8')
    calls = []
    monkeypatch.setattr(search, 'embed_resume_entries', lambda entries: calls.append(len(entries)) or [VECTOR]*len(entries))
    write = search._write_document_embedding

    def fail_second(entry, vector, **options):
        if entry.filename == '1.txt':
            raise RuntimeError('Synthetic writer error')
        return write(entry, vector, **options)

    with monkeypatch.context() as context:
        context.setattr(search, '_write_document_embedding', fail_second)
        with pytest.raises(RuntimeError):
            pool.publish_next()
    assert pool.status(job) is None
    with pool.db.get_cursor() as (cur, _):
        cur.execute('SELECT count(*) AS n FROM resume_embeddings')
        assert cur.fetchone()['n'] == 0
    assert pool.publish_next() and pool.status(job) == [True, True]
    assert calls == [2, 2]


def test_agent_and_admin_entrypoints_are_scoped_and_bounded(api, pool, monkeypatch):
    client, auth = api
    monkeypatch.setattr(main.limiter, 'enabled', False)
    monkeypatch.setattr(main.app.state, 'managed_desktop_scheduler', SimpleNamespace(pool=pool), raising=False)
    assert client.post(BASE+'/admin/invites').status_code == 403
    auth.verify_session.return_value['user_type'] = 'tenant_admin'
    invitation = client.post(BASE+'/admin/invites')
    assert invitation.status_code == 201 and invitation.headers['cache-control'] == 'no-store'
    key = Ed25519PrivateKey.generate().public_key()
    data = {'enrollmentCode': invitation.json()['enrollmentCode'], 'name': 'Company fixture',
            'publicKey': base64.b64encode(key.public_bytes(serialization.Encoding.DER,
                                                          serialization.PublicFormat.SubjectPublicKeyInfo)).decode()}
    paired = client.post(BASE+'/enroll', json=data)
    assert paired.status_code == 201
    assert client.post(BASE+'/enroll', json=data).status_code == 400
    assert client.post(BASE+'/claim', json={}).status_code == 401
    worker = paired.json()
    headers = {'Authorization': 'Bearer '+worker['credential'], 'X-SmartHR-Worker-Id': worker['workerId']}
    assert client.post(BASE+'/claim', headers=headers, json={'model': REVISION, 'ready': True}).status_code == 204
    assert client.post(BASE+'/claim', headers=headers, json={'bad':'A'*3000}).status_code == 413
    auth.verify_session.return_value['company']['company_id'] = 2
    assert client.delete(BASE+'/admin/workers/'+worker['workerId']).status_code == 404
    auth.verify_session.return_value['company']['company_id'] = 1
    assert client.delete(BASE+'/admin/workers/'+worker['workerId']).status_code == 204
    assert client.post(BASE+'/claim', headers=headers, json={}).status_code == 401


def test_default_and_malformed_allowlist_fail_closed(monkeypatch):
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.delenv('SMARTHR_MANAGED_DESKTOP_ENABLED', raising=False)
    monkeypatch.setenv('SMARTHR_MANAGED_DESKTOP_COMPANIES', '1,8')
    assert configured_companies() == set()
    monkeypatch.setenv('SMARTHR_MANAGED_DESKTOP_ENABLED', '1')
    assert configured_companies() == {1, 8}
    monkeypatch.setenv('SMARTHR_MANAGED_DESKTOP_COMPANIES', '1,not-a-tenant')
    assert configured_companies() == set()
