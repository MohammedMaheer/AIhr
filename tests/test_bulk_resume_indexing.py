from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from test_integration_workflows import api  # noqa: F401
from test_upload_workflows import PDF, upload_api  # noqa: F401
from vps_local import discovery_shim as search


def test_manual_batch_keeps_order_and_mixed_outcomes(upload_api, monkeypatch):
    client, db, single = upload_api
    db.verify_session.return_value['company']['company_code'] = 'fictional'
    monkeypatch.setenv('SMARTHR_BULK_EMBED_BATCH_SIZE', '3')
    grouped = Mock(return_value=[True, None, False])
    monkeypatch.setattr(main, '_store_resume_upload_batch', grouped)
    files = [('files', (name, PDF, 'application/pdf'))
             for name in ['a.pdf', 'bad.exe', 'b.pdf', 'c.pdf', 'last.pdf']]
    response = client.post('/api/upload-files', files=files, data={'folder_path': 'Fixtures/Batch', 'batch_info': '1/2'})
    assert response.status_code == 200
    result = response.json()
    assert result['batch_stats'] == {'successful': 3, 'failed': 2, 'total': 5}
    assert [item['filename'] for item in result['results']] == ['a.pdf', 'bad.exe', 'b.pdf', 'c.pdf', 'last.pdf']
    assert [item.get('vector_indexed') for item in result['results']] == [True, None, None, False, True]
    assert grouped.call_args.args[1:5] == ('fixture-bucket', 1, 'fictional', 7)
    assert [item['filename'] for item in grouped.call_args.args[-1]] == ['a.pdf', 'b.pdf', 'c.pdf']
    assert single.call_args.kwargs['filename'] == 'last.pdf'


def test_large_files_flush_the_byte_budget_without_rejecting_the_upload(upload_api, monkeypatch):
    client, _, single = upload_api
    monkeypatch.setenv('SMARTHR_BULK_EMBED_BATCH_SIZE', '8')
    grouped = Mock(return_value=[True, True])
    monkeypatch.setattr(main, '_store_resume_upload_batch', grouped)
    content = PDF + b'X' * (6 * 1024 * 1024)
    response = client.post('/api/upload-files', files=[('files', (f'{i}.pdf', content, 'application/pdf'))
                                                      for i in range(3)])
    assert response.status_code == 200
    assert response.json()['batch_stats']['successful'] == 3
    assert len(grouped.call_args.args[-1]) == 2
    assert single.call_count == 1


@pytest.mark.parametrize('local, value, size', [('1', '8', 8), ('1', '400', 8), ('1', '-2', 1),
                                              ('1', 'bad', 1), ('0', '8', 1)])
def test_batch_setting_bounds_and_cloud_safety(monkeypatch, local, value, size):
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', local)
    monkeypatch.setenv('SMARTHR_BULK_EMBED_BATCH_SIZE', value)
    assert main._manual_upload_batch_size() == size


@pytest.mark.parametrize('failure', ['exception', 'wrong-count', 'nonfinite', 'write-failure', None])
def test_batch_uses_same_writer_and_contains_individual_failures(monkeypatch, failure):
    documents = [search.Document(id=str(i)) for i in range(5)]
    entries = [SimpleNamespace(searchable=True, text=f'synthetic {i}' * 5) for i in range(3)]
    entries += [SimpleNamespace(searchable=False, text=''), None]
    monkeypatch.setattr(search, '_prepare_document_embedding', lambda document: entries[int(document.id)])
    vectors = [[float(i + 1)] + [0.0] * 383 for i in range(3)]
    model = Mock()
    model.get_embeddings.return_value = [SimpleNamespace(values=v) for v in vectors]
    if failure == 'exception':
        model.get_embeddings.side_effect = RuntimeError('fictional failure')
    if failure == 'wrong-count':
        model.get_embeddings.return_value.pop()
    if failure == 'nonfinite':
        model.get_embeddings.return_value[1] = SimpleNamespace(values=[float('nan')] * 384)
    monkeypatch.setattr(search.vertexai_shim.language_models.TextEmbeddingModel, 'from_pretrained', lambda _: model)
    single = Mock(side_effect=lambda text: vectors[next(i for i, e in enumerate(entries[:3]) if e.text == text)])
    monkeypatch.setattr(search, '_embed_query', single)
    written = []

    def write(entry, vector, document_id):
        if failure == 'write-failure' and document_id == '1':
            raise RuntimeError('fictional member failure')
        written.append((document_id, vector))
        return search.IndexOperation(document_id, indexed=vector is not None)

    monkeypatch.setattr(search, '_write_document_embedding', write)
    results = search.index_resume_batch(documents)
    assert results[-1].error_code == 'source_missing'
    assert [r.indexed for r in results] == [True, failure != 'write-failure', True, False, False]
    assert [v for i, v in written] == ([vectors[0], vectors[2], None] if failure == 'write-failure' else [*vectors, None])
    assert model.get_embeddings.call_args.args == ([entry.text for entry in entries[:3]],)
    assert single.call_count == (3 if failure in {'exception', 'wrong-count', 'nonfinite'} else 0)
