"""Opt-in real HTTP/browser/SQL flow. Run explicitly with an isolated test database.

Authentication is fixture-provided; embedding vectors are deterministic test values.
CV parsing, private file storage, application APIs, SQL and UI are real. No paid AI.
"""
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from unittest.mock import AsyncMock
from urllib.parse import urlparse

dsn = urlparse(os.environ.get('SMARTHR_TEST_DATABASE_URL', ''))
assert dsn.hostname in {'127.0.0.1', 'localhost'} and dsn.path in {'/qa', '/smarthr_qa'}, 'Use a dedicated loopback QA database.'

import uvicorn
from docx import Document

import main
from test_durable_search import queue_db  # noqa: F401
from test_job_applications import job_app_flow  # noqa: F401
from vps_local import discovery_shim as index

REAL_UPLOAD = main._run_resume_upload
REAL_QUOTA_CHECK = main._check_resume_upload_limit


def test_browser_application_upload_review_and_interview(job_app_flow, monkeypatch, tmp_path):
    flow = job_app_flow
    with flow.db.get_cursor() as (cursor, _):
        cursor.execute('''ALTER TABLE tenant_companies ADD COLUMN subscription_plan TEXT DEFAULT 'basic',
            ADD COLUMN max_users INTEGER DEFAULT 10, ADD COLUMN max_resumes INTEGER DEFAULT 1000;
            ALTER TABLE resume_embeddings ADD COLUMN file_size INTEGER, ADD COLUMN content_type TEXT,
            ADD COLUMN extracted_text TEXT, ADD COLUMN text_length INTEGER, ADD COLUMN embedding vector(3),
            ADD COLUMN candidate_years NUMERIC, ADD COLUMN candidate_location TEXT,
            ADD COLUMN candidate_languages TEXT[], ADD COLUMN candidate_skills TEXT[],
            ADD COLUMN profile_source TEXT, ADD COLUMN profile_updated_at TIMESTAMP,
            ADD COLUMN embedded_at TIMESTAMP, ADD COLUMN embed_model TEXT, ADD COLUMN extraction_error TEXT,
            ADD COLUMN search_tags TEXT[] DEFAULT '{}', ADD COLUMN source_uploaded_at TIMESTAMP,
            ADD COLUMN source_received_at TIMESTAMPTZ;
            CREATE UNIQUE INDEX browser_embedding_identity ON resume_embeddings
            (storage_bucket,folder,filename,(COALESCE(company_id,0)));''')
    monkeypatch.setattr(main, '_run_resume_upload', REAL_UPLOAD)
    monkeypatch.setattr(main, '_check_resume_upload_limit', REAL_QUOTA_CHECK)
    monkeypatch.setattr(main, '_resume_upload_slots', asyncio.Semaphore(2))
    monkeypatch.setattr(main, 'get_company_resources', lambda user=None: ('jobs-one-bucket', 'fixture-store'))
    monkeypatch.setattr(index, '_get_pool', lambda: flow.db.pool)
    monkeypatch.setattr(index, '_advanced_schema_ensured', True)
    monkeypatch.setattr(index, '_embed_query', lambda text: [1, 0, 0])
    flow.actor['user']['full_name'] = 'Fictional Manager'
    flow.actor['user']['company']['company_name'] = 'Fictional Hiring Co'
    monkeypatch.setattr(main, 'get_current_user', AsyncMock(return_value=flow.actor['user']))
    cv = tmp_path / 'fictional-browser-cv.docx'
    document = Document()
    document.add_heading('Fictional Browser Applicant', 0)
    document.add_paragraph('UI designer with five years of experience using Figma and user interface design. '
                           'Location: Dubai. English. This is an isolated QA fixture, not a real candidate.')
    document.save(cv)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app, host='127.0.0.1', port=port, lifespan='off', log_level='error'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        assert server.started, 'Isolated HTTP application did not start'
        script = Path(__file__).with_suffix('.cjs')
        result = subprocess.run(['node', str(script), f'http://127.0.0.1:{port}', str(cv)],
                                cwd=script.parents[1], capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        print(result.stdout)
        with flow.db.get_cursor() as (cursor, _):
            cursor.execute('SELECT count(*) AS count FROM job_applications WHERE status=%s', ('shortlisted',))
            assert cursor.fetchone()['count'] == 2
            cursor.execute('SELECT extracted_text,embedding,search_tags FROM resume_embeddings')
            rows = cursor.fetchall()
            assert len(rows) == 2
            assert all('Fictional Browser Applicant' in row['extracted_text'] and row['embedding']
                       and 'UI design' in row['search_tags'] for row in rows)
            cursor.execute('SELECT count(*) AS count FROM scheduled_interviews WHERE job_application_id IS NOT NULL')
            assert cursor.fetchone()['count'] == 2
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive(), 'Isolated HTTP server did not stop'
