import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

import main
from database import DatabaseManager
from services.analysis_quality import verified_scorecard
from services.task_lease import PermanentTaskError, TaskLeaseLost, current_lease
from services.task_queue import SearchWorker, gather_candidates


def assessment():
    return {'success': True, 'input_source': 'full_document', 'scorecard_type': 'comprehensive_hr',
            'match_score': 82, 'hr_scorecard': {'candidate_overview': {'name': 'Synthetic CV'},
                                            'score_breakdown': {'technical_skills': {}}}}


@pytest.mark.parametrize('change', [
    {'success': False}, {'input_source': 'snippet'}, {'input_source': None},
    {'scorecard_type': 'basic_fallback'}, {'scorecard_type': 'error'},
    {'match_score': float('nan')}, {'match_score': float('inf')},
    {'match_score': True}, {'match_score': '82'}, {'match_score': 101},
    {'match_score': -1}, {'hr_scorecard': {}}, {'hr_scorecard': None},
])
def test_incomplete_or_invented_assessment_is_not_verified(change):
    assert not verified_scorecard({**assessment(), **change})


def test_full_document_assessment_is_verified():
    assert verified_scorecard(assessment())
    assert verified_scorecard({**assessment(), 'scorecard_type': 'split_approach'})


def test_worker_binds_lease_and_renews_while_processing():
    async def scenario():
        database = MagicMock()
        database.renew_hr_task_lease.return_value = True
        async def execute(payload):
            assert current_lease.get() == ('qa-task', 'qa-token')
            await asyncio.sleep(.025)
            return {'success': True}
        worker = SearchWorker(lambda: database, execute, heartbeat_seconds=.005, lease_seconds=1)
        await worker.process(database, {'task_id': 'qa-task', 'lease_token': 'qa-token',
                             'attempt_count': 1, 'task_payload': {}})
        assert current_lease.get() is None
        assert database.renew_hr_task_lease.call_count >= 1
        database.release_hr_task.assert_not_called()
    asyncio.run(scenario())


@pytest.mark.parametrize('error,permanent', [(RuntimeError('transient'), False),
    (PermanentTaskError('bad input'), True), (main.HTTPException(403, 'not authorized'), True)])
def test_worker_failure_has_bounded_database_retry(error, permanent):
    async def scenario():
        database = MagicMock()
        worker = SearchWorker(lambda: database, AsyncMock(side_effect=error))
        await worker.process(database, {'task_id': 'qa-task', 'lease_token': 'qa-token',
                             'attempt_count': 1, 'task_payload': {}})
        args = database.release_hr_task.call_args.args
        assert args[:2] == ('qa-task', 'qa-token') and args[-2:] == (3, permanent)
        assert 'transient' not in args[2] and 'bad input' not in args[2]
    asyncio.run(scenario())


def test_lost_heartbeat_cancels_work_without_releasing_someone_elses_lease():
    async def scenario():
        database = MagicMock()
        database.renew_hr_task_lease.return_value = False
        cancelled = asyncio.Event()
        async def execute(payload):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        worker = SearchWorker(lambda: database, execute, heartbeat_seconds=.005, lease_seconds=1)
        await worker.process(database, {'task_id': 'qa-task', 'lease_token': 'qa-token',
                             'attempt_count': 1, 'task_payload': {}})
        assert cancelled.is_set()
        database.release_hr_task.assert_not_called()
    asyncio.run(scenario())


def test_shutdown_leaves_durable_lease_for_recovery_and_cancels_siblings():
    async def scenario():
        database = MagicMock()
        started, cancelled = asyncio.Event(), asyncio.Event()
        async def execute(payload):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        worker = SearchWorker(lambda: database, execute)
        task = asyncio.create_task(worker.process(database, {'task_id': 'qa-task',
            'lease_token': 'qa-token', 'attempt_count': 1, 'task_payload': {}}))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()
        database.release_hr_task.assert_not_called()
    asyncio.run(scenario())


