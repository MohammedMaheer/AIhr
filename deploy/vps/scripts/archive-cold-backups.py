#!/usr/bin/env python3
"""Lossless cold-backup consolidation; dry run and verified recovery precede removal."""
import argparse
from contextlib import ExitStack
from decimal import Decimal
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import tempfile
import time
import uuid

PATTERNS = {'legacy-source': re.compile(r'full-audit-[0-9]{8}T[0-9]{6}Z'),
            'qa-runtime': re.compile(r'v[0-9]+-runtime-[0-9]+')}
CV_SUFFIXES = {'.pdf', '.doc', '.docx', '.rtf', '.odt', '.ppt', '.pptx'}
INDEX = '__cold_backup_manifest__.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stamp(path):
    s = path.lstat()
    return {'dev': s.st_dev, 'ino': s.st_ino, 'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
            'ctime_ns': s.st_ctime_ns, 'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid}


def runtime_references():
    """References remain in memory; environment values are never logged."""
    paths, texts = [], []
    proc = Path('/proc')
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        for item in ('cwd', 'exe'):
            try:
                paths.append(os.readlink(pid / item).removesuffix(' (deleted)'))
            except OSError:
                pass
        try:
            for fd in (pid / 'fd').iterdir():
                try:
                    paths.append(os.readlink(fd).removesuffix(' (deleted)'))
                except OSError:
                    pass
        except OSError:
            pass
        for name in ('cmdline', 'environ', 'maps'):
            try:
                texts.append((pid / name).read_bytes().decode(errors='replace'))
            except OSError:
                pass
    for root in ('/etc/systemd/system', '/etc/nginx', '/etc/cron.d', '/var/spool/cron/crontabs'):
        for path in Path(root).rglob('*'):
            try:
                if path.is_file() and path.stat().st_size < 2 * 1024**2:
                    texts.append(path.read_text(errors='replace'))
            except OSError:
                pass
    return paths, texts


def pinned(path, references, mounts):
    paths, texts = references
    if any(Path(p).is_relative_to(path) for p in paths if p.startswith('/')):
        return True
    if any(path.is_relative_to(m) or Path(m).is_relative_to(path) for m in mounts):
        return True
    pattern = re.compile(r'(?<![\w-])' + re.escape(path.name) + r'(?=$|[/\s\x00\x22\x27])')
    return any(pattern.search(text) for text in texts)


def plan(root, kind, is_pinned=lambda path: False, now=None):
    if kind not in PATTERNS or root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ValueError('Unsafe backup root')
    now = time.time() if now is None else now
    entries = sorted(p for p in root.iterdir() if PATTERNS[kind].fullmatch(p.name)
                     and p.is_dir() and not p.is_symlink() and not (p / 'ARCHIVED.json').exists())
    if kind == 'qa-runtime':
        entries.sort(key=lambda p: int(p.name.rsplit('-', 1)[-1]))
    protected = set(entries[:1] + entries[-2:])
    selected = []
    for directory in entries:
        if directory in protected or is_pinned(directory):
            continue
        files, directories = [], []
        safe = True
        for p in [directory, *sorted(directory.rglob('*'))]:
            s = p.lstat()
            if (p.is_symlink() or s.st_dev != root.stat().st_dev or
                    not (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)) or
                    p.suffix.lower() in CV_SUFFIXES or
                    (p.suffix.lower() == '.txt' and re.search(r'(?i)resume|curriculum|\bcv\b', p.stem))):
                safe = False
                break
            record = {'name': p.relative_to(root).as_posix(), **stamp(p)}
            if p.is_dir():
                directories.append(record)
            elif s.st_nlink == 1:
                files.append({**record, 'sha256': digest(p)})
            else:
                safe = False
                break
        if not safe or not files or now - max(r['ctime_ns'] / 1e9 for r in files) < 48 * 3600:
            continue
        selected.append({'name': directory.name, 'directories': directories, 'files': files})
    return {'schema': 1, 'root': str(root), 'kind': kind, 'protected': sorted(p.name for p in protected),
            'selected': selected}


