"""Cleanup is opt-in, hash-verified and cannot target CVs, backups or mounts."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import subprocess
import sys

import pytest

spec = importlib.util.spec_from_file_location('release_cleanup', Path(__file__).resolve().parents[1] / 'deploy/vps/scripts/prune-release-sources.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def release(root, index, *, deployed=True):
    stage = root / 'releases' / f'review-abcdef{index}-20261114t10000{index}z'
    source = stage / 'source'
    source.mkdir(parents=True)
    (source / 'main.py').write_bytes(b'# reviewed application source\n')
    (source / 'config.json').write_text(json.dumps(cleanup.SYNTHETIC_CONFIG))
    hashes = {'main.py': cleanup.digest(source / 'main.py')}
    with tarfile.open(stage / 'source.tar.gz', 'w:gz') as bundle:
        bundle.add(source / 'main.py', arcname='main.py')
    (stage / 'backup').mkdir()
    (stage / 'backup/db.pgdump').write_bytes(b'private backup must remain')
    info = {'image': 'smarthr-app:' + stage.name, 'source_hashes': hashes,
            'deployed': deployed, 'deployed_at': '2026-11-14T10:00:0' + str(index)}
    (stage / 'receipt.json').write_text(json.dumps(info))
    return stage, info


def test_cleanup_preserves_two_newest_sources_and_all_cv_backup_data(tmp_path):
    stages = [release(tmp_path, i)[0] for i in range(4)]
    cv = tmp_path / 'storage' / 'genuine-cv.docx'
    cv.parent.mkdir()
    cv.write_bytes(b'genuine original')
    targets, protected = cleanup.plan(tmp_path, [])
    assert protected == {stage.name for stage in stages[2:]}
    assert len(targets) == 4
    cleanup.apply(tmp_path, targets, [])
    assert cv.read_bytes() == b'genuine original'
    assert all((stage / 'backup/db.pgdump').read_bytes() == b'private backup must remain' for stage in stages)
    assert all((stage / 'source/main.py').is_file() for stage in stages[2:])


@pytest.mark.parametrize('extra', ['genuine-cv.pdf', 'private.env', 'config.json', 'changed-source'])
def test_source_directory_with_unverified_content_is_never_removed(tmp_path, extra):
    stage, info = release(tmp_path, 0)
    path = stage / 'source' / ('main.py' if extra == 'changed-source' else extra)
    path.write_bytes(b'unreviewed content')
    assert stage / 'source' not in cleanup.verified_targets(stage, info)
    assert path.is_file()


def test_unsafe_archive_and_mounted_old_release_are_protected(tmp_path):
    stage, info = release(tmp_path, 0, deployed=False)
    with tarfile.open(stage / 'source.tar.gz', 'w:gz') as bundle:
        member = tarfile.TarInfo('../storage/cv.pdf'); member.size = 3
        bundle.addfile(member, io.BytesIO(b'CV!'))
    assert stage / 'source.tar.gz' not in cleanup.verified_targets(stage, info)
    state = [{'Config': {'Image': 'unrelated-app:latest'}, 'Mounts': [{'Source': str(stage / 'source')}]}]
    assert cleanup.plan(tmp_path, state)[0] == []


def test_cleanup_rechecks_hashes_before_applying(tmp_path):
    stage, _ = release(tmp_path, 0, deployed=False)
    targets, _ = cleanup.plan(tmp_path, [])
    (stage / 'source/main.py').write_bytes(b'user modifications')
    with pytest.raises(RuntimeError, match='plan changed'):
        cleanup.apply(tmp_path, targets, [])
    assert (stage / 'source/main.py').is_file()


def test_mount_permutation_does_not_hide_a_real_container_change():
    first = {'Id': 'owned-container', 'State': {'StartedAt': 'one'}, 'Config': {'Image': 'owned:one'},
             'Mounts': [{'Destination': '/b', 'Source': '/owned/b', 'RW': False},
                        {'Destination': '/a', 'Source': '/owned/a', 'RW': True}]}
    reordered = {**first, 'Mounts': first['Mounts'][::-1]}
    assert cleanup.container_identity([first]) == cleanup.container_identity([reordered])
    changed = {**first, 'Mounts': [{'Destination': '/a', 'Source': '/other/a', 'RW': True}, first['Mounts'][0]]}
    assert cleanup.container_identity([first]) != cleanup.container_identity([changed])
    assert cleanup.container_identity([first]) != cleanup.container_identity([{**first, 'State': {'StartedAt': 'two'}}])


def test_apply_requires_an_explicit_reviewed_plan_before_docker_access():
    result = subprocess.run([sys.executable, str(Path(cleanup.__file__)), '--apply'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert '--expected-plan-sha256 from a reviewed dry run' in result.stderr


def test_changed_receipt_cannot_reuse_reviewed_plan_even_with_same_targets(tmp_path):
    stage, info = release(tmp_path, 0, deployed=False)
    targets, _ = cleanup.plan(tmp_path, [])
    reviewed = cleanup.plan_digest(tmp_path, targets, [])
    (stage / 'receipt.json').write_text(json.dumps({**info, 'new_review_evidence': True}))
    assert cleanup.plan(tmp_path, [])[0] == targets
    with pytest.raises(RuntimeError, match='evidence changed'):
        cleanup.apply(tmp_path, targets, [], expected_plan_sha256=reviewed)
    assert (stage / 'source/main.py').is_file()


def test_unchanged_reviewed_plan_applies_and_preserves_backups(tmp_path):
    stage, _ = release(tmp_path, 0, deployed=False)
    targets, _ = cleanup.plan(tmp_path, [])
    reviewed = cleanup.plan_digest(tmp_path, targets, [])
    cleanup.apply(tmp_path, targets, [], expected_plan_sha256=reviewed)
    assert not (stage / 'source').exists()
    assert (stage / 'backup/db.pgdump').read_bytes() == b'private backup must remain'


def test_new_disposable_release_invalidates_previously_reviewed_plan(tmp_path):
    stage, _ = release(tmp_path, 0, deployed=False)
    targets, _ = cleanup.plan(tmp_path, [])
    reviewed = cleanup.plan_digest(tmp_path, targets, [])
    later, _ = release(tmp_path, 1, deployed=False)
    current, _ = cleanup.plan(tmp_path, [])
    with pytest.raises(RuntimeError, match='evidence changed'):
        cleanup.apply(tmp_path, current, [], expected_plan_sha256=reviewed)
    assert (stage / 'source/main.py').is_file()
    assert (later / 'source/main.py').is_file()