def test_failed_candidate_batch_does_not_leave_paid_sibling_work_running():
    async def scenario():
        cancelled = asyncio.Event()
        async def good():
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        async def bad():
            await asyncio.sleep(.01)
            raise TaskLeaseLost('expired')
        with pytest.raises(TaskLeaseLost):
            await gather_candidates([good(), bad()])
        assert cancelled.is_set()
    asyncio.run(scenario())


def test_job_deadline_releases_capacity_without_automatic_paid_retry():
    async def scenario():
        database = MagicMock()
        cancelled = asyncio.Event()
        async def stalled(payload):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()
        worker = SearchWorker(lambda: database, stalled, timeout_seconds=.01)
        await worker.process(database, {'task_id': 'qa-task', 'lease_token': 'qa-token',
            'attempt_count': 1, 'task_payload': {}})
        assert cancelled.is_set()
        assert database.release_hr_task.call_args.args[-1] is True
    asyncio.run(scenario())


def test_task_payload_committed_with_pending_record_and_ack_never_starts_http(monkeypatch):
    monkeypatch.setenv('USE_CLOUD_TASKS', 'false')
    database = MagicMock()
    database.get_task_status.return_value = {'user_id': '7', 'status': 'pending'}
    with patch.object(main, 'get_db_manager', return_value=database), patch('requests.post') as http:
        assert main.save_task_to_database('qa-task', 'Original JD', 'Position', 10, '7', 1)
        assert database.save_hr_scorecard_task.call_args.kwargs['task_payload'] == {
            'task_id': 'qa-task', 'user_data': {'id': '7'}, 'company_id': 1}
        assert main.create_hr_scorecard_task('qa-task', 'JD', 'Position', 10, {'id': 7})['queue_name'] == 'postgresql'
        http.assert_not_called()


def run_mock_search(*, unreadable_first=False, db_failure=False, criteria='Original requirements',
                    requested=2, pool_size=4, eligible_every=1):
    database = MagicMock()
    database.claim_hr_scorecard_task.return_value = {'task_id': 'qa-task', 'query': criteria,
        'job_title': 'QA', 'result_count': requested, 'user_id': '7', 'company_id': None}
    database.get_cached_resume_analysis.return_value = None
    database.complete_hr_task.return_value = 123
    if db_failure:
        database.complete_hr_task.side_effect = RuntimeError('database unavailable')
    docs = [SimpleNamespace(id=str(i), relevance_score=1,
        document=SimpleNamespace(name=f'{i}.txt', derived_struct_data={
            'link': f'gs://qa-bucket/{i}.txt', 'snippets': [{'snippet': 'Python developer in Dubai, 8 years'}]}))
        for i in range(pool_size)]
    search = MagicMock()
    search.search.return_value = SimpleNamespace(results=docs)
    async def analyze(content, query, *args, **kwargs):
        assert query == criteria, 'The full original JD must reach the assessment'
        scored = assessment()
        index = int(kwargs['file_path'].split('.')[0])
        scored['hr_scorecard']['candidate_overview'].update(
            location='Dubai, UAE' if index % eligible_every == 0 else 'Chennai, India',
            experience_years='5 Years')
        return scored
    def content(path, user):
        if unreadable_first and path == '0.txt':
            return None, b'scanned PDF'
        return f'Complete fictional CV: {path}', b'fictional'
    async def run():
        return await main.run_hr_scorecard_task({'task_id': 'qa-task', 'user_data': {'id': 7,
            'user_type': 'super_admin'}})
    with patch.object(main, 'get_db_manager', return_value=database), \
         patch.object(main, '_prepare_search_input', side_effect=lambda kind, *args: {'all_keywords': ['Python']} if kind == 'keywords' else {'optimized_query': 'Python'}), \
         patch.object(main, 'get_search_client', return_value=search), \
         patch.object(main, 'create_company_search_request', return_value={}), \
         patch.object(main, 'get_company_resources', return_value=('qa-bucket', 'qa-store')), \
         patch.object(main, '_get_storage_client') as storage, \
         patch.object(main, 'using_deepseek', return_value=True), \
         patch.object(main, 'get_file_content_and_bytes_from_gcs', side_effect=content), \
         patch.object(main, 'send_file_to_gemini_directly') as binary, \
         patch.object(main, 'analyze_resume_with_hr_scorecard', side_effect=analyze) as llm:
        storage.return_value.bucket.return_value.blob.return_value.generation = 'qa-generation'
        result = asyncio.run(run())
        binary.assert_not_called()
    return result, database, llm


