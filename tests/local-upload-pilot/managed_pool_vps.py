"""Postgres-backed reservation rules for the disposable managed-worker pilot."""
import hashlib


class WorkerPool:
    def __init__(self, db):
        self.db = db
        with db.get_cursor() as (cur, _):
            cur.execute('''CREATE TABLE IF NOT EXISTS managed_qa_workers (
                id text PRIMARY KEY, company_id int NOT NULL REFERENCES tenant_companies(id),
                public_key bytea NOT NULL, enabled boolean NOT NULL DEFAULT true,
                ready boolean NOT NULL DEFAULT false, sequence bigint NOT NULL DEFAULT 0,
                seen_at timestamptz, assigned_at timestamptz);
                CREATE TABLE IF NOT EXISTS managed_qa_leases (
                job_id text NOT NULL, worker_id text NOT NULL REFERENCES managed_qa_workers(id),
                attempt smallint NOT NULL, deadline timestamptz NOT NULL,
                finished boolean NOT NULL DEFAULT false, PRIMARY KEY(job_id, attempt));
                CREATE INDEX IF NOT EXISTS managed_qa_busy ON managed_qa_leases(worker_id,deadline)
                    WHERE NOT finished;
                CREATE TABLE IF NOT EXISTS managed_qa_jobs (
                    id text PRIMARY KEY, owner_id int NOT NULL, company_id int NOT NULL,
                    bucket text NOT NULL, folder text NOT NULL, uris text[] NOT NULL,
                    state text NOT NULL, finished boolean NOT NULL DEFAULT false);''')

    def save_job(self, job_id, job):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''INSERT INTO managed_qa_jobs(id,owner_id,company_id,bucket,folder,uris,state,finished)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''', (job_id, job.owner, job.company, job.bucket, job.folder,
                    [doc.content.uri for doc in job.documents], job.state, job.finished))

    def jobs(self):
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT * FROM managed_qa_jobs')
            return cur.fetchall()

    def remaining(self, job):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''SELECT greatest(0, extract(epoch FROM max(deadline)-clock_timestamp())*1000)::int AS ms
                FROM managed_qa_leases WHERE job_id=%s AND NOT finished''', (job,))
            return cur.fetchone()['ms']

    def enroll(self, company, public_key):
        worker = hashlib.sha256(public_key).hexdigest()
        with self.db.get_cursor() as (cur, _):
            cur.execute('INSERT INTO managed_qa_workers(id,company_id,public_key) VALUES (%s,%s,%s)',
                        (worker, company, public_key))
        return worker

    def public_key(self, worker):
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT public_key FROM managed_qa_workers WHERE id=%s AND enabled', (worker,))
            row = cur.fetchone()
        return bytes(row['public_key']) if row else None

    def heartbeat(self, worker, sequence, ready):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''UPDATE managed_qa_workers SET sequence=%s, ready=%s, seen_at=clock_timestamp()
                WHERE id=%s AND enabled AND sequence < %s''', (sequence, ready, worker, sequence))
            return cur.rowcount == 1

    def revoke(self, company, worker):
        with self.db.get_cursor() as (cur, _):
            cur.execute('''UPDATE managed_qa_workers SET enabled=false, ready=false
                WHERE company_id=%s AND id=%s AND enabled''', (company, worker))
            if not cur.rowcount:
                return False
            cur.execute('UPDATE managed_qa_leases SET finished=true WHERE worker_id=%s AND NOT finished', (worker,))
            return True

    def reserve(self, company, job):
        with self.db.get_cursor() as (cur, _):
            cur.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (job,))
            cur.execute('''SELECT count(*) AS attempts, bool_or(NOT finished AND deadline > clock_timestamp()) AS active
                FROM managed_qa_leases WHERE job_id=%s''', (job,))
            current = cur.fetchone()
            if current['active'] or current['attempts'] >= 2:
                return None
            cur.execute('''SELECT w.id FROM managed_qa_workers w
                WHERE w.company_id=%s AND w.enabled AND w.ready
                  AND w.seen_at > clock_timestamp() - interval '20 seconds'
                  AND NOT EXISTS (SELECT 1 FROM managed_qa_leases l WHERE l.worker_id=w.id
                      AND (l.job_id=%s OR (NOT l.finished AND l.deadline > clock_timestamp())))
                ORDER BY w.assigned_at NULLS FIRST,w.id LIMIT 1 FOR UPDATE OF w SKIP LOCKED''', (company, job))
            row = cur.fetchone()
            if not row:
                return None
            worker = row['id']
            # Check again after locking under READ COMMITTED: a prior selection may have just committed.
            cur.execute('''SELECT 1 FROM managed_qa_leases WHERE worker_id=%s
                AND NOT finished AND deadline > clock_timestamp()''', (worker,))
            if cur.fetchone():
                return None
            cur.execute('UPDATE managed_qa_workers SET assigned_at=clock_timestamp() WHERE id=%s', (worker,))
            cur.execute('''INSERT INTO managed_qa_leases(job_id,worker_id,attempt,deadline)
                VALUES (%s,%s,%s,clock_timestamp()+interval '12 seconds')
                RETURNING extract(epoch FROM deadline)::float AS deadline''', (job, worker, current['attempts'] + 1))
            return worker, cur.fetchone()['deadline']

    def finish(self, job):
        with self.db.get_cursor() as (cur, _):
            cur.execute('UPDATE managed_qa_leases SET finished=true WHERE job_id=%s AND NOT finished', (job,))
            cur.execute('UPDATE managed_qa_jobs SET finished=true WHERE id=%s', (job,))
