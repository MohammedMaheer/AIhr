import hashlib
from contextlib import contextmanager
from unittest.mock import MagicMock
from pathlib import Path

import pytest
from psycopg2.errors import UndefinedTable

from services.recovered_text import lookup_recovered_text
from services.recovery_quality import acceptable_ocr, normalize_text, review_text
from test_durable_search import queue_db

USER = {'id': 7, 'user_type': 'tenant_user', 'company': {'company_id': 1}}
TEXT = 'Fictional CV. Experience: Software developer. Education: Bachelor degree. Skills: Python and SQL. ' * 8


def database(rows=None, error=None):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows or []
    cursor.execute.side_effect = error
    @contextmanager
    def get_cursor():
        yield cursor, None
    return MagicMock(get_cursor=get_cursor), cursor


def valid_row(text=TEXT):
    return {'extracted_text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest()}


def test_full_recovered_text_is_scoped_and_bound_to_original_bytes():
    db, cursor = database([valid_row()])
    assert lookup_recovered_text(db, USER, 'bucket', 'selected/cv.pdf', b'original') == TEXT
    sql, values = cursor.execute.call_args.args
    assert 'company_id = %s' in sql and "quality_status='accepted'" in sql
    assert values == ['bucket', 'selected', 'cv.pdf', 1, hashlib.sha256(b'original').hexdigest()]


@pytest.mark.parametrize('key', ['/cv.pdf', '../cv.pdf', 'a//cv.pdf', 'a/./cv.pdf', 'a\\cv.pdf'])
def test_unsafe_keys_do_not_read_a_recovery(key):
    db, cursor = database([valid_row()])
    assert lookup_recovered_text(db, USER, 'bucket', key, b'original') is None
    cursor.execute.assert_not_called()


def test_anonymous_or_ambiguous_sources_never_reuse_text():
    db, cursor = database([valid_row(), valid_row()])
    assert lookup_recovered_text(db, None, 'bucket', 'cv.pdf', b'original') is None
    cursor.execute.assert_not_called()
    assert lookup_recovered_text(db, {'id': 1, 'user_type': 'super_admin'}, 'bucket', 'cv.pdf', b'original') is None


@pytest.mark.parametrize('row', [
    {**valid_row(), 'text_sha256': '0' * 64}, valid_row('short'), valid_row('x' * 80_001), valid_row(TEXT+'\x00'),
])
def test_tampered_short_or_oversized_recovered_text_is_rejected(row):
    db, _ = database([row])
    assert lookup_recovered_text(db, USER, 'bucket', 'cv.pdf', b'original') is None


def test_missing_additive_schema_is_read_only_and_compatible():
    db, cursor = database(error=UndefinedTable())
    assert lookup_recovered_text(db, USER, 'bucket', 'cv.pdf', b'original') is None
    assert not any(token in cursor.execute.call_args.args[0] for token in ('CREATE ', 'UPDATE ', 'ALTER '))


def test_recovery_is_preferred_only_when_available_and_local(monkeypatch):
    import main
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setattr(main, 'get_db_manager', lambda: object())
    monkeypatch.setattr('services.recovered_text.lookup_recovered_text', lambda *args: TEXT)
    native = MagicMock(return_value='Existing native extraction')
    monkeypatch.setattr(main, 'extract_text_from_file', native)
    assert main._extract_search_document_text(b'original', 'bucket', 'cv.pdf', USER) == TEXT
    native.assert_not_called()
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '0')
    assert main._extract_search_document_text(b'original', 'bucket', 'cv.pdf', USER) == 'Existing native extraction'


def test_unregistered_or_unavailable_recovery_keeps_native_behavior(monkeypatch):
    import main
    monkeypatch.setenv('SMARTHR_LOCAL_MODE', '1')
    monkeypatch.setattr(main, 'get_db_manager', lambda: object())
    recovered = MagicMock(return_value=None)
    monkeypatch.setattr('services.recovered_text.lookup_recovered_text', recovered)
    monkeypatch.setattr(main, 'extract_text_from_file', lambda *args: 'Unchanged text')
    assert main._extract_search_document_text(b'bytes', 'bucket', 'folder/cv.pdf', USER) == 'Unchanged text'
    recovered.side_effect = RuntimeError('Synthetic unavailable database')
    assert main._extract_search_document_text(b'bytes', 'bucket', 'folder/cv.pdf', USER) == 'Unchanged text'