def test_unreadable_cv_is_not_scored_from_snippet_and_valid_replacements_fill_count():
    result, database, llm = run_mock_search(unreadable_first=True)
    assert result['results'] == 2 and llm.call_count == 2
    rows = database.complete_hr_task.call_args.args[1]
    assert {row['file_path'] for row in rows} == {'1.txt', '2.txt'}
    assert all(row['gemini_analysis']['input_source'] == 'full_document' for row in rows)


def test_candidate_batch_stops_without_scoring_unneeded_cvs():
    result, database, llm = run_mock_search()
    assert result['results'] == 2 and llm.call_count == 2


def test_ten_requested_candidates_are_ten_exact_matches_when_available():
    result, database, llm = run_mock_search(criteria='Python developer based in Dubai with 3-6 years experience',
        requested=10, pool_size=40, eligible_every=3)
    rows = database.complete_hr_task.call_args.args[1]
    assert result['results'] == 10 and result['exact_match_shortfall'] == 0
    assert all(row['gemini_analysis']['hr_scorecard']['candidate_overview']['location'] == 'Dubai, UAE' for row in rows)
    assert all(not row['criteria_match']['misses'] for row in rows)
    assert llm.call_count < 40


def test_shortfall_is_honest_and_never_filled_with_nonmatching_candidates():
    result, database, llm = run_mock_search(criteria='Python developer based in Dubai with 3-6 years experience',
        requested=10, pool_size=12, eligible_every=3)
    rows = database.complete_hr_task.call_args.args[1]
    assert result['results'] == 4 and result['exact_match_shortfall'] == 6
    assert all(not row['criteria_match']['misses'] for row in rows)


def test_database_failure_is_never_reported_as_a_completed_search():
    with pytest.raises(main.HTTPException) as exc:
        run_mock_search(db_failure=True)
    assert exc.value.status_code == 500


def test_slow_status_database_does_not_block_the_api_event_loop():
    import time
    async def scenario():
        database = MagicMock()
        def slow_status(task_id):
            time.sleep(.05)
            return {'user_id': '7', 'status': 'processing'}
        database.get_task_status.side_effect = slow_status
        with patch.object(main, 'get_db_manager', return_value=database):
            task = asyncio.create_task(main.get_hr_scorecard_task_status('qa-task', {'id': '7', 'user_type':'super_admin'}))
            await asyncio.sleep(.005)
            assert not task.done(), 'A blocking database call prevented other API work'
            assert (await task)['status'] == 'processing'
    asyncio.run(scenario())


