from types import SimpleNamespace
from unittest.mock import patch

import pytest
import main


@pytest.mark.parametrize('status,expected', [(True, True), (False, False), (None, False)])
def test_upload_helper_requires_explicit_local_index_success(monkeypatch, status, expected):
    from google.cloud import discoveryengine_v1
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    operation = SimpleNamespace(name='local/test', indexed=status, error_code='synthetic')
    with patch.object(main, 'get_company_resources', return_value=('fixture-bucket', 'fixture-store')), \
         patch.object(discoveryengine_v1.DocumentServiceClient, 'create_document', return_value=operation):
        assert main.upload_to_vector_datastore('resume/fictional.docx', 1, 'fictional', '1') is expected


def test_cloud_document_acceptance_keeps_existing_contract(monkeypatch):
    from google.cloud import discoveryengine_v1
    monkeypatch.delenv('SMARTHR_LOCAL_MODE', raising=False)
    with patch.object(main, 'get_company_resources', return_value=('fixture-bucket', 'fixture-store')), \
         patch.object(discoveryengine_v1.DocumentServiceClient, 'create_document', return_value=SimpleNamespace(name='cloud/test')):
        assert main.upload_to_vector_datastore('resume/fictional.docx') is True
