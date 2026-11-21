"""QA cleanup never uses mutable tags, force/prune, production images or volumes."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

spec=importlib.util.spec_from_file_location('qa_cleanup',Path(__file__).resolve().parents[1]/'deploy/vps/scripts/prune-qa-images.py')
cleanup=importlib.util.module_from_spec(spec);spec.loader.exec_module(cleanup)
NOW=1800000000


def image(number,tag=None,parent='',layers=None):
    return {'Id':'sha256:'+format(number,'064x'),'Parent':parent,'RepoTags':[tag] if tag else [],
            'RepoDigests':[],'Created':'2026-01-01T00:00:00Z','Size':1000,
            'RootFS':{'Type':'layers','Layers':layers or ['base']}}


@pytest.fixture
def graph():
    base=image(1,'smarthr-app:clean-20260101t000000z')
    rows=[base];histories={base['Id']:['production history']}
    for day in range(1,6):
        tag=f'smarthr-app:clean-2026010{day}t000000z'
        base['RepoTags'].append(tag) if tag not in base['RepoTags'] else None
        parent=image(10+day,parent=base['Id'],layers=['base','qa-'+str(day)])
        qa=image(20+day,tag+'-qa',parent['Id'],['base','qa-'+str(day)])
        parent['Size']=qa['Size']=2000
        parent['Created']=qa['Created']=f'2026-01-0{day}T00:00:00Z'
        histories[qa['Id']]=cleanup.QA_HISTORY+histories[base['Id']]
        rows.extend([parent,qa])
    return rows,histories


def planned(graph,containers=None):
    rows,histories=graph
    return cleanup.plan(rows,containers or [],histories.__getitem__,now=NOW)


def selected(value):return {r['image']['Id'] for r in value['selected']}


def test_baseline_newest_two_and_production_are_retained(graph):
    value=planned(graph)
    assert selected(value)=={image(n)['Id'] for n in (12,13,22,23)}
    assert image(1)['Id'] in value['retained_ids']
    order=[r['image']['Id'] for r in value['selected']]
    assert order.index(image(22)['Id'])<order.index(image(12)['Id'])


def test_stopped_container_reference_is_protected(graph):
    pin={'id':'stopped','image_id':image(22)['Id']}
    assert image(22)['Id'] not in selected(planned(graph,[pin]))


def test_explicit_operations_qa_pin_is_retained(graph,monkeypatch):
    monkeypatch.setattr(cleanup,'PINNED_QA',{'smarthr-app:clean-20260102t000000z-qa'})
    assert image(22)['Id'] not in selected(planned(graph))


def test_foreign_alias_or_multiple_tags_are_never_removed(graph):
    graph[0][4]['RepoTags'].append('another-app:needed')
    assert image(22)['Id'] not in selected(planned(graph))


def test_extra_copy_or_unverified_history_is_not_eligible(graph):
    graph[1][image(22)['Id']].insert(0,'COPY genuine originals /backup')
    assert image(22)['Id'] not in selected(planned(graph))


def test_nonmatching_layer_base_is_not_eligible(graph):
    graph[0][4]['RootFS']['Layers']=['different','qa']
    assert image(22)['Id'] not in selected(planned(graph))


def test_recent_image_is_retained(graph):
    graph[0][4]['Created']='2027-01-15T07:59:59Z'
    assert image(22)['Id'] not in selected(planned(graph))


def test_recent_but_not_newest_image_is_retained(graph):
    rows,histories=graph
    newest=max(cleanup.created(r) for r in rows)
    assert image(23)['Id'] not in selected(cleanup.plan(rows,[],histories.__getitem__,now=newest+3600))


def test_shared_parent_is_preserved(graph):
    foreign=image(99,'other-app:current',image(12)['Id'])
    graph[0].append(foreign)
    assert image(12)['Id'] not in selected(planned(graph))


def test_missing_production_base_is_retained(graph):
    graph[0][0]['RepoTags'].remove('smarthr-app:clean-20260102t000000z')
    assert image(22)['Id'] not in selected(planned(graph))


def test_registry_digest_is_retained(graph):
    graph[0][4]['RepoDigests']=['registry/private@sha256:needed']
    assert image(22)['Id'] not in selected(planned(graph))


def test_local_self_digest_is_not_misclassified_as_external_registry(graph):
    graph[0][4]['RepoDigests']=['smarthr-app@'+image(22)['Id']]
    assert image(22)['Id'] in selected(planned(graph))


def test_service_or_compose_reference_is_retained_without_logging_secrets(graph):
    rows,histories=graph
    text='UNRELATED_SECRET=fictional\nIMAGE=smarthr-app:clean-20260102t000000z-qa'
    value=cleanup.plan(rows,[],histories.__getitem__,now=NOW,references=[text])
    assert image(22)['Id'] not in selected(value)
    assert 'fictional' not in str(value)


def test_wrong_digest_prevents_any_removal(graph):
    value=planned(graph);calls=[]
    with pytest.raises(RuntimeError,match='reviewed digest'):
        cleanup.execute(value,'0'*64,lambda i:None,lambda:[],calls.append)
    assert calls==[]


def test_changed_tags_prevent_removal(graph):
    value=planned(graph);calls=[]
    changed=copy.deepcopy(value['selected'][0]['image']);changed['RepoTags']=['other-app:now-needed']
    with pytest.raises(RuntimeError,match='metadata/tags changed'):
        cleanup.execute(value,cleanup.digest(value),lambda i:changed,lambda:[],calls.append)
    assert calls==[]


def test_new_container_prevents_removal(graph):
    value=planned(graph);calls=[]
    with pytest.raises(RuntimeError,match='Container identity changed'):
        cleanup.execute(value,cleanup.digest(value),lambda i:None,lambda:[{'id':'new'}],calls.append)
    assert calls==[]


def test_success_checks_all_retained_images_and_uses_exact_ids(graph):
    value=planned(graph);state={r['Id']:r for r in graph[0]};calls=[]
    def remove(identifier):calls.append(identifier);del state[identifier]
    result=cleanup.execute(value,cleanup.digest(value),state.get,lambda:[],remove)
    assert result==calls and set(calls)==selected(value)
    assert set(state)==set(value['retained_ids'])


def test_command_uses_no_force_no_prune_and_immutable_id(monkeypatch):
    calls=[]
    monkeypatch.setattr(cleanup.subprocess,'run',lambda args,**kw:calls.append(args))
    cleanup.remove(image(22)['Id'])
    assert calls==[['docker','image','rm','--no-prune',image(22)['Id']]]
    with pytest.raises(ValueError):cleanup.remove('smarthr-app:mutable')


def test_batched_retained_inventory_still_rejects_a_missing_protected_image(graph):
    value=planned(graph);state={r['Id']:r for r in graph[0]}
    with pytest.raises(RuntimeError,match='retained image is missing'):
        cleanup.execute(value,cleanup.digest(value),state.get,lambda:[],lambda i:state.pop(i),
                        retained_ids=lambda:set(state)-{image(1)['Id']})


def test_cli_requires_review_before_docker_or_linux_access():
    r=subprocess.run([sys.executable,cleanup.__file__,'--apply'],capture_output=True,text=True)
    assert r.returncode==2 and '--expected-plan-sha256' in r.stderr