@pytest.fixture
def queue_db():
    dsn = os.getenv('SMARTHR_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('Requires an isolated PostgreSQL test database')
    import psycopg2
    from psycopg2 import sql
    from psycopg2.pool import ThreadedConnectionPool
    schema = 'smarthr_qa_' + uuid.uuid4().hex
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    with admin.cursor() as cursor:
        cursor.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    database = DatabaseManager.__new__(DatabaseManager)
    database.pool = ThreadedConnectionPool(1, 12, dsn=dsn, options=f'-csearch_path={schema},public')
    database._test_schema = schema
    try:
        with database.get_cursor() as (cursor, _):
            cursor.execute('''
                CREATE TABLE tenant_companies (id SERIAL PRIMARY KEY, company_code TEXT, company_name TEXT, max_searches INTEGER);
                CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, user_type TEXT, is_active BOOLEAN);
                CREATE TABLE user_companies (user_id INTEGER, company_id INTEGER);
                CREATE TABLE search_history (id SERIAL PRIMARY KEY, search_query TEXT, job_title TEXT, result_count INTEGER,
                    created_by_user_id INTEGER, company_id INTEGER, search_method TEXT, search_timestamp TIMESTAMP DEFAULT NOW());
                CREATE TABLE search_results (id SERIAL PRIMARY KEY, search_id INTEGER, candidate_name TEXT, candidate_email TEXT,
                    candidate_phone TEXT, candidate_location TEXT, position_applied TEXT, experience_years INTEGER,
                    match_score INTEGER CHECK (match_score BETWEEN 0 AND 100), match_status TEXT, file_path TEXT,
                    gemini_analysis JSONB, hr_scorecard JSONB, company_id INTEGER, uploaded_by_user_id INTEGER,
                    UNIQUE (search_id, file_path));
                CREATE TABLE hr_scorecard_tasks (task_id TEXT PRIMARY KEY, query TEXT, job_title TEXT, result_count INTEGER,
                    user_id TEXT, company_id INTEGER, status TEXT, progress TEXT, error_message TEXT, search_id INTEGER,
                    created_at TIMESTAMP, updated_at TIMESTAMP, completed_at TIMESTAMP);
            ''')
        database.ensure_task_queue_schema()
        yield database
    finally:
        database.pool.closeall()
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        admin.close()


def enqueue(database, task_id='qa-task'):
    database.save_hr_scorecard_task(task_id, 'Full JD', 'QA', 10, '7',
        task_payload={'task_id': task_id, 'user_data': {'id': 7}})


def expire(database, task_id):
    with database.get_cursor() as (cursor, _):
        cursor.execute("UPDATE hr_scorecard_tasks SET lease_expires_at=NOW()-interval '1 second' WHERE task_id=%s", (task_id,))


def test_postgres_claim_is_exclusive_and_global_concurrency_is_bounded(queue_db):
    from concurrent.futures import ThreadPoolExecutor
    for i in range(8):
        enqueue(queue_db, f'qa-{i}')
    with ThreadPoolExecutor(max_workers=8) as executor:
        claims = list(executor.map(lambda _: queue_db.claim_next_hr_task(max_active=2), range(8)))
    claimed = [job for job in claims if job]
    assert len(claimed) == len({job['task_id'] for job in claimed}) == 2
    assert not queue_db.claim_hr_scorecard_task(claimed[0]['task_id'])


def test_search_quota_is_atomic_under_concurrent_history_writes(queue_db):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    with queue_db.get_cursor() as (cursor, _):
        cursor.execute("INSERT INTO tenant_companies(id, max_searches) VALUES (1, 1)")

    start = threading.Barrier(2)

    def save_search():
        start.wait()
        try:
            queue_db.save_search_history('Fictional role', 'QA', 0, 7, company_id=1)
            return 'saved'
        except Exception as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: save_search(), range(2)))

    assert outcomes.count('saved') == 1
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('SELECT COUNT(*) AS count FROM search_history WHERE company_id=1')
        assert cursor.fetchone()['count'] == 1


def test_postgres_crash_recovery_fences_the_old_attempt(queue_db):
    enqueue(queue_db)
    first = queue_db.claim_next_hr_task()
    expire(queue_db, first['task_id'])
    second = queue_db.claim_next_hr_task()
    assert second['task_id'] == first['task_id'] and second['lease_token'] != first['lease_token']
    assert second['attempt_count'] == 2
    assert not queue_db.renew_hr_task_lease(first['task_id'], first['lease_token'])
    assert not queue_db.release_hr_task(first['task_id'], first['lease_token'], 'stale')
    with pytest.raises(TaskLeaseLost):
        queue_db.complete_hr_task(first['task_id'], [], {}, first['lease_token'])
    token = current_lease.set((first['task_id'], first['lease_token']))
    try:
        with pytest.raises(TaskLeaseLost):
            queue_db.update_task_status(first['task_id'], {'status': 'completed'})
    finally:
        current_lease.reset(token)
    search = queue_db.complete_hr_task(second['task_id'], [], {'step': 'completed'}, second['lease_token'])
    assert queue_db.complete_hr_task(second['task_id'], [], {}, second['lease_token']) == search
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('SELECT count(*) AS n FROM search_history')
        assert cursor.fetchone()['n'] == 1


