"""Relay synthetic tests to isolated disposable VPS containers over approved SSH."""
import base64
import os
from pathlib import Path
import re
import subprocess
import sys

here = Path(__file__).resolve().parent
root = here.parents[1]
host = os.environ['PILOT_BASELINE_SSH']
image = os.environ['PILOT_BASELINE_IMAGE']
assert re.fullmatch(r'[\w.-]+@[\w.-]+', host)
assert re.fullmatch(r'[\w.-]+:[\w.-]+', image)
paths = ('config.example.json', 'deploy/schema.sql', 'deploy/vps/schema-local-mode.sql',
         'tests/local-upload-pilot/handoff_vps.py')
payload = {Path(name).name: base64.b64encode((root/name).read_bytes()).decode() for name in paths}

stage = r'''
import base64, json, pathlib, secrets, subprocess, tempfile, time

tag='smarthr-assistqa-'+secrets.token_hex(5)
net=tag+'-net'
db=tag+'-db'
password=secrets.token_urlsafe(24)

def run(args, data=None):
    result=subprocess.run(args,capture_output=True,text=True,input=data,timeout=35)
    if result.returncode:
        raise RuntimeError('Fixture operation failed: '+args[1]+' '+result.stderr[-500:])
    return result.stdout.strip()

with tempfile.TemporaryDirectory(prefix=tag+'-') as temp:
    directory=pathlib.Path(temp)
    for name, data in payload.items():
        (directory/name).write_bytes(base64.b64decode(data))
    config=directory/'config.example.json'
    settings=json.loads(config.read_text())
    settings['upload']['allowed_extensions']=['.pdf','.doc','.docx']
    config.write_text(json.dumps(settings))
    config.chmod(0o644)
    run(['docker','network','create','--internal','--label','smarthr.qa='+tag,net])
    try:
        assert run(['docker','network','inspect','--format','{{.Internal}}',net])=='true'
        run(['docker','run','-d','--name',db,'--label','smarthr.qa='+tag,'--pull=never','--network',net,
             '--memory','384m','--cpus','1','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=144m',
             '-e','POSTGRES_USER=desktop_qa','-e','POSTGRES_DB=desktop_offload_qa',
             '-e','POSTGRES_PASSWORD='+password,'pgvector/pgvector:pg17'])
        for _ in range(25):
            if subprocess.run(['docker','exec',db,'pg_isready','-h','127.0.0.1','-U','desktop_qa',
                               '-d','desktop_offload_qa'],capture_output=True).returncode==0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Fixture database did not start')
        for schema in ('schema.sql','schema-local-mode.sql'):
            run(['docker','exec','-i',db,'psql','-X','-U','desktop_qa','-d','desktop_offload_qa',
                 '-v','ON_ERROR_STOP=1'],(directory/schema).read_text())
        env={'DB_HOST':db,'DB_PORT':'5432','DB_NAME':'desktop_offload_qa','DB_USER':'desktop_qa','DB_PASSWORD':password,
             'DISABLE_STARTUP_VALIDATION':'1','SMARTHR_LOCAL_MODE':'1','USE_CLOUD_TASKS':'false',
             'SMARTHR_BULK_EMBED_BATCH_SIZE':'8','SMARTHR_QUERY_EMBED_CACHE_MAX':'0',
             'SMARTHR_STORAGE_ROOT':'/tmp/smarthr-offload-fixtures','SMARTHR_EMBED_MODEL':'sentence-transformers/all-MiniLM-L6-v2',
             'SENTENCE_TRANSFORMERS_HOME':'/app/.st_cache','HF_HOME':'/app/.st_cache','HF_HUB_OFFLINE':'1',
             'PYTHONPATH':'/app','OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'1',
             'SECRET_KEY':secrets.token_hex(32)}
        options=['docker','run','--rm','-i','--name',tag,'--label','smarthr.qa='+tag,'--pull=never','--network',net,
                 '--read-only','--tmpfs','/tmp:rw,nosuid,mode=1777,size=128m','--cap-drop=ALL','--security-opt=no-new-privileges',
                 '--cpus=1.75','--memory=1600m','--memory-swap=1600m','--pids-limit=64',
                 '-v','smarthr_stcache:/app/.st_cache:ro','-v',str(config)+':/app/config.json:ro',
                 '-v',str(directory/'handoff_vps.py')+':/qa/handoff.py:ro']
        for k,v in env.items():
            options.extend(['-e',k+'='+v])
        status=subprocess.run(options+['--entrypoint','timeout',image,'210','python','-u','/qa/handoff.py'],timeout=220).returncode
    finally:
        for name in (tag,db):
            found=subprocess.run(['docker','inspect',name],capture_output=True,text=True)
            if found.returncode==0:
                assert json.loads(found.stdout)[0]['Config']['Labels']['smarthr.qa']==tag
                run(['docker','rm','-fv',name])
        assert json.loads(run(['docker','network','inspect',net]))[0]['Labels']['smarthr.qa']==tag
        run(['docker','network','rm',net])
    raise SystemExit(status)
'''
bootstrap = f'image={image!r}\npayload={payload!r}\n{stage}'
command = "python3 -u -c 'import sys,base64; exec(base64.b64decode(sys.stdin.buffer.readline()))'"
with subprocess.Popen(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8',
                       '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', host, command],
                      stdin=subprocess.PIPE) as ssh:
    try:
        ssh.stdin.write(base64.b64encode(bootstrap.encode()) + b'\n')
        ssh.stdin.flush()
        for line in sys.stdin.buffer:
            ssh.stdin.write(line)
            ssh.stdin.flush()
    except BrokenPipeError:
        pass
    finally:
        ssh.stdin.close()
    raise SystemExit(ssh.wait(timeout=240))
