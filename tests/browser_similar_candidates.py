"""Opt-in isolated browser/HTTP/worker/SQL verification; no real AI calls."""
import asyncio
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import urlparse

dsn=urlparse(os.environ.get('SMARTHR_TEST_DATABASE_URL',''))
assert dsn.hostname in {'127.0.0.1','localhost'} and dsn.path in {'/qa','/smarthr_qa'}

from fastapi import Request
import uvicorn
import main
from services.task_queue import SearchWorker
from test_durable_search import queue_db  # noqa: F401
from test_folder_tag_e2e import flow, seed  # noqa: F401


def test_zero_exact_results_offer_scoped_local_similar_profiles(flow,monkeypatch):
    seed(flow)
    async def actor(request: Request):
        user=flow.db.get_hr_task_user(7,1)
        user['full_name']='Fictional Recruiter'
        return user
    main.app.dependency_overrides[main.require_auth]=actor
    async def current(request,_token):return await actor(request)
    monkeypatch.setattr(main,'get_current_user',current)
    monkeypatch.setattr(main,'extract_standardized_keywords_from_jd',lambda *a:{'success':True,'all_keywords':['Figma']})
    monkeypatch.setattr(main,'extract_keywords_for_single_query',lambda query,*a:{'success':True,'optimized_query':query})
    async def unexpected(*a,**k):raise AssertionError('No scorecard calls for known strict failures or local suggestions')
    monkeypatch.setattr(main,'analyze_resume_with_hr_scorecard',unexpected)
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=port,lifespan='off',log_level='error'))
    async def serve():
        worker=SearchWorker(lambda:flow.db,main.run_hr_scorecard_task,poll_seconds=.02)
        worker.start()
        try:await server.serve(sockets=[listener])
        finally:await worker.stop()
    thread=threading.Thread(target=lambda:asyncio.run(serve()),daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.1)
        assert server.started
        script=Path(__file__).with_suffix('.cjs')
        result=subprocess.run(['node',str(script),f'http://127.0.0.1:{port}'],cwd=script.parents[1],
            capture_output=True,text=True,timeout=180)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(timeout=10);listener.close()
        assert not thread.is_alive()