def test_postgres_result_failure_rolls_back_history_and_completion(queue_db):
    enqueue(queue_db)
    job = queue_db.claim_next_hr_task()
    broken = {'file_path': 'qa.txt', 'gemini_analysis': {**assessment(), 'match_score': 200}}
    with pytest.raises(Exception):
        queue_db.complete_hr_task(job['task_id'], [broken], {}, job['lease_token'])
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('SELECT count(*) AS n FROM search_history')
        assert cursor.fetchone()['n'] == 0
    assert queue_db.get_task_status(job['task_id'])['status'] == 'processing'


def test_postgres_retry_backoff_exhaustion_and_terminal_legacy_jobs(queue_db):
    enqueue(queue_db)
    queue_db.save_hr_scorecard_task('old-failed', 'JD', 'QA', 10, 7, status='failed')
    first = queue_db.claim_next_hr_task()
    assert queue_db.release_hr_task(first['task_id'], first['lease_token'], 'transient', max_attempts=2)
    assert not queue_db.claim_next_hr_task()
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute("UPDATE hr_scorecard_tasks SET next_attempt_at=NOW() WHERE task_id='qa-task'")
    second = queue_db.claim_next_hr_task(max_attempts=2)
    expire(queue_db, second['task_id'])
    assert not queue_db.claim_next_hr_task(max_attempts=2)
    assert queue_db.get_task_status('qa-task')['status'] == 'failed'
    assert queue_db.get_task_status('old-failed')['status'] == 'failed'


def test_postgres_revoked_or_cross_tenant_access_is_rejected(queue_db):
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute("INSERT INTO tenant_companies(id,company_code,company_name) VALUES (1,'first','First'),(2,'second','Second')")
        cursor.execute("INSERT INTO users VALUES (7,'qa@example.invalid','admin',true),(8,'super@example.invalid','super_admin',true)")
        cursor.execute('INSERT INTO user_companies VALUES (7,1)')
    assert queue_db.get_hr_task_user(7, 1)['company']['company_id'] == 1
    assert queue_db.get_hr_task_user(7, 2) is None
    assert queue_db.get_hr_task_user(7, None) is None
    assert queue_db.get_hr_task_user(8, None)['user_type'] == 'super_admin'
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('UPDATE users SET is_active=false WHERE id=7')
    assert queue_db.get_hr_task_user(7, 1) is None


def test_postgres_recovers_a_killed_process_without_losing_the_job(queue_db):
    import json
    import subprocess
    import sys
    import time
    enqueue(queue_db)
    code = '''
import json, os, time
from database import DatabaseManager
from psycopg2.pool import ThreadedConnectionPool
db = DatabaseManager.__new__(DatabaseManager)
db.pool = ThreadedConnectionPool(1, 2, dsn=os.environ['SMARTHR_TEST_DATABASE_URL'],
    options='-csearch_path=' + os.environ['SMARTHR_TEST_SCHEMA'] + ',public')
job = db.claim_next_hr_task(lease_seconds=2)
print(json.dumps({'task_id': job['task_id']}), flush=True)
time.sleep(30)
'''
    child = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, env={**os.environ, 'SMARTHR_TEST_SCHEMA': queue_db._test_schema})
    try:
        assert json.loads(child.stdout.readline())['task_id'] == 'qa-task'
        child.kill()
        child.wait(timeout=5)
        recovered = None
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and recovered is None:
            recovered = queue_db.claim_next_hr_task()
            if recovered is None:
                time.sleep(.1)
        assert recovered['task_id'] == 'qa-task' and recovered['attempt_count'] == 2
        assert queue_db.complete_hr_task('qa-task', [], {}, recovered['lease_token'])
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
