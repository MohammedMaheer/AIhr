from docx import Document

from vps_local.discovery_shim import _extract_text_from_file


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
