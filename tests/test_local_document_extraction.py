from docx import Document
from unittest.mock import MagicMock, patch
import pytest

from vps_local.discovery_shim import _extract_text_from_file
from vps_local import discovery_shim as discovery


def test_table_only_docx_is_not_silently_unsearchable(tmp_path):
    doc = Document()
    cells = doc.add_table(rows=1, cols=2).rows[0].cells
    cells[0].text = 'Fictional Python Engineer'
    cells[1].text = 'Skills: FastAPI, PostgreSQL, Docker. Experience: 6 years.'
    path = tmp_path/'fixture.docx'
    doc.save(path)
    text = _extract_text_from_file(path)
    assert 'Fictional Python Engineer' in text and 'PostgreSQL' in text
    assert len(text) >= 30


def test_paragraphs_and_tables_are_preserved_with_bounded_output(tmp_path):
    doc = Document()
    doc.add_paragraph('Fictional candidate summary with Python experience.')
    doc.add_table(rows=1, cols=1).cell(0,0).text = 'FastAPI developer experience. '*4000
    path = tmp_path/'fixture.docx'
    doc.save(path)
    text = _extract_text_from_file(path)
    assert text.startswith('Fictional candidate summary') and 'FastAPI' in text
    assert len(text) == 80_000


def test_unreadable_legacy_word_does_not_become_invented_resume_text(tmp_path):
    path = tmp_path/'fixture.doc'
    path.write_bytes(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'+b'\x00'*80)
    assert _extract_text_from_file(path) == ''


def test_empty_docx_stays_empty(tmp_path):
    path = tmp_path/'fixture.docx'
    Document().save(path)
    assert _extract_text_from_file(path) == ''


def test_missing_source_is_not_reported_as_indexed():
    with patch.object(discovery, '_paths_for_uri', return_value=('', [])):
        operation = discovery.DocumentServiceClient().create_document(
            discovery.CreateDocumentRequest(document=discovery.Document()))
    assert operation.indexed is False
    assert operation.error_code == 'source_missing'


@pytest.mark.parametrize('text,indexed', [('', False), ('short', False), ('Fictional Python engineer. '*5, True)])
def test_saved_file_and_searchable_index_are_distinct(tmp_path, text, indexed):
    path = tmp_path/'fixture.docx'
    path.write_bytes(b'fixture')
    conn, pool = MagicMock(), MagicMock()
    pool.getconn.return_value = conn
    with patch.object(discovery, '_paths_for_uri', return_value=('resume/fixture.docx', [path])), \
         patch.object(discovery, '_extract_text_from_file', return_value=text), \
         patch.object(discovery, '_embed_query', return_value=[.1]*384) as embed, \
         patch.object(discovery, '_ensure_advanced_search_schema'), \
         patch.object(discovery, '_get_pool', return_value=pool):
        operation = discovery.DocumentServiceClient().create_document(
            discovery.CreateDocumentRequest(document=discovery.Document()))
    assert operation.indexed is indexed
    assert operation.error_code == ('' if indexed else 'no_searchable_text')
    assert embed.call_count == int(indexed)
    conn.commit.assert_called_once()
    pool.putconn.assert_called_once_with(conn)


def test_index_failure_does_not_expose_database_details():
    with patch.object(discovery, '_upsert_document_embedding', side_effect=RuntimeError('private credentials')):
        operation = discovery.DocumentServiceClient().create_document(
            discovery.CreateDocumentRequest(document=discovery.Document()))
    assert operation.indexed is False
    assert operation.error_code == 'indexing_failed'
    assert 'private' not in repr(operation)
    assert discovery.DocumentServiceClient().create_document().indexed is False
