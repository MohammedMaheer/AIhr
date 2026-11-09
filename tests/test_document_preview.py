from contextlib import contextmanager
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
import io
import zipfile

import pytest
from fastapi import HTTPException
import main
from services import document_preview as preview
from services.resume_library import preview_upload
from test_durable_search import queue_db
from test_resume_scope import library_db, USER
from test_integration_workflows import api


@pytest.fixture
def original(monkeypatch):
    row = {'id':7, 'company_id':1, 'file_name':'Fictional CV.pdf', 'file_path':'gs://fixture/cv.pdf', 'gcs_bucket_name':'fixture'}
    monkeypatch.setattr(preview, 'upload_record', lambda *_: dict(row))
    blob = MagicMock()
    blob.exists.return_value = True
    blob.size = 20
    blob.download_as_bytes.return_value = b'%PDF-1.7\nfictional'
    client = MagicMock()
    client.bucket.return_value.blob.return_value = blob
    with preview._cache_lock:
        preview._cache.clear()
    return row, blob, client


@pytest.mark.parametrize('extension', ['pdf','PDF','txt','doc','docx'])
def test_original_formats_are_read_only_and_do_not_use_ai(original, monkeypatch, extension):
    row, blob, client = original
    row['file_path']='gs://fixture/cv.'+extension
    if extension.lower()!='pdf':blob.download_as_bytes.return_value=b'Fictional text'
    converted=MagicMock(return_value=b'%PDF-1.7\nconverted')
    monkeypatch.setattr(preview,'_convert_word',converted)
    content, kind=preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert content and kind==('text/plain' if extension=='txt' else 'application/pdf')
    assert converted.call_count==(1 if extension in ('doc','docx') else 0)
    blob.upload_from_string.assert_not_called()


@pytest.mark.parametrize('content,expected', [(b'\xef\xbb\xbfFull CV\nText','Full CV\nText'),
    ('Arabic: \u0645\u0635\u0645\u0645'.encode('utf-8'),'Arabic: \u0645\u0635\u0645\u0645'),
    ('Unicode CV'.encode('utf-16'),'Unicode CV'), ('Unicode CV'.encode('utf-32'),'Unicode CV'),
    (b'Candidate\x92s CV','Candidate\u2019s CV')])
def test_original_text_encodings(content, expected):
    assert preview._decode_text(content)==expected


def test_unindexed_upload_has_document_preview_and_cached_text_is_only_a_fallback(library_db):
    with library_db.get_cursor() as (cur,_):
        cur.execute("INSERT INTO resume_uploads(file_name,file_path,company_id) VALUES ('Scanned.pdf','gs://fixture-bucket/scanned.pdf',1) RETURNING id")
        identifier=cur.fetchone()['id']
    data=preview_upload(library_db,USER,identifier)
    assert data['text']=='' and data['preview_kind']=='pdf'
    assert data['preview_url']==f'/api/resume-library/{identifier}/document'


def test_tenant_cannot_read_another_company_original(library_db):
    loader=MagicMock()
    with pytest.raises(HTTPException) as error:
        preview.render_upload(library_db,USER,5,'fixture',loader)
    assert error.value.status_code==404
    loader.assert_not_called()


def test_conversion_cache_still_checks_ownership(original, monkeypatch):
    row,blob,client=original;row['file_path']='gs://fixture/cv.docx'
    converted=MagicMock(return_value=b'%PDF-1.7\nconverted');monkeypatch.setattr(preview,'_convert_word',converted)
    for _ in range(2):assert preview.render_upload(None,USER,7,'fixture',lambda:client)[0].startswith(b'%PDF-')
    assert converted.call_count==1
    denied=MagicMock(side_effect=HTTPException(404,'CV not found'));monkeypatch.setattr(preview,'upload_record',denied)
    with pytest.raises(HTTPException):preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert converted.call_count==1
    assert len(preview._cache)==1


@pytest.mark.parametrize('path', ['https://example.invalid/cv.pdf','file:///etc/passwd','gs://fixture/../cv.pdf','gs://fixture/x\\cv.pdf'])
def test_no_url_fetches_or_traversal(original, path):
    row,_,_=original;row['file_path']=path;loader=MagicMock()
    with pytest.raises(HTTPException) as error:preview.render_upload(None,USER,7,'fixture',loader)
    assert error.value.status_code==404;loader.assert_not_called()


