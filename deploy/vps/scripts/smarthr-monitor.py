"""Local SmartHR health/capacity checks; no providers, email or automatic restarts."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

SERVICES = ('smarthr-app', 'smarthr-postgres')
STATE = Path('/var/lib/smarthr-monitor/state.json')


def inspect_snapshot():
    result = {'services': {}, 'health': False, 'deep_health': False, 'ai_skipped': False}
    disk = shutil.disk_usage('/opt/smarthr')
    result['disk_used_percent'] = round(100 * (1 - disk.free / disk.total), 2)
    try:
        output = subprocess.check_output(['docker', 'inspect', *SERVICES], text=True, timeout=10)
        for row in json.loads(output):
            name = row['Name'].lstrip('/')
            if name not in SERVICES:
                continue
            options = row['HostConfig'].get('LogConfig', {}).get('Config', {})
            result['services'][name] = {
                'running': row['State']['Running'],
                'healthy': row['State'].get('Health', {}).get('Status') == 'healthy',
                'memory_limit': row['HostConfig']['Memory'],
                'pids_limit': row['HostConfig'].get('PidsLimit') or 0,
                'log_rotation': bool(options.get('max-size') and options.get('max-file')),
                'oom_killed': row['State'].get('OOMKilled', False),
            }
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        pass
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for field, path in (('health', '/health'), ('deep_health', '/health/deep')):
        try:
            with opener.open('http://127.0.0.1:8081' + path, timeout=10) as response:
                body = json.load(response)
                result[field] = body.get('status') == 'healthy'
                if field == 'deep_health':
                    result['ai_skipped'] = body.get('checks', {}).get('llm', {}).get('status') == 'skipped'
        except (OSError, ValueError):
            pass
    return result


def evaluate(snapshot):
    critical, warnings = [], []
    for name in SERVICES:
        row = snapshot.get('services', {}).get(name, {})
        if not row.get('running') or not row.get('healthy') or row.get('oom_killed'):
            critical.append(name + ':unhealthy')
        if row.get('memory_limit', 0) <= 0 or row.get('pids_limit', 0) <= 0:
            warnings.append(name + ':resource_limits_missing')
        if not row.get('log_rotation'):
            warnings.append(name + ':log_rotation_missing')
    if not snapshot.get('health') or not snapshot.get('deep_health'):
        critical.append('readiness_unhealthy')
    if not snapshot.get('ai_skipped'):
        critical.append('readiness_ai_policy_unverified')
    used = snapshot.get('disk_used_percent', 100)
    if used >= 92:
        critical.append('disk_critical')
    elif used >= 80:
        warnings.append('disk_warning')
    return {'level': 'critical' if critical else 'warning' if warnings else 'healthy',
            'issues': sorted(critical + warnings)}


def record_transition(status, path=STATE):
    previous = None
    try:
        previous = json.loads(path.read_text())
    except (OSError, ValueError):
        pass
    if previous == status:
        return False
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + str(os.getpid()) + '.tmp')
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(status, stream, sort_keys=True)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    sys.stdout.write(json.dumps({'component': 'smarthr-monitor', **status}, sort_keys=True) + '\n')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Print a read-only check without saving state.')
    args = parser.parse_args()
    snapshot = inspect_snapshot()
    status = evaluate(snapshot)
    if args.check:
        sys.stdout.write(json.dumps({'status': status, 'snapshot': snapshot}, sort_keys=True) + '\n')
    else:
        record_transition(status)
    return 1 if status['level'] == 'critical' else 0


if __name__ == '__main__':
    raise SystemExit(main())
