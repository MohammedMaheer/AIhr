"""Cold archival retains every byte, metadata, current recovery sets and runtime pins."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import pytest

spec=importlib.util.spec_from_file_location('cold_archive',Path(__file__).resolve().parents[1]/'deploy/vps/scripts/archive-cold-backups.py')
archive=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive)


@pytest.fixture
def backups(tmp_path,monkeypatch):
    root=tmp_path/'.codex-backups';root.mkdir()
    for i in range(1,6):
        d=root/f'full-audit-2026010{i}T000000Z';d.mkdir()
        (d/'snapshot.pgdump').write_bytes((b'fictional recoverable backup\n'*4096)+str(i).encode())
        (d/'.env').write_bytes(b'FICTIONAL_TEST_SETTING=not-a-real-secret\n')
    value=archive.plan(root,'legacy-source',now=time.time()+72*3600)
    original=archive.create_archive
    monkeypatch.setattr(archive,'create_archive',lambda value,path:original(value,path,dictionary_bytes=1024**2))
    monkeypatch.setattr(archive.shutil,'disk_usage',lambda root:type('Space',(),{'free':10*1024**3})())
    return root,value,tmp_path/'archives'


def test_plan_preserves_oldest_two_newest_and_runtime_references(backups):
    root,value,_=backups
    assert len(value['selected'])==2 and len(value['protected'])==3
    name=value['selected'][0]['name']
    pinned=archive.plan(root,'legacy-source',lambda p:p.name==name,now=time.time()+72*3600)
    assert len(pinned['selected'])==1 and pinned['selected'][0]['name']!=name


def test_successful_archive_preserves_all_bytes_and_leaves_recovery_pointers(backups):
    root,value,destination=backups
    result=archive.consolidate(value,destination,archive.plan_digest(value),minimum_savings=1)
    assert result['isolated_restore_passed'] and result['files_verified']==4
    archive.verify_archive(Path(result['archive']),value)
    for entry in value['selected']:
        pointer=json.loads((root/entry['name']/'ARCHIVED.json').read_text())
        assert pointer['archive_sha256']==result['archive_sha256']
        assert pointer['member_prefix']==entry['name']
        assert sorted(p.name for p in (root/entry['name']).iterdir())==['ARCHIVED.json']
    for name in value['protected']:
        assert (root/name/'snapshot.pgdump').is_file()
    assert not archive.plan(root,'legacy-source',now=time.time()+72*3600)['selected']


def test_wrong_review_digest_prevents_archive_creation(backups):
    root,value,destination=backups
    with pytest.raises(RuntimeError,match='reviewed'):archive.consolidate(value,destination,'0'*64,minimum_savings=1)
    assert not destination.exists() and all((root/e['name']/'snapshot.pgdump').exists() for e in value['selected'])


def test_modified_file_is_not_removed(backups):
    root,value,destination=backups
    (root/value['selected'][0]['name']/'snapshot.pgdump').write_bytes(b'user change')
    with pytest.raises(RuntimeError,match='metadata changed'):
        archive.consolidate(value,destination,archive.plan_digest(value),minimum_savings=1)
    assert not destination.exists()


def test_failed_archive_verification_never_deletes_originals(backups,monkeypatch):
    root,value,destination=backups
    def failed(*args):raise RuntimeError('corrupt archive')
    monkeypatch.setattr(archive,'verify_archive',failed)
    with pytest.raises(RuntimeError,match='corrupt'):
        archive.consolidate(value,destination,archive.plan_digest(value),minimum_savings=1)
    assert all((root/e['name']/'snapshot.pgdump').is_file() for e in value['selected'])


def test_reference_appearing_after_verification_preserves_originals(backups):
    root,value,destination=backups;calls=[]
    def pinned(path):
        calls.append(path)
        return len(calls)>len(value['selected'])
    with pytest.raises(RuntimeError,match='references changed'):
        archive.consolidate(value,destination,archive.plan_digest(value),pinned,minimum_savings=1)
    assert all((root/e['name']/'snapshot.pgdump').exists() for e in value['selected'])


def test_original_cvs_and_unrecognized_directories_are_ineligible(backups):
    root,value,_=backups
    (root/value['selected'][0]['name']/'genuine-cv.pdf').write_bytes(b'original must remain')
    live=root/'candidate-storage';live.mkdir();(live/'cv.docx').write_bytes(b'CV')
    fresh=archive.plan(root,'legacy-source',now=time.time()+72*3600)
    assert len(fresh['selected'])==1 and (live/'cv.docx').read_bytes()==b'CV'


def test_qa_customer_and_export_sources_are_never_selected(tmp_path):
    root=tmp_path/'qa';root.mkdir()
    for name in ['v1-runtime-100','v2-runtime-200','v3-runtime-300','v4-runtime-400',
                 'v5-customer-source-500','v6-export-source-600']:
        d=root/name;d.mkdir();(d/'source.sqlite3').write_bytes(b'fictional snapshot')
    value=archive.plan(root,'qa-runtime',now=time.time()+72*3600)
    assert [e['name'] for e in value['selected']]==['v2-runtime-200']


def test_recent_backups_are_never_selected(backups):
    root,_,_=backups
    assert archive.plan(root,'legacy-source')['selected']==[]


def test_qa_retention_orders_by_timestamp_not_lexical_version(tmp_path):
    root=tmp_path/'qa';root.mkdir()
    for name in ['v8-runtime-100','v9-runtime-200','v10-runtime-300','v11-runtime-400']:
        d=root/name;d.mkdir();(d/'snapshot.sqlite3').write_bytes(b'fictional snapshot')
    value=archive.plan(root,'qa-runtime',now=time.time()+72*3600)
    assert [e['name'] for e in value['selected']]==['v9-runtime-200']


def test_changed_member_set_is_not_removed(backups):
    root,value,destination=backups
    (root/value['selected'][0]['name']/'new.txt').write_text('new user data')
    with pytest.raises(RuntimeError,match='member set changed'):
        archive.consolidate(value,destination,archive.plan_digest(value),minimum_savings=1)
    assert not destination.exists()


def test_insufficient_savings_keeps_originals(backups):
    root,value,destination=backups
    with pytest.raises(RuntimeError,match='Insufficient savings'):
        archive.consolidate(value,destination,archive.plan_digest(value),minimum_savings=10**9)
    assert not list(destination.glob('*.tar.xz'))
    assert all((root/e['name']/'snapshot.pgdump').exists() for e in value['selected'])


def test_unsafe_archive_destination_is_rejected(backups):
    root,value,_=backups
    with pytest.raises(ValueError,match='separate'):
        archive.consolidate(value,root/'archives',archive.plan_digest(value),minimum_savings=1)


def test_cli_requires_review_before_linux_or_docker_access(backups):
    root,_,destination=backups
    r=subprocess.run([sys.executable,archive.__file__,'--source-root',str(root),'--archive-root',str(destination),
      '--kind','legacy-source','--apply'],capture_output=True,text=True)
    assert r.returncode==2 and '--expected-plan-sha256' in r.stderr


def test_parent_mount_and_config_reference_pin_an_old_backup(backups):
    root,value,_=backups;path=root/value['selected'][0]['name']
    assert archive.pinned(path,([],[]),[str(root)])
    assert archive.pinned(path,([],['restore '+path.name+'/snapshot.pgdump']),[])


def test_similar_directory_name_does_not_create_a_false_reference(backups):
    root,value,_=backups;path=root/value['selected'][0]['name']
    assert not archive.pinned(path,([],['restore '+path.name+'-other']),[])
