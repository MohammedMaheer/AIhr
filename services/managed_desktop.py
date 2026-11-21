"""Durable leases for trusted, tenant-scoped desktop embedding workers."""
import asyncio
import base64
import binascii
from contextlib import suppress
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import struct
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from services.resume_filters import record_metadata

logger = logging.getLogger(__name__)
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
LEASE_SECONDS = 7
JOB_SECONDS = 17
MAX_VECTORS = 8
VECTOR_WIDTH = 384
RESULT_LIMIT = 24000


def sha(value):
    return hashlib.sha256(value).hexdigest()


def configured_companies():
    if os.getenv('SMARTHR_LOCAL_MODE', '').lower() not in {'1', 'true', 'yes', 'on'}:
        return frozenset()
    if os.getenv('SMARTHR_MANAGED_DESKTOP_ENABLED') != '1':
        return frozenset()
    values = os.getenv('SMARTHR_MANAGED_DESKTOP_COMPANIES', '')
    if re.fullmatch(r'[1-9][0-9]{0,9}(?:,[1-9][0-9]{0,9}){0,19}', values):
        return frozenset(int(item) for item in values.split(','))
    return frozenset()


def compatible_model():
    if os.getenv('SMARTHR_EMBED_MODEL', 'all-MiniLM-L6-v2') not in {MODEL_NAME, 'all-MiniLM-L6-v2'}:
        return False
    home = Path(os.getenv('SENTENCE_TRANSFORMERS_HOME', '/app/.st_cache'))
    try:
        return (home/'models--sentence-transformers--all-MiniLM-L6-v2/refs/main').read_text().strip() == REVISION
    except OSError:
        return False


def digest_token(value):
    return sha(value.encode('ascii')) if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{43}', value) else None


def parse_key(encoded):
    if not isinstance(encoded, str) or len(encoded) > 100:
        return None
    try:
        data = base64.b64decode(encoded, validate=True)
        return data if isinstance(serialization.load_der_public_key(data), Ed25519PublicKey) else None
    except (ValueError, TypeError, binascii.Error):
        return None


def result_message(job_id, lease_id, digest, packed):
    return f'managed-v1:{job_id}:{lease_id}:{REVISION}:{digest}:{packed}'.encode('ascii')


def unpack_vectors(raw, count):
    if not 2 <= count <= MAX_VECTORS or len(raw) != count * VECTOR_WIDTH * 4:
        return None
    vectors = list(struct.iter_unpack(f'<{VECTOR_WIDTH}f', raw))
    return vectors if all(all(map(math.isfinite, row)) and 0.99 <= math.fsum(x*x for x in row) <= 1.01 for row in vectors) else None


