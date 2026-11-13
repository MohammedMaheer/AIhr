"""Opt-in browser/HTTP/worker/SQL scope test; all providers are test doubles."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse

dsn = urlparse(os.environ.get('SMARTHR_TEST_DATABASE_URL', ''))
assert dsn.hostname in {'127.0.0.1', 'localhost'} and dsn.path in {'/qa', '/smarthr_qa'}, 'Use an isolated loopback QA database.'

from fastapi import Request
import uvicorn
import main
from services.llm_cache import PreparationCache
from services.task_queue import SearchWorker
from test_durable_search import assessment, queue_db  # noqa: F401
from test_folder_tag_e2e import flow, seed, FOLDER  # noqa: F401


def test_browser_folder_tag_date_payload_worker_and_results(flow, monkeypatch, tmp_path):
    rows = seed(flow)
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute("""INSERT INTO users VALUES (9,'peer@example.invalid','tenant_user',true);
            INSERT INTO user_companies VALUES (9,1);
            CREATE TABLE candidate_notes(search_result_id INTEGER PRIMARY KEY, comments TEXT NOT NULL DEFAULT '');
            CREATE TABLE candidate_actions(id SERIAL PRIMARY KEY, search_result_id INTEGER,
                action_type TEXT, action_status BOOLEAN, comments TEXT, updated_at TIMESTAMP);
            CREATE TABLE resume_text_recoveries(resume_embedding_id INTEGER, source_sha256 TEXT,
                text_sha256 TEXT, quality_status TEXT)""")
    seen, preparation_calls = [], []
    monkeypatch.setattr(main, '_jd_preparation_cache', PreparationCache())
    def keywords(query, tracker):
        preparation_calls.append('keywords')
        tracker.add_call('test-keywords', 'test-model', 1000, 200)
        return {'success': True, 'all_keywords': ['Figma']}
    def optimize(query, tracker):
        preparation_calls.append('query')
        tracker.add_call('test-query', 'test-model', 1000, 200)
        return {'success': True, 'optimized_query': query}
    monkeypatch.setattr(main, 'extract_standardized_keywords_from_jd', keywords)
    monkeypatch.setattr(main, 'extract_keywords_for_single_query', optimize)
    monkeypatch.setattr(flow.db, 'get_cached_resume_analysis', lambda *args, **kwargs: None)
    monkeypatch.setattr(flow.db, 'save_cached_resume_analysis', lambda *args, **kwargs: None)
    async def score(text, *args, **kwargs):
        assert 'Fictional candidate' in text
        seen.append(kwargs['file_path'])
        result = assessment()
        result['hr_scorecard']['candidate_overview'].update(name='Fictional candidate', position_applied_for='Designer', experience_years=5)
        return result
    monkeypatch.setattr(main, 'analyze_resume_with_hr_scorecard', score)
    monkeypatch.setattr(main, 'using_deepseek', lambda: True)
    async def actor(request: Request):
        user_id = int(request.headers.get('X-Fixture-User', '7'))
        assert user_id in (7, 9)
        user = flow.db.get_hr_task_user(user_id, 1)
        user['full_name'] = 'Fictional Recruiter'
        return user
    main.app.dependency_overrides[main.require_auth] = actor
    async def current_actor(request, _token):
        return await actor(request)
    monkeypatch.setattr(main, 'get_current_user', current_actor)
    def paths(predicate):
        return sorted(row['folder'] + '/' + row['filename'] for row in rows if row['company_id'] == 1 and predicate(row))
    scenarios = [
        {'name': 'received', 'folders': [FOLDER], 'tags': ['UI design'], 'basis': 'received', 'from': '2026-04-01', 'to': '2026-04-30',
         'expected': paths(lambda row: row['original_filename'] == 'within.docx')},
        {'name': 'uploaded', 'folders': [FOLDER], 'tags': ['UI design'], 'basis': 'uploaded', 'from': '2026-04-01', 'to': '2026-04-30',
         'expected': paths(lambda row: row['folder'] == FOLDER and row['original_filename'] == 'same-name.docx')},
        {'name': 'multiple', 'folders': [FOLDER, FOLDER+'-old'], 'tags': ['UI design', 'Web design'], 'basis': 'uploaded',
         'expected': paths(lambda row: (row['folder'] in [FOLDER, FOLDER+'/sub', FOLDER+'-old']) and bool(set(row['search_tags']) & {'UI design', 'Web design'}))},
        {'name': 'empty', 'folders': [FOLDER], 'tags': ['Finance and accounting'], 'basis': 'received', 'from': '2026-04-01', 'to': '2026-04-30', 'expected': []},
    ]
    fixture = tmp_path / 'scopes.json'
    fixture.write_text(json.dumps(scenarios), encoding='utf-8')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1', port=port, lifespan='off', log_level='error'))
    async def serve():
        worker = SearchWorker(lambda: flow.db, main.run_hr_scorecard_task, poll_seconds=.02)
        worker.start()
        try:
            await server.serve(sockets=[listener])
        finally:
            await worker.stop()
    thread = threading.Thread(target=lambda: asyncio.run(serve()), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        assert server.started
        script = Path(__file__).with_suffix('.cjs')
        result = subprocess.run(['node', str(script), f'http://127.0.0.1:{port}', str(fixture)],
            cwd=script.parents[1], capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert sorted(preparation_calls) == ['keywords', 'query'], 'Identical JD preparation should be shared by both recruiters only within their tenant'
        expected = set().union(*(set(case['expected']) for case in scenarios))
        assert set(seen) == expected
        with flow.db.get_cursor() as (cursor, _):
            cursor.execute("SELECT count(*) AS count FROM hr_scorecard_tasks WHERE status='completed'")
            assert cursor.fetchone()['count'] == 10
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
