import io
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from docx import Document
import pytest

from services import document_validation as validation
from vps_local.discovery_shim import _extract_text_from_file


def archive(extra=None):
    data = io.BytesIO()
    with ZipFile(data, 'w', ZIP_DEFLATED) as zipped:
        for name in validation.REQUIRED_DOCX_PARTS:
            zipped.writestr(name, '<fixture/>')
        for name, content in (extra or {}).items():
            entry = ZipInfo('fixture')
            entry.filename = name
            entry.compress_type = ZIP_DEFLATED
            zipped.writestr(entry, content)
    return data.getvalue()


def test_real_word_document_and_table_content_remain_valid(tmp_path):
    doc = Document()
    doc.add_paragraph('Fictional Python engineer with six years experience.')
    doc.add_table(rows=1, cols=1).cell(0, 0).text = 'FastAPI, PostgreSQL'
    content = io.BytesIO()
    doc.save(content)
    assert validation.validate_docx_archive(content.getvalue()) == (True, '')
    path = tmp_path/'fixture.docx'
    path.write_bytes(content.getvalue())
    assert validation.validate_docx_archive(path) == (True, '')
    assert 'PostgreSQL' in _extract_text_from_file(path)


@pytest.mark.parametrize('content', [None, b'', b'PK\x03\x04not a word document', b'not zip', b'%PDF-1.7'])
def test_magic_bytes_alone_are_not_a_word_package(content):
    assert validation.validate_docx_archive(content)[0] is False


def test_plain_zip_is_not_a_word_document():
    content = io.BytesIO()
    with ZipFile(content, 'w') as zipped:
        zipped.writestr('unrelated.txt', 'fixture')
    assert not validation.validate_docx_archive(content.getvalue())[0]


def test_empty_root_directory_marker_keeps_existing_word_exporters_compatible():
    assert validation.validate_docx_archive(archive({'/': b''}))[0]
    assert not validation.validate_docx_archive(archive({'/': b'not a directory marker'}))[0]


def test_encrypted_archive_members_are_rejected():
    original = ZipFile.infolist
    def encrypted(zipped):
        entries = original(zipped)
        entries[0].flag_bits |= 1
        return entries
    with patch.object(ZipFile, 'infolist', encrypted):
        assert not validation.validate_docx_archive(archive())[0]


def test_compressed_expansion_is_bounded_without_reading_members(monkeypatch):
    monkeypatch.setattr(validation, 'MAX_DOCX_EXPANDED_BYTES', 4096)
    content = archive({'word/large.xml': 'a'*65536})
    assert len(content) < 4096
    with patch.object(ZipFile, 'open', side_effect=AssertionError('Must not decompress before validation')):
        assert not validation.validate_docx_archive(content)[0]


def test_xml_part_limit_is_separate_from_total_archive_limit(monkeypatch):
    monkeypatch.setattr(validation, 'MAX_DOCX_XML_BYTES', 64)
    assert not validation.validate_docx_archive(archive({'word/large.xml': 'a'*65}))[0]
    assert validation.validate_docx_archive(archive({'word/image.bin': b'a'*65}))[0]


def test_entry_count_is_bounded(monkeypatch):
    monkeypatch.setattr(validation, 'MAX_DOCX_ENTRIES', 3)
    assert not validation.validate_docx_archive(archive({'extra.xml': 'fixture'}))[0]


@pytest.mark.parametrize('path', ['../outside.xml', '/absolute.xml', 'word/../outside.xml', 'word\\unsafe.xml', 'word/unsafe\x00.xml'])
def test_unsafe_member_paths_are_rejected(path):
    assert not validation.validate_docx_archive(archive({path: 'fixture'}))[0]


def test_duplicate_parts_are_rejected():
    content = io.BytesIO(archive())
    with ZipFile(content, 'a') as zipped, pytest.warns(UserWarning):
        zipped.writestr('word/document.xml', '<duplicate/>')
    assert not validation.validate_docx_archive(content.getvalue())[0]


def test_guard_applies_to_local_indexing_before_docx_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(validation, 'MAX_DOCX_EXPANDED_BYTES', 4096)
    path = tmp_path/'fixture.docx'
    path.write_bytes(archive({'word/large.xml': 'a'*65536}))
    with patch('docx.Document', side_effect=AssertionError('Unsafe archive reached parser')) as parser:
        assert _extract_text_from_file(path) == ''
    parser.assert_not_called()
