import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smarthr_monitor', ROOT/'deploy/vps/scripts/smarthr-monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def healthy_snapshot():
    return {'services': {name: {'running': True, 'healthy': True, 'memory_limit': 1024,
            'pids_limit': 256, 'log_rotation': True} for name in monitor.SERVICES},
            'health': True, 'deep_health': True, 'ai_skipped': True, 'disk_used_percent': 50}


def test_guardrails_change_only_owned_service_resources_and_logs():
    manifest = yaml.safe_load((ROOT/'deploy/vps/production-guardrails.yml').read_text())
    assert set(manifest) == {'services'}
    assert set(manifest['services']) == set(monitor.SERVICES)
    for service in manifest['services'].values():
        assert set(service) == {'cpus','cpu_shares','mem_limit','mem_reservation','memswap_limit','pids_limit','logging'}
        assert 0 < service['cpus'] <= 2 and 128 <= service['pids_limit'] <= 512
        assert service['logging'] == {'driver':'json-file','options':{'max-size':'10m','max-file':'5'}}
    assert manifest['services']['smarthr-app']['mem_limit'] == '3g'
    assert manifest['services']['smarthr-postgres']['mem_limit'] == '2g'


@pytest.mark.parametrize('used,level',[(50,'healthy'),(80,'warning'),(91.9,'warning'),(92,'critical')])
def test_monitor_disk_boundaries(used,level):
    snapshot = healthy_snapshot(); snapshot['disk_used_percent'] = used
    assert monitor.evaluate(snapshot)['level'] == level


def test_monitor_never_treats_unverified_ai_health_policy_as_healthy():
    snapshot = healthy_snapshot(); snapshot['ai_skipped'] = False
    assert 'readiness_ai_policy_unverified' in monitor.evaluate(snapshot)['issues']


def test_monitor_detects_owned_service_failure_and_missing_limits():
    snapshot = healthy_snapshot(); snapshot['services']['smarthr-app'] = {}
    status = monitor.evaluate(snapshot)
    assert status['level'] == 'critical'
    assert 'smarthr-app:resource_limits_missing' in status['issues']
    assert 'smarthr-app:log_rotation_missing' in status['issues']


def test_monitor_records_only_state_changes_without_private_payloads(tmp_path,capsys):
    path = tmp_path/'state.json'
    assert monitor.record_transition({'level':'healthy','issues':[]},path)
    assert not monitor.record_transition({'level':'healthy','issues':[]},path)
    assert len(capsys.readouterr().out.splitlines()) == 1
    assert monitor.record_transition({'level':'warning','issues':['disk_warning']},path)


def test_monitor_requests_only_local_non_ai_health_urls(monkeypatch):
    import json
    monkeypatch.setattr(monitor.shutil,'disk_usage',lambda p: MagicMock(total=100,free=50))
    monkeypatch.setattr(monitor.subprocess,'check_output',lambda *a,**k:'[]')
    opener = MagicMock()
    response = MagicMock()
    response.read.side_effect = [json.dumps({'status':'healthy'}).encode(),
        json.dumps({'status':'healthy','checks':{'llm':{'status':'skipped'}}}).encode()]
    response.__enter__.return_value = response
    opener.open.return_value = response
    monkeypatch.setattr(monitor.urllib.request,'build_opener',lambda *a:opener)
    snapshot = monitor.inspect_snapshot()
    assert snapshot['ai_skipped'] is True
    assert [call.args[0] for call in opener.open.call_args_list] == [
        'http://127.0.0.1:8081/health','http://127.0.0.1:8081/health/deep']