def test_size_missing_empty_and_bad_pdf_errors_are_honest(original):
    _,blob,client=original
    blob.size=preview.MAX_SOURCE_BYTES+1
    with pytest.raises(HTTPException) as error:preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert error.value.status_code==413;blob.download_as_bytes.assert_not_called()
    blob.size=0;blob.download_as_bytes.return_value=b''
    with pytest.raises(HTTPException) as error:preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert error.value.status_code==422
    blob.download_as_bytes.return_value=b'Not a PDF'
    with pytest.raises(HTTPException) as error:preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert error.value.status_code==422
    blob.exists.return_value=False
    with pytest.raises(HTTPException) as error:preview.render_upload(None,USER,7,'fixture',lambda:client)
    assert error.value.status_code==404


def test_word_preview_is_bounded_and_never_falls_back_to_network(monkeypatch):
    connection=MagicMock();monkeypatch.setattr(preview,'_UnixConnection',lambda *a,**kw:connection)
    connection.getresponse.return_value=SimpleNamespace(status=200,read=lambda size:b'%PDF-1.7\nfixture')
    assert preview._convert_word(b'fixture','docx').startswith(b'%PDF-')
    connection.request.assert_called_once_with('POST','/convert/docx',b'fixture',{'Content-Type':'application/octet-stream'})
    connection.close.assert_called_once()
    connection.getresponse.return_value=SimpleNamespace(status=422,read=lambda size:b'invalid')
    with pytest.raises(HTTPException) as error:preview._convert_word(b'fixture','doc')
    assert error.value.status_code==422
    connection.request.side_effect=OSError('private server details')
    with pytest.raises(HTTPException) as error:preview._convert_word(b'fixture','docx')
    assert error.value.status_code==503 and 'private' not in error.value.detail


def test_busy_converter_returns_retryable_error():
    preview._conversion_slot.acquire()
    try:
        with pytest.raises(HTTPException) as error:preview._convert_word(b'fixture','docx')
        assert error.value.status_code==429
    finally:preview._conversion_slot.release()


def test_inline_endpoint_auth_headers_and_no_original_overwrite(api, monkeypatch):
    client,db=api
    render=MagicMock(return_value=(b'%PDF-1.7\nfixture','application/pdf'))
    monkeypatch.setattr(preview,'render_upload',render)
    result=client.get('/api/resume-library/7/document')
    assert result.status_code==200 and result.content.startswith(b'%PDF-')
    assert result.headers['cache-control']=='private, no-store'
    assert result.headers['content-disposition']=='inline'
    assert result.headers['x-content-type-options']=='nosniff'
    db.verify_session.return_value=None
    assert client.get('/api/resume-library/7/document').status_code==401
    assert render.call_count==1


def test_viewer_framing_is_same_origin_only_and_main_app_stays_non_embeddable(api):
    client,_=api
    app=client.get('/',follow_redirects=False)
    assert app.headers['x-frame-options']=='DENY'
    assert "frame-ancestors 'none'" in app.headers['content-security-policy']
    assert "frame-src 'self'" in app.headers['content-security-policy']
    viewer=client.get('/static/vendor/pdfjs-6.5.438/web/viewer.html')
    assert viewer.status_code==200
    assert viewer.headers['x-frame-options']=='SAMEORIGIN'
    policy=viewer.headers['content-security-policy']
    assert "frame-ancestors 'self'" in policy
    assert "connect-src 'self' blob: data:" in policy
    assert "script-src 'self' 'wasm-unsafe-eval'" in policy
    assert 'connect-src *' not in policy
    other=client.get('/static/js/main.js')
    assert other.headers['x-frame-options']=='DENY'


def test_document_viewer_runtime_assets_are_packaged():
    root=Path(__file__).resolve().parents[1]/'static/vendor/pdfjs-6.5.438'
    for name in ('build/pdf.mjs','build/pdf.worker.mjs','build/pdf.renderer.mjs','build/pdf.sandbox.mjs',
                 'web/viewer.html','web/viewer.mjs','web/viewer.css','web/locale/locale.json',
                 'web/wasm/openjpeg.wasm','LICENSE'):
        assert (root/name).is_file(), 'Missing self-hosted viewer asset: '+name


def test_worker_rejects_non_word_and_macro_packages_without_running_a_process():
    spec=spec_from_file_location('preview_worker',Path(__file__).resolve().parents[1]/'deploy/vps/preview/worker.py')
    worker=module_from_spec(spec);spec.loader.exec_module(worker)
    assert not worker.valid_word(b'<html>not Word</html>','doc')
    assert not worker.valid_word(b'invalid zip','docx')
    for macros in (False,True):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr('[Content_Types].xml','fixture');archive.writestr('word/document.xml','fixture')
            if macros:archive.writestr('word/vbaProject.bin',b'fixture')
        assert worker.valid_word(stream.getvalue(),'docx') is not macros
    assert 'DisableMacrosExecution' in worker.PROFILE and '<value>true</value>' in worker.PROFILE
