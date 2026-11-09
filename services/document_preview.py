"""Authorized original-document previews. No AI, public URLs or external viewers."""
from collections import OrderedDict
import hashlib
import http.client
import os
import socket
import threading
import time

from fastapi import HTTPException
from services.resume_library import source_location, upload_record

MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_PDF_BYTES = 32 * 1024 * 1024
CACHE_BYTES = 64 * 1024 * 1024
CACHE_TTL = 300
_cache = OrderedDict()
_cache_lock = threading.Lock()
_conversion_slot = threading.BoundedSemaphore(1)


class _UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(os.environ.get('DOCUMENT_PREVIEW_SOCKET', '/run/preview/renderer.sock'))


def _cache_get(key):
    with _cache_lock:
        now = time.monotonic()
        for old in list(_cache):
            if _cache[old][0] <= now:
                del _cache[old]
        value = _cache.get(key)
        if value:
            _cache.move_to_end(key)
            return value[1]


def _cache_put(key, content):
    with _cache_lock:
        _cache[key] = (time.monotonic() + CACHE_TTL, content)
        _cache.move_to_end(key)
        size = sum(len(value[1]) for value in _cache.values())
        while size > CACHE_BYTES:
            _, value = _cache.popitem(last=False)
            size -= len(value[1])


def _convert_word(content, extension):
    if not _conversion_slot.acquire(blocking=False):
        raise HTTPException(429, 'Another Word preview is being prepared. Try again shortly.')
    connection = _UnixConnection('preview', timeout=40)
    try:
        connection.request('POST', '/convert/' + extension, content, {'Content-Type':'application/octet-stream'})
        response = connection.getresponse()
        output = response.read(MAX_PDF_BYTES + 1)
        if response.status == 422:
            raise HTTPException(422, 'This Word document may be damaged or password-protected. Download the original to open it.')
        if response.status != 200 or not output.startswith(b'%PDF-') or len(output) > MAX_PDF_BYTES:
            raise HTTPException(503, 'The document preview could not be prepared. Try again or download the original.')
        return output
    except (OSError, http.client.HTTPException) as error:
        raise HTTPException(503, 'Word preview is temporarily unavailable. Try again or download the original.') from error
    finally:
        connection.close()
        _conversion_slot.release()


def _decode_text(content):
    if content.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
        return content.decode('utf-32', errors='replace')
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        return content.decode('utf-16', errors='replace')
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return content.decode('cp1252', errors='replace')


def render_upload(db, user, upload_id, default_bucket, client_factory):
    # Ownership is checked on every request, including cache hits.
    row = upload_record(db, user, upload_id)
    bucket, key = source_location(row['file_path'], row['gcs_bucket_name'] or default_bucket)
    if not bucket or not key or '\\' in key or '\x00' in key or any(part in ('', '.', '..') for part in key.split('/')):
        raise HTTPException(404, 'CV not found')
    extension = key.rsplit('.', 1)[-1].lower()
    if extension not in ('pdf', 'doc', 'docx', 'txt'):
        raise HTTPException(415, 'This file type has no document preview. Download the original to open it.')
    try:
        blob = client_factory().bucket(bucket).blob(key)
        if not blob.exists():
            raise HTTPException(404, 'The original document is unavailable. An extracted text view may still be available.')
        if blob.size is None and hasattr(blob, 'reload'):
            blob.reload()
        if blob.size is not None and blob.size > MAX_SOURCE_BYTES:
            raise HTTPException(413, 'This document is too large for an inline preview. Download the original to open it.')
        content = blob.download_as_bytes(end=MAX_SOURCE_BYTES, timeout=20)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(503, 'The original document could not be loaded. Try again or download it.') from error
    if not content:
        raise HTTPException(422, 'This document is empty.')
    if len(content) > MAX_SOURCE_BYTES:
        raise HTTPException(413, 'This document is too large for an inline preview. Download the original to open it.')
    if extension == 'txt':
        return _decode_text(content).encode('utf-8'), 'text/plain'
    if extension == 'pdf':
        if not content.lstrip()[:1024].startswith(b'%PDF-'):
            raise HTTPException(422, 'This PDF could not be previewed. Download the original to open it.')
        return content, 'application/pdf'
    digest = hashlib.sha256(content).hexdigest()
    cache_key = (row['company_id'], row['id'], bucket, key, extension, digest)
    cached = _cache_get(cache_key)
    if cached:
        return cached, 'application/pdf'
    converted = _convert_word(content, extension)
    _cache_put(cache_key, converted)
    return converted, 'application/pdf'