def plan_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sync_directory(path):
    if os.name == 'nt':
        return
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_new_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def verify_sources(value):
    root = Path(value['root'])
    for entry in value['selected']:
        directory = root / entry['name']
        expected = {r['name'] for r in entry['files'] + entry['directories']}
        actual = {p.relative_to(root).as_posix() for p in [directory, *directory.rglob('*')]}
        if actual != expected:
            raise RuntimeError('Backup member set changed')
        for record in entry['files'] + entry['directories']:
            path = root / record['name']
            current = stamp(path)
            if path.is_symlink() or path.resolve() != path or current != {k: record[k] for k in current}:
                raise RuntimeError('Backup metadata changed')
            if 'sha256' in record and digest(path) != record['sha256']:
                raise RuntimeError('Backup content changed')


def create_archive(value, path, dictionary_bytes=64 * 1024**2):
    root = Path(value['root'])
    with path.open('xb') as raw:
        os.chmod(path, 0o600)
        with lzma.LZMAFile(raw, 'w', filters=[{'id': lzma.FILTER_LZMA2, 'preset': 6, 'dict_size': dictionary_bytes}]) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                encoded = json.dumps(value, sort_keys=True).encode()
                info = tarfile.TarInfo(INDEX); info.size = len(encoded); info.mode = 0o600
                archive.addfile(info, io.BytesIO(encoded))
                for entry in value['selected']:
                    for record in entry['directories'] + entry['files']:
                        path = root / record['name']
                        info = archive.gettarinfo(str(path), arcname=record['name'])
                        info.uname = info.gname = ''
                        info.pax_headers['mtime'] = str(Decimal(record['mtime_ns']) / Decimal(10**9))
                        if 'sha256' in record:
                            with path.open('rb') as stream:
                                archive.addfile(info, stream)
                        else:
                            archive.addfile(info)
        raw.flush(); os.fsync(raw.fileno())


def verify_archive(path, value):
    records = {r['name']: r for e in value['selected'] for r in e['directories'] + e['files']}
    seen = set()
    with lzma.LZMAFile(path, 'r') as decoded:
        with tarfile.open(fileobj=decoded, mode='r|') as archive:
            for member in archive:
                if member.name in seen:
                    raise RuntimeError('Duplicate archive member')
                seen.add(member.name)
                if member.name == INDEX:
                    expected_size = len(json.dumps(value, sort_keys=True).encode())
                    if not member.isfile() or member.size != expected_size or json.load(archive.extractfile(member)) != value:
                        raise RuntimeError('Archive manifest differs')
                    continue
                record = records.get(member.name)
                if not record or member.mode != record['mode'] or member.uid != record['uid'] or member.gid != record['gid']:
                    raise RuntimeError('Unexpected archive member or metadata')
                mtime = Decimal(member.pax_headers.get('mtime', str(member.mtime)))
                if int(mtime * 10**9) != record['mtime_ns']:
                    raise RuntimeError('Archive timestamp differs')
                if 'sha256' in record:
                    if not member.isfile() or member.size != record['size']:
                        raise RuntimeError('Archive file type/size differs')
                    if hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest() != record['sha256']:
                        raise RuntimeError('Archive content differs')
                elif not member.isdir():
                    raise RuntimeError('Archive directory type differs')
        while decoded.read(1024 * 1024):
            pass  # Drain the XZ footer/checksum before accepting the archive.
    if seen != set(records) | {INDEX}:
        raise RuntimeError('Archive members missing')


