#!/usr/bin/env python3
"""Dry-run-first removal of verified redundant SmartHR source copies only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

RELEASE_NAME = re.compile(r'review-[a-f0-9]{7,40}-[0-9]{8}t[0-9]{6}z')
SYNTHETIC_CONFIG = {'gcs': {'bucket_name': 'fixture-bucket', 'default_folder': 'resume/',
    'credentials_path': '/nonexistent/service-account.json'},
    'vector_search': {'project_id': 'fixture', 'datastore_id': 'fixture', 'location': 'global'}}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_targets(stage, info):
    hashes = info.get('source_hashes')
    if not isinstance(hashes, dict) or not hashes or len(hashes) > 5000:
        return []
    for name, value in hashes.items():
        if (not isinstance(name, str) or not name or Path(name).is_absolute()
                or '..' in Path(name).parts or '\\' in name
                or Path(name).suffix.lower() in {'.pdf', '.doc', '.docx', '.rtf', '.odt'}
                or Path(name).name in {'.env', 'config.json', 'config.docker.json', 'service-account.json'}
                or not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value)):
            return []
    targets = []
    source = stage / 'source'
    if source.is_dir() and not source.is_symlink():
        valid = True
        for path in source.rglob('*'):
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                valid = False
                break
            if path.is_dir():
                continue
            name = path.relative_to(source).as_posix()
            if name in hashes and digest(path) == hashes[name]:
                continue
            if '__pycache__' in path.relative_to(source).parts and path.suffix == '.pyc':
                continue
            if name == 'config.json' and path.stat().st_size < 16_384:
                try:
                    if json.loads(path.read_text()) == SYNTHETIC_CONFIG:
                        continue
                except (ValueError, OSError):
                    pass
            valid = False
            break
        if valid:
            targets.append(source)
    archive = stage / 'source.tar.gz'
    if archive.is_file() and not archive.is_symlink():
        try:
            seen = set()
            with tarfile.open(archive) as bundle:
                for member in bundle:
                    if member.isdir():
                        continue
                    if (not member.isfile() or member.name not in hashes or member.name in seen
                            or member.size > 32 * 1024 * 1024):
                        raise ValueError('Archive is not the reviewed source snapshot')
                    stream = bundle.extractfile(member)
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != hashes[member.name]:
                        raise ValueError('Archive digest differs')
                    seen.add(member.name)
            if seen == set(hashes):
                targets.append(archive)
        except (ValueError, OSError, tarfile.TarError):
            pass
    return targets


def plan(root, containers):
    releases = root / 'releases'
    if releases.is_symlink() or releases.resolve().parent != root.resolve():
        raise ValueError('Unexpected releases directory')
    records = {}
    for stage in releases.iterdir():
        if stage.is_symlink() or not stage.is_dir() or not RELEASE_NAME.fullmatch(stage.name):
            continue
        receipt = stage / 'receipt.json'
        if not receipt.is_file() or receipt.is_symlink() or receipt.stat().st_size > 2 * 1024 * 1024:
            continue
        info = json.loads(receipt.read_text())
        if info.get('image') == 'smarthr-app:' + stage.name:
            records[stage] = info
    mounted = [Path(item['Source']).resolve() for container in containers for item in container.get('Mounts', [])]
    protected = set()
    for container in containers:
        image = container['Config'].get('Image', '')
        if image.startswith('smarthr-app:review-'):
            protected.add(image.partition(':')[2])
    active = set(protected)
    deployed = sorted(((stage, info) for stage, info in records.items() if info.get('deployed')),
                      key=lambda item: item[1].get('deployed_at') or '', reverse=True)
    protected.update(stage.name for stage, _ in deployed[:2])
    for stage, info in records.items():
        if stage.name in active:
            previous = info.get('previous_image', '')
            if previous.startswith('smarthr-app:review-'):
                protected.add(previous.partition(':')[2])
    targets = []
    for stage, info in records.items():
        if stage.name in protected or any(stage.is_relative_to(path) or path.is_relative_to(stage) for path in mounted):
            continue
        targets.extend(verified_targets(stage, info))
    return sorted(targets), protected


def plan_digest(root, targets, containers):
    manifest = {'targets': [{'path': path.relative_to(root).as_posix(),
                             'receipt_sha256': digest(path.parent / 'receipt.json')}
                            for path in targets],
                'containers': container_identity(containers)}
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def apply(root, targets, containers, *, expected_plan_sha256=None):
    current, _ = plan(root, containers)
    if current != targets:
        raise RuntimeError('Cleanup plan changed; review the new dry run')
    if expected_plan_sha256 is not None and plan_digest(root, current, containers) != expected_plan_sha256:
        raise RuntimeError('Cleanup evidence changed; review the new dry run')
    for path in targets:
        stage = path.parent
        if (path.name not in {'source', 'source.tar.gz'} or stage.parent != root / 'releases'
                or path.resolve() != stage.resolve() / path.name or path.is_symlink()):
            raise RuntimeError('Refusing to remove an unverified path')
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def container_identity(rows):
    return {row['Id']: (row['State']['StartedAt'], row['Config']['Image'],
                       sorted(row['Mounts'], key=lambda mount: mount['Destination'])) for row in rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-plan-sha256', help='Plan digest from the reviewed dry-run output')
    args = parser.parse_args()
    if args.apply and not re.fullmatch(r'[a-f0-9]{64}', args.expected_plan_sha256 or ''):
        parser.error('--apply requires --expected-plan-sha256 from a reviewed dry run')
    if args.expected_plan_sha256 and not args.apply:
        parser.error('--expected-plan-sha256 requires --apply')
    os.nice(10)
    root = Path('/opt/smarthr').resolve()
    ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
    containers = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True))
    targets, protected = plan(root, containers)
    fingerprint = plan_digest(root, targets, containers)
    if args.apply and args.expected_plan_sha256 != fingerprint:
        raise RuntimeError('Cleanup plan differs from the reviewed dry run')
    sizes = {str(path.relative_to(root)): int(subprocess.check_output(['du', '-s', '-B1', str(path)], text=True).split()[0])
             for path in targets}
    before = shutil.disk_usage(root)
    if args.apply:
        fresh_ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
        if fresh_ids != ids:
            raise RuntimeError('Container inventory changed; rerun the dry run')
        fresh = json.loads(subprocess.check_output(['docker', 'inspect', *fresh_ids], text=True))
        if container_identity(fresh) != container_identity(containers):
            raise RuntimeError('Container identity or mounts changed')
        apply(root, targets, fresh, expected_plan_sha256=args.expected_plan_sha256)
    after = shutil.disk_usage(root)
    print(json.dumps({'applied': args.apply, 'plan_sha256': fingerprint, 'targets': sizes, 'protected_releases': sorted(protected),
        'verified_disposable_bytes': sum(sizes.values()), 'free_bytes_before': before.free,
        'free_bytes_after': after.free, 'cvs_backups_images_volumes_untouched': True}))


if __name__ == '__main__':
    main()