def test_local_quality_gates_do_not_turn_certificates_into_candidates():
    assert normalize_text('A\x00\r\nB  ') == 'A\nB'
    assert review_text(TEXT, 'fictional-cv.pdf') == 'accepted'
    assert review_text(TEXT, 'Degree certificate.pdf') == 'review_supporting_document'
    assert review_text('x', 'cv.pdf') == 'review_insufficient_text'
    assert acceptable_ocr([90, 91, 82])
    assert not acceptable_ocr([90, 20, 10])
    assert not acceptable_ocr([])


@pytest.fixture
def recovered_db(queue_db):
    with queue_db.get_cursor() as (cursor, _):
        cursor.execute('''CREATE TABLE resume_embeddings(id SERIAL PRIMARY KEY,company_id INTEGER,
            storage_bucket TEXT,folder TEXT,filename TEXT,extracted_text TEXT)''')
        cursor.execute((Path(__file__).resolve().parents[1]/'deploy/vps/migrations/20261110_resume_recovery.sql').read_text())
        for company,text in ((1,TEXT),(2,TEXT+' Different tenant')):
            cursor.execute('''INSERT INTO resume_embeddings(company_id,storage_bucket,folder,filename,extracted_text)
                VALUES(%s,'bucket','selected','cv.pdf',%s) RETURNING id''',(company,text))
            identifier=cursor.fetchone()['id']
            cursor.execute('''INSERT INTO resume_text_recoveries(resume_embedding_id,source_sha256,text_sha256,
                extraction_method,quality_status) VALUES(%s,%s,%s,'fixture','accepted')''',
                (identifier,hashlib.sha256(b'original').hexdigest(),hashlib.sha256(text.encode()).hexdigest()))
    return queue_db


def test_postgres_recovery_respects_tenant_bucket_folder_and_changed_bytes(recovered_db):
    assert lookup_recovered_text(recovered_db, USER, 'bucket', 'selected/cv.pdf', b'original') == TEXT
    other={**USER,'company':{'company_id':2}}
    assert lookup_recovered_text(recovered_db, other, 'bucket', 'selected/cv.pdf', b'original') == TEXT+' Different tenant'
    assert lookup_recovered_text(recovered_db, USER, 'other', 'selected/cv.pdf', b'original') is None
    assert lookup_recovered_text(recovered_db, USER, 'bucket', 'other/cv.pdf', b'original') is None
    assert lookup_recovered_text(recovered_db, USER, 'bucket', 'selected/cv.pdf', b'replaced') is None
    assert lookup_recovered_text(recovered_db, {'id':1,'user_type':'super_admin'}, 'bucket', 'selected/cv.pdf', b'original') is None
    with recovered_db.get_cursor() as (cursor, _):
        cursor.execute("UPDATE resume_embeddings SET extracted_text=extracted_text || ' tampered' WHERE company_id=1")
    assert lookup_recovered_text(recovered_db, USER, 'bucket', 'selected/cv.pdf', b'original') is None


def test_original_download_path_supplies_complete_recovery_without_provider_calls(recovered_db,monkeypatch):
    import main
    from services.search_reuse import SearchReuse
    monkeypatch.setenv('SMARTHR_LOCAL_MODE','1')
    monkeypatch.setattr(main,'get_db_manager',lambda:recovered_db)
    monkeypatch.setattr(main,'get_company_resources',lambda user:('bucket','fixture'))
    monkeypatch.setattr(main,'resolve_gcs_file_path',lambda *args:'selected/cv.pdf')
    storage=MagicMock()
    storage.bucket.return_value.blob.return_value.download_as_bytes.return_value=b'original'
    monkeypatch.setattr(main,'_get_storage_client',lambda:storage)
    native=MagicMock(side_effect=AssertionError('Complete registered recovery must precede a partial native extractor'))
    monkeypatch.setattr(main,'extract_text_from_file',native)
    monkeypatch.setattr(main,'_search_reuse',SearchReuse())
    assert main.get_file_content_and_bytes_from_gcs('selected/cv.pdf',USER)==(TEXT,b'original')
    assert main.get_file_content_from_gcs('selected/cv.pdf',USER)==TEXT
    native.assert_not_called()
