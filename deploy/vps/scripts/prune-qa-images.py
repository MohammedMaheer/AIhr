#!/usr/bin/env python3
"""Remove only reviewed, unreferenced SmartHR test images and exclusive ancestors."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

QA_TAG = re.compile(r'smarthr-app:clean-[0-9]{8}t[0-9]{6}z-qa')
PINNED_QA = {'smarthr-app:clean-20261111t103729z-qa'}
QA_HISTORY = [
    '/bin/sh -c #(nop)  USER appuser',
    '/bin/sh -c python -m pip install pytest==8.4.1 httpx==0.28.1 && python -m pip check',
    '/bin/sh -c #(nop)  USER root',
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def image_record(row):
    return {key: row.get(key) for key in
            ('Id', 'Parent', 'RepoTags', 'RepoDigests', 'Created', 'Size', 'RootFS')}


def container_record(row):
    return {'id': row['Id'], 'image_id': row['Image'], 'reference': row['Config']['Image'],
            'started': row['State']['StartedAt'],
            'mounts': sorted(row['Mounts'], key=lambda m: m['Destination'])}


def created(row):
    return dt.datetime.fromisoformat(row['Created'].replace('Z', '+00:00')).timestamp()


def plan(images, containers, history, now=None, references=()):
    now = time.time() if now is None else now
    images = sorted(images, key=lambda row: row['Id'])
    containers = sorted(containers, key=lambda row: row['id'])
    by_id = {r['Id']: r for r in images}
    by_tag = {t: r for r in images for t in r['RepoTags'] or []}
    children = {r['Id']: set() for r in images}
    for row in images:
        if row['Parent'] in children:
            children[row['Parent']].add(row['Id'])
    qa = sorted([r for r in images if len(r['RepoTags'] or []) == 1
                 and QA_TAG.fullmatch(r['RepoTags'][0])], key=created)
    protected = {r['Id'] for r in qa[:1] + qa[-2:]}
    protected.update(r['image_id'] for r in containers)
    protected.update(r['Id'] for r in images if set(r['RepoTags'] or []) & PINNED_QA)
    protected.update(r['Id'] for r in images if any(
        name in text for name in [r['Id'], *(r['RepoTags'] or []), *(r['RepoDigests'] or [])]
        for text in references))
    selected = {}
    for row in qa:
        # A local self-digest is an alias of this image, not an external registry reference.
        if (row['Id'] in protected or any(d != 'smarthr-app@' + row['Id'] for d in row['RepoDigests'] or [])
                or children[row['Id']]
                or now - created(row) < 72 * 3600):
            continue
        base = by_tag.get(row['RepoTags'][0][:-3])
        if not base:
            continue
        before, after = base['RootFS']['Layers'], row['RootFS']['Layers']
        if (base['RootFS']['Type'] != 'layers' or row['RootFS']['Type'] != 'layers'
                or after[:len(before)] != before or len(after) != len(before) + 1
                or not 0 < row['Size'] - base['Size'] < 32 * 1024**2):
            continue
        qa_history, base_history = history(row['Id']), history(base['Id'])
        if not base_history or qa_history != QA_HISTORY + base_history:
            continue
        selected[row['Id']] = {'image': row, 'reason': 'verified test-only leaf',
                               'retained_base_id': base['Id'],
                               'history_sha256': digest(qa_history)}
    # Only walk parents of verified QA leaves. Shared or tagged ancestry is retained.
    changed = True
    while changed:
        changed = False
        for identifier in list(selected):
            parent = by_id.get(by_id[identifier]['Parent'])
            if (not parent or parent['Id'] in selected or parent['Id'] in protected
                    or parent['RepoTags'] or parent['RepoDigests']
                    or now - created(parent) < 72 * 3600
                    or not children[parent['Id']].issubset(selected)):
                continue
            selected[parent['Id']] = {'image': parent, 'reason': 'exclusive untagged QA ancestor'}
            changed = True
    remaining = set(selected)
    ordered = []
    while remaining:
        leaves = sorted(i for i in remaining if not children[i] & remaining)
        if not leaves:
            raise RuntimeError('Image graph cycle; cleanup refused')
        ordered.extend(selected[i] for i in leaves)
        remaining.difference_update(leaves)
    return {'schema': 1, 'image_graph_sha256': digest(images), 'references_sha256': digest(sorted(references)),
            'containers': containers,
            'selected': ordered, 'retained_ids': sorted(set(by_id) - set(selected)),
            'policy': 'Keep all production/foreign images, multi-tag images, QA baseline/newest two, pinned QA and container references'}


def execute(value, expected, inspect, containers, remove, record=lambda event: None, retained_ids=None):
    if expected != digest(value):
        raise RuntimeError('Cleanup plan differs from reviewed digest')
    removed = []
    for item in value['selected']:
        if sorted(containers(), key=lambda row: row['id']) != value['containers']:
            raise RuntimeError('Container identity changed; stop cleanup')
        row = item['image']
        if inspect(row['Id']) != row:
            raise RuntimeError('Image metadata/tags changed; stop cleanup')
        record({'phase': 'removal-start', 'id': row['Id']})
        # Immutable IDs plus Docker's no-force guard protect retags/container races.
        remove(row['Id'])
        removed.append(row['Id'])
        record({'phase': 'removed', 'id': row['Id']})
    available = retained_ids() if retained_ids else {i for i in value['retained_ids'] if inspect(i) is not None}
    if not set(value['retained_ids']).issubset(available):
        raise RuntimeError('A retained image is missing; investigate without restarting apps')
    if sorted(containers(), key=lambda row: row['id']) != value['containers']:
        raise RuntimeError('Container identity changed during cleanup')
    return removed


def out(args):
    return subprocess.check_output(args, text=True, timeout=180).strip()


def containers():
    ids = out(['docker', 'ps', '-aq']).split()
    return [container_record(r) for r in json.loads(out(['docker', 'inspect', *ids]))] if ids else []


def images():
    ids = sorted(set(out(['docker', 'image', 'ls', '-aq', '--no-trunc']).split()))
    result = []
    for start in range(0, len(ids), 50):
        result.extend(image_record(r) for r in json.loads(out(['docker', 'image', 'inspect', *ids[start:start + 50]])))
    return result


def inspect(identifier):
    result = subprocess.run(['docker', 'image', 'inspect', identifier], capture_output=True, text=True, timeout=90)
    return image_record(json.loads(result.stdout)[0]) if result.returncode == 0 else None


def history(identifier):
    return [json.loads(line) for line in out(['docker', 'history', '--no-trunc', '--format',
                                            '{{json .CreatedBy}}', identifier]).splitlines()]


def references():
    """Configuration content is used only for pins/digests, never logged."""
    files = set()
    for directory in ('/etc/systemd/system', '/etc/cron.d', '/var/spool/cron/crontabs'):
        files.update(Path(directory).rglob('*'))
    for pattern in ('*/docker-compose*.yml', '*/docker-compose*.yaml', '*/compose*.yml',
                    '*/compose*.yaml', '*/deploy/*.yml'):
        files.update(Path('/opt').glob(pattern))
    files.update(Path('/opt/smarthr/ops').glob('*.py'))
    files.update(Path('/opt/smarthr/ops').glob('*.sh'))
    files.add(Path('/opt/smarthr/.env'))
    texts = []
    for path in sorted(files):
        try:
            if path.is_file() and path.stat().st_size < 2 * 1024**2:
                texts.append(path.read_text(errors='replace'))
        except OSError:
            raise RuntimeError('Cannot inspect configuration pins; cleanup refused') from None
    return texts


def remove(identifier):
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', identifier):
        raise ValueError('Only immutable image IDs may be removed')
    subprocess.run(['docker', 'image', 'rm', '--no-prune', identifier],
                   capture_output=True, text=True, check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-plan-sha256')
    args = parser.parse_args()
    if args.apply and not re.fullmatch('[a-f0-9]{64}', args.expected_plan_sha256 or ''):
        parser.error('--apply requires --expected-plan-sha256 from a reviewed dry run')
    import fcntl
    os.nice(15)
    lock = Path('/var/lib/vps-artifact-retention/.lock')
    lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if lock.is_symlink():
        raise ValueError('Unsafe retention lock')
    with lock.open('a') as stream:
        os.chmod(lock, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        value = plan(images(), containers(), history, references=references())
        proof = digest(value)
        if not args.apply:
            print(json.dumps({'applied': False, 'plan': value, 'plan_sha256': proof}))
            return
        if proof != args.expected_plan_sha256:
            raise RuntimeError('Image graph/container plan changed; review a fresh dry run')
        directory = Path('/opt/smarthr/ops/image-cleanup')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.resolve() != directory:
            raise ValueError('Unsafe receipt directory')
        os.chmod(directory, 0o700)
        receipt = directory / (str(time.time_ns()) + '.jsonl')
        before = shutil.disk_usage('/opt/smarthr').free
        with receipt.open('x') as log:
            os.chmod(receipt, 0o600)
            def record(event):
                log.write(json.dumps(event) + '\n'); log.flush(); os.fsync(log.fileno())
            record({'phase': 'reviewed-plan', 'plan_sha256': proof, 'plan': value})
            removed = execute(value, proof, inspect, containers, remove, record,
                              lambda: set(out(['docker', 'image', 'ls', '-aq', '--no-trunc']).split()))
            result = {'applied': True, 'plan_sha256': proof, 'removed_ids': removed,
                      'retained_images_verified': len(value['retained_ids']),
                      'free_bytes_before': before, 'free_bytes_after': shutil.disk_usage('/opt/smarthr').free,
                      'receipt': str(receipt)}
            record({'phase': 'completed', **result})
        print(json.dumps(result))


if __name__ == '__main__':
    main()