class DesktopPool:
    def __init__(self, db, companies):
        self.db = db
        self.companies = frozenset(companies)

    @staticmethod
    def installed(db):
        with db.get_cursor() as (cur, _):
            cur.execute("SELECT to_regclass('managed_desktop_jobs') IS NOT NULL AS installed")
            return cur.fetchone()['installed']

    def invite(self, company):
        token = secrets.token_urlsafe(32)
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT pg_advisory_xact_lock(713801,%s)', (company,))
            cur.execute('DELETE FROM managed_desktop_invites WHERE company_id=%s OR expires_at<=now()', (company,))
            cur.execute('INSERT INTO managed_desktop_invites VALUES (%s,%s,now()+interval \'10 minutes\')',
                        (digest_token(token), company))
        return token

    def enroll(self, code, name, encoded_key):
        digest, key = digest_token(code), parse_key(encoded_key)
        if not digest or not key or not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9 ._()-]{1,80}', name.strip()):
            return None
        worker_id, credential = str(uuid.uuid4()), secrets.token_urlsafe(32)
        with self.db.get_cursor() as (cur, _):
            cur.execute('''DELETE FROM managed_desktop_invites WHERE digest=%s AND expires_at>clock_timestamp()
                           RETURNING company_id''', (digest,))
            row = cur.fetchone()
            if not row or row['company_id'] not in self.companies:
                return None
            company = row['company_id']
            cur.execute('SELECT pg_advisory_xact_lock(713802,%s)', (company,))
            cur.execute('SELECT count(*) AS n FROM managed_desktop_workers WHERE company_id=%s AND enabled', (company,))
            if cur.fetchone()['n'] >= 16:
                return None
            cur.execute('''INSERT INTO managed_desktop_workers(id,company_id,name,credential,public_key)
                           VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id''',
                        (worker_id, company, name.strip(), digest_token(credential), key))
            if not cur.fetchone():
                return None
        return {'workerId': worker_id, 'credential': credential, 'model': REVISION}

    def workers(self, company):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''SELECT id::text,name,enabled,last_seen,
                          ready AND last_seen>now()-interval '12 seconds' AS ready
                          FROM managed_desktop_workers WHERE company_id=%s ORDER BY created_at DESC LIMIT 100''', (company,))
            return cur.fetchall()

    def revoke(self, company, worker):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''UPDATE managed_desktop_workers SET enabled=false,ready=false WHERE company_id=%s AND id=%s AND enabled''',
                        (company, worker))
            if not cur.rowcount:
                return False
            cur.execute('''UPDATE managed_desktop_jobs SET lease_until=now(),vectors=NULL
                           WHERE worker_id=%s AND finished_at IS NULL''', (worker,))
        return True

    def _authenticate(self, cur, worker, credential):
        digest = digest_token(credential)
        if not digest:
            return None
        cur.execute('''SELECT company_id,public_key,last_seen FROM managed_desktop_workers
                       WHERE id=%s AND enabled AND credential=%s FOR UPDATE''', (worker, digest))
        row = cur.fetchone()
        return row if row and row['company_id'] in self.companies else None

    def enqueue(self, company, bucket, documents):
        if company not in self.companies or not 2 <= len(documents) <= MAX_VECTORS:
            return None
        job = str(uuid.uuid4())
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT pg_advisory_xact_lock(713803,%s)', (company,))
            cur.execute('''INSERT INTO managed_desktop_jobs(id,company_id,bucket,documents,expires_at)
                SELECT %s,%s,%s,%s::jsonb,now()+make_interval(secs=>%s)
                WHERE EXISTS (SELECT 1 FROM managed_desktop_workers w
                    WHERE w.company_id=%s AND w.enabled AND w.ready AND w.last_seen>now()-interval '12 seconds'
                      AND NOT EXISTS (SELECT 1 FROM managed_desktop_jobs j WHERE j.worker_id=w.id
                          AND j.finished_at IS NULL AND j.lease_until>now() AND j.vectors IS NULL))
                    AND (SELECT count(*) FROM managed_desktop_jobs WHERE company_id=%s AND finished_at IS NULL)<16
                RETURNING id''', (job, company, bucket, json.dumps(documents), JOB_SECONDS, company, company))
            return job if cur.fetchone() else None

    def reserve(self, worker, credential, model, ready):
        with self.db.get_cursor() as (cur, _):
            who = self._authenticate(cur, worker, credential)
            if who is None:
                return None, False
            # This update is also the heartbeat. One request per second per device is ample.
            cur.execute('''UPDATE managed_desktop_workers SET last_seen=clock_timestamp(),ready=%s WHERE id=%s
                           AND (last_seen IS NULL OR last_seen<=clock_timestamp()-interval '1 second')''',
                        (ready is True and model == REVISION, worker))
            if not cur.rowcount or ready is not True or model != REVISION:
                return None, True
            lease = str(uuid.uuid4())
            cur.execute('''WITH chosen AS (
                SELECT id FROM managed_desktop_jobs WHERE company_id=%s AND finished_at IS NULL AND vectors IS NULL
                    AND expires_at>clock_timestamp() AND coalesce(lease_until,'-infinity'::timestamptz)<=clock_timestamp()
                    AND cardinality(tried)<2 AND NOT (%s::uuid=ANY(tried))
                    AND NOT EXISTS (SELECT 1 FROM managed_desktop_jobs j WHERE j.worker_id=%s
                        AND j.finished_at IS NULL AND j.vectors IS NULL AND j.lease_until>clock_timestamp())
                ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
                UPDATE managed_desktop_jobs j SET worker_id=%s,lease_id=%s,
                    tried=array_append(j.tried,%s::uuid),lease_until=least(j.expires_at,clock_timestamp()+make_interval(secs=>%s)),
                    input_digest=NULL FROM chosen WHERE j.id=chosen.id
                RETURNING j.id::text,j.lease_id::text,j.company_id,j.bucket,j.documents,j.lease_until''',
                        (who['company_id'], worker, worker, worker, lease, worker, LEASE_SECONDS))
            return cur.fetchone(), True

    @staticmethod
    def prepare(job):
        from vps_local import discovery_shim as index
        entries = []
        for item in job['documents']:
            doc = index.Document(struct_data={'company_id': job['company_id']}, content=index.Document.Content(
                uri=f"gs://{job['bucket']}/{item['key']}", mime_type=item['mime']))
            entries.append(index._prepare_document_embedding(doc))
        return entries

    @staticmethod
    def texts_digest(entries):
        if not all(entry is not None and entry.searchable for entry in entries):
            return None
        hashes = [sha(entry.text.encode('utf-8')) for entry in entries]
        return sha(''.join(hashes).encode('ascii'))

    def materialize(self, job):
        entries = self.prepare(job)
        digest = self.texts_digest(entries)
        with self.db.get_cursor() as (cur, _):
            cur.execute('''UPDATE managed_desktop_jobs j SET input_digest=%s,
                        lease_until=CASE WHEN %s::text IS NULL THEN clock_timestamp() ELSE lease_until END,
                        expires_at=CASE WHEN %s::text IS NULL THEN clock_timestamp() ELSE expires_at END
                WHERE j.id=%s AND j.lease_id=%s AND j.lease_until>clock_timestamp() AND j.finished_at IS NULL
                    AND EXISTS (SELECT 1 FROM managed_desktop_workers w WHERE w.id=j.worker_id AND w.enabled)
                RETURNING greatest(0, floor(extract(epoch FROM (lease_until-clock_timestamp())) * 1000))::integer AS lease_ms''',
                        (digest, digest, digest, job['id'], job['lease_id']))
            live = cur.fetchone()
        if not (live and digest and live['lease_ms']):
            return None
        return {'jobId': job['id'], 'leaseId': job['lease_id'], 'model': REVISION, 'digest': digest,
                'leaseMs': live['lease_ms'], 'texts': [entry.text for entry in entries]}

    def complete(self, worker, credential, job, lease, packed, signature):
        if not isinstance(packed, str) or not packed.isascii() or len(packed) > RESULT_LIMIT or not isinstance(signature, str) or len(signature) > 96:
            return False
        with self.db.get_cursor() as (cur, _):
            who = self._authenticate(cur, worker, credential)
            if who is None:
                return None
            cur.execute('''SELECT input_digest,jsonb_array_length(documents) AS n FROM managed_desktop_jobs
                        WHERE id=%s AND worker_id=%s AND company_id=%s AND lease_id=%s AND lease_until>clock_timestamp()
                          AND finished_at IS NULL AND vectors IS NULL AND input_digest IS NOT NULL FOR UPDATE''',
                        (job, worker, who['company_id'], lease))
            ref = cur.fetchone()
            if not ref:
                return False
            try:
                key = serialization.load_der_public_key(bytes(who['public_key']))
                key.verify(base64.b64decode(signature, validate=True), result_message(job, lease, ref['input_digest'], packed))
                payload = base64.b64decode(packed, validate=True)
            except (ValueError, TypeError, binascii.Error, InvalidSignature):
                return False
            if unpack_vectors(payload, ref['n']) is None:
                return False
            cur.execute('UPDATE managed_desktop_jobs SET vectors=%s WHERE id=%s AND lease_until>clock_timestamp()',
                        (payload, job))
            return cur.rowcount == 1

    def status(self, job):
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT outcomes FROM managed_desktop_jobs WHERE id=%s AND finished_at IS NOT NULL', (job,))
            row = cur.fetchone()
        return row['outcomes'] if row else None

    def due(self):
        with self.db.get_cursor() as (cur, _):
            cur.execute("SELECT EXISTS (SELECT 1 FROM managed_desktop_jobs WHERE finished_at IS NULL AND (vectors IS NOT NULL OR expires_at<=now())) AS due")
            return cur.fetchone()['due']

    def publish_next(self):
        from vps_local import discovery_shim as index

        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT pg_try_advisory_xact_lock(713804,1) AS owned')
            if not cur.fetchone()['owned']:
                return False
            cur.execute('''SELECT j.*,w.enabled AS worker_enabled FROM managed_desktop_jobs j
                        LEFT JOIN managed_desktop_workers w ON w.id=j.worker_id WHERE j.finished_at IS NULL
                        AND (j.vectors IS NOT NULL OR j.expires_at<=now())
                        ORDER BY j.created_at LIMIT 1 FOR UPDATE OF j SKIP LOCKED''')
            job = cur.fetchone()
            if not job:
                return False
            entries = self.prepare(job)
            trusted = job['company_id'] in self.companies and job['worker_enabled'] and job['vectors'] is not None
            vectors = None
            if trusted and self.texts_digest(entries) == job['input_digest']:
                vectors = unpack_vectors(job['vectors'], len(entries))
            if vectors is None:
                vectors = index.embed_resume_entries(entries)
            outcomes = []
            for item, entry, vector in zip(job['documents'], entries, vectors, strict=True):
                if entry is None:
                    outcomes.append(False)
                    continue
                outcome = index._write_document_embedding(entry, vector, cursor=cur)
                record_metadata(self.db, job['bucket'], item['key'], job['company_id'], cursor=cur)
                outcomes.append(outcome.indexed)
            cur.execute('''UPDATE managed_desktop_jobs SET outcomes=%s::jsonb,finished_at=now(),vectors=NULL,input_digest=NULL
                           WHERE id=%s''', (json.dumps(outcomes), job['id']))
        return True

    def prune(self):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''DELETE FROM managed_desktop_jobs WHERE id IN (SELECT id FROM managed_desktop_jobs
                        WHERE finished_at<now()-interval '1 day' LIMIT 100)''')


class DesktopScheduler:
    def __init__(self, pool, run_upload_worker, clear_cache):
        self.pool = pool
        self.run_upload_worker = run_upload_worker
        self.clear_cache = clear_cache
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run(), name='managed-desktop-scheduler')

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def run(self):
        ticks = 0
        while True:
            try:
                if await asyncio.to_thread(self.pool.due):
                    if await self.run_upload_worker(self.pool.publish_next):
                        self.clear_cache()
                ticks += 1
                if ticks >= 120:
                    await asyncio.to_thread(self.pool.prune)
                    ticks = 0
            except Exception as exc:
                logger.warning('Managed desktop queue retry: %s', type(exc).__name__)
                await asyncio.sleep(2)
            await asyncio.sleep(.5)

    async def wait(self, job, *, seconds=36):
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds
        while loop.time() < end:
            try:
                result = await asyncio.to_thread(self.pool.status, job)
                if result is not None:
                    return result
            except Exception:
                return None    # Keep the durable job; never restart an already committed submission.
            await asyncio.sleep(.5)
        return None
