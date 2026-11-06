"""Bound Office archive expansion before handing documents to parsers."""
import io
from zipfile import BadZipFile, ZipFile

MAX_DOCX_ENTRIES = 2048
MAX_DOCX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_DOCX_XML_BYTES = 16 * 1024 * 1024
REQUIRED_DOCX_PARTS = {'[Content_Types].xml', '_rels/.rels', 'word/document.xml'}


def validate_docx_archive(source):
    """Check directory metadata only; never decompress or extract archive members."""
    try:
        with ZipFile(io.BytesIO(source) if isinstance(source, bytes) else source) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                return False, 'DOCX contains too many archive entries.'
            names = {entry.filename for entry in entries}
            if len(names) != len(entries) or not REQUIRED_DOCX_PARTS <= names:
                return False, 'DOCX must contain a valid Word document package.'
            if sum(entry.file_size for entry in entries) > MAX_DOCX_EXPANDED_BYTES:
                return False, 'DOCX expanded content exceeds the safe processing limit.'
            for entry in entries:
                name = entry.orig_filename
                # Some Word exporters add an empty root-directory marker; no part is read from it.
                if name == '/' and entry.is_dir() and entry.file_size == 0:
                    continue
                if name != entry.filename or name.startswith('/') or '\\' in name or '..' in name.split('/'):
                    return False, 'DOCX contains an invalid archive path.'
                if entry.flag_bits & 1:
                    return False, 'Password-protected DOCX files are not supported.'
                if name.lower().endswith(('.xml', '.rels')) and entry.file_size > MAX_DOCX_XML_BYTES:
                    return False, 'DOCX document content exceeds the safe processing limit.'
        return True, ''
    except (BadZipFile, OSError, ValueError, EOFError, TypeError, AttributeError):
        return False, 'DOCX files must be valid ZIP-based Word documents.'