def consolidate(value, destination, expected_digest, check_pins=lambda path: False, minimum_savings=32 * 1024**2):
    if expected_digest != plan_digest(value) or not value['selected']:
        raise RuntimeError('No reviewed nonempty plan')
    root = Path(value['root'])
    if destination.is_symlink() or destination.resolve() != destination or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise ValueError('Archive destination must be separate and non-symlink')
    if any(check_pins(root / e['name']) for e in value['selected']):
        raise RuntimeError('Backup is referenced by a runtime')
    verify_sources(value)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt' and stat.S_IMODE(destination.stat().st_mode) != 0o700:
        raise ValueError('Archive directory must be private')
    before = shutil.disk_usage(root).free
    if before < 2 * 1024**3:
        raise RuntimeError('Insufficient safe headroom')
    name = 'cold-' + value['kind'] + '-' + uuid.uuid4().hex
    archive = destination / (name + '.tar.xz')
    create_archive(value, archive)
    verify_archive(archive, value)
    source_bytes = sum(r['size'] for e in value['selected'] for r in e['files'])
    if source_bytes - archive.stat().st_size < minimum_savings:
        archive.unlink()
        raise RuntimeError('Insufficient savings; original backups retained')
    # Restore one complete set to an isolated directory before any source is removed.
    with tempfile.TemporaryDirectory(prefix='.restore-check-', dir=destination) as temporary:
        target = Path(temporary); chosen = value['selected'][0]
        with tarfile.open(archive, 'r:xz') as bundle:
            members = [m for m in bundle if m.name == chosen['name'] or m.name.startswith(chosen['name'] + '/')]
            bundle.extractall(target, members=members, filter='data')
        for r in chosen['files']:
            if digest(target / r['name']) != r['sha256']:
                raise RuntimeError('Isolated restore differs')
    verify_sources(value)
    if any(check_pins(root / e['name']) for e in value['selected']):
        raise RuntimeError('Runtime references changed; originals retained')
    archive_hash = digest(archive)
    manifest = destination / (name + '.json')
    write_new_json(manifest, {'archive': str(archive), 'archive_sha256': archive_hash, 'plan': value})
    for entry in value['selected']:
        directory = root / entry['name']
        if check_pins(directory):
            raise RuntimeError('Runtime reference appeared; stop removal')
        write_new_json(directory / 'ARCHIVED.json', {'archive': str(archive), 'manifest': str(manifest),
            'archive_sha256': archive_hash, 'member_prefix': entry['name'], 'restore_to_an_empty_directory': True})
        for record in entry['files']:
            path = root / record['name']
            current = stamp(path)
            if (path.is_symlink() or path.resolve() != path or
                    current != {k: record[k] for k in current} or digest(path) != record['sha256']):
                raise RuntimeError('Backup changed; archive is retained for recovery')
            path.unlink()
        for record in sorted(entry['directories'], key=lambda r: len(Path(r['name']).parts), reverse=True):
            path = root / record['name']
            if path != directory:
                path.rmdir()
        sync_directory(directory)
    sync_directory(destination); sync_directory(root)
    return {'archive': str(archive), 'archive_sha256': archive_hash, 'manifest': str(manifest),
            'sets_archived': len(value['selected']), 'files_verified': sum(len(e['files']) for e in value['selected']),
            'original_bytes': source_bytes, 'archive_bytes': archive.stat().st_size,
            'free_bytes_before': before, 'free_bytes_after': shutil.disk_usage(root).free,
            'every_original_byte_retained_in_verified_archive': True, 'isolated_restore_passed': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--archive-root', type=Path, required=True)
    parser.add_argument('--kind', choices=PATTERNS, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-plan-sha256')
    args = parser.parse_args()
    expected_name = '.codex-backups' if args.kind == 'legacy-source' else 'qa'
    if not args.source_root.is_absolute() or args.source_root.name != expected_name:
        parser.error('Unapproved source-root class')
    if args.apply and not re.fullmatch('[a-f0-9]{64}', args.expected_plan_sha256 or ''):
        parser.error('--apply requires the reviewed --expected-plan-sha256')
    import fcntl
    import subprocess
    os.nice(15)
    with ExitStack() as stack:
        lock = Path('/var/lib/vps-artifact-retention/.lock')
        lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if lock.is_symlink():
            raise ValueError('Unsafe retention lock')
        stream = stack.enter_context(lock.open('a'))
        os.chmod(lock, 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        def pins(path):
            ids = subprocess.check_output(['docker', 'ps', '-aq'], text=True).split()
            rows = json.loads(subprocess.check_output(['docker', 'inspect', *ids], text=True)) if ids else []
            mounts = [str(Path(m['Source']).resolve()) for row in rows for m in row['Mounts']]
            references = runtime_references()
            for base in (args.source_root, *list(args.source_root.parents)[:2], Path('/usr/local/bin')):
                for alias in base.iterdir():
                    if alias.is_symlink():
                        references[0].append(str(alias.resolve()))
            return pinned(path, references, mounts)
        value = plan(args.source_root, args.kind, pins)
        proof = plan_digest(value)
        result = consolidate(value, args.archive_root, args.expected_plan_sha256, pins) if args.apply else {
            'plan': value, 'plan_sha256': proof, 'applied': False}
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
