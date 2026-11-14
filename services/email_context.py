"""Bounded email provenance for retrieval only, never candidate qualifications."""
import hashlib
from html.parser import HTMLParser
import re
from email.utils import parseaddr

from services.resume_filters import received_date

MAX_BODY_CHARS = 12_000
MAX_INPUT_CHARS = 200_000
MAX_SUBJECT_CHARS = 250
CONTEXT_VERSION = 1


class _MessageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.quoted_tail = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        labels = ' '.join(attributes.get(key) or '' for key in ('class', 'id')).lower()
        if 'divrplyfwdmsg' in labels or 'moz-cite-prefix' in labels:
            self.quoted_tail = True
        style = (attributes.get('style') or '').replace(' ', '').lower()
        hidden = (tag in {'script', 'style', 'head', 'blockquote', 'template'}
                  or any(label in labels for label in ('gmail_quote', 'gmail_signature', 'divrplyfwdmsg', 'moz-cite-prefix'))
                  or 'display:none' in style or 'visibility:hidden' in style
                  or 'hidden' in attributes)
        skip = hidden or bool(self.stack and self.stack[-1][1])
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, skip))
        if not skip and tag in {'p', 'div', 'br', 'li', 'tr', 'hr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in {'p', 'div', 'li', 'tr'}:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.quoted_tail and (not self.stack or not self.stack[-1][1]):
            self.parts.append(data)


def clean_message(value, *, html=False, limit=MAX_BODY_CHARS):
    if not isinstance(value, str):
        return ''
    text = value[:MAX_INPUT_CHARS]
    if html or re.search(r'</?[a-z][^>]{0,1000}>', text, re.I):
        parser = _MessageText()
        parser.feed(text)
        parser.close()
        text = ''.join(parser.parts)
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_line).strip()
        if re.match(r'^(?:[-_]{2,}\s*(?:original|forwarded) message|begin forwarded message:|on .{1,300}wrote:|from:\s|--\s*$)', line, re.I):
            break
        if re.fullmatch(r'(?:best regards|kind regards|regards|sincerely|sent from my .{1,80})[,.:]?', line, re.I):
            break
        if line.startswith('>'):
            continue
        if line:
            lines.append(' '.join(line.split()))
    return '\n'.join(lines)[:limit].strip()


def build_context(message):
    """Keep ambiguous multi-CV message text for provenance, but never rank by it."""
    if not isinstance(message, dict) or not isinstance(message.get('id'), str) or not message['id']:
        return None
    attachments = message.get('attachments')
    if not isinstance(attachments, list) or not attachments:
        return None
    plain = message.get('body_plain')
    body = clean_message(plain) if isinstance(plain, str) and plain.strip() else clean_message(message.get('body_html'), html=True)
    subject = clean_message(message.get('subject'), limit=MAX_SUBJECT_CHARS).replace('\n', ' ')
    text = '\n'.join(part for part in (subject, body) if part)
    sender = parseaddr(str(message.get('from') or '')[:1000])[1].casefold()[:320]
    date = received_date(message.get('date'))
    return {'text': text, 'metadata': {
        'version': CONTEXT_VERSION, 'purpose': 'retrieval_only',
        'association': 'single_resume' if len(attachments) == 1 else 'shared_message',
        'attachment_count': len(attachments), 'sender': sender,
        'received_at': date.isoformat() if date else None,
        'message_sha256': hashlib.sha256(message['id'].encode()).hexdigest(),
        'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
    }}


def validated_context(value):
    if not isinstance(value, dict) or set(value) != {'text', 'metadata'}:
        raise ValueError('Invalid email context')
    text, metadata = value['text'], value['metadata']
    if (not isinstance(text, str) or len(text) > MAX_BODY_CHARS + MAX_SUBJECT_CHARS + 1
            or '\x00' in text or not isinstance(metadata, dict)
            or set(metadata) != {'version', 'purpose', 'association', 'attachment_count', 'sender',
                                 'received_at', 'message_sha256', 'text_sha256'}
            or type(metadata.get('version')) is not int or metadata['version'] != CONTEXT_VERSION
            or metadata.get('purpose') != 'retrieval_only'
            or type(metadata.get('attachment_count')) is not int or not 1 <= metadata['attachment_count'] <= 1000
            or metadata.get('association') != ('single_resume' if metadata['attachment_count'] == 1 else 'shared_message')
            or not isinstance(metadata.get('message_sha256'), str)
            or not re.fullmatch(r'[a-f0-9]{64}', metadata['message_sha256'])
            or metadata.get('text_sha256') != hashlib.sha256(text.encode()).hexdigest()
            or not isinstance(metadata.get('sender'), str) or len(metadata['sender']) > 320
            or (metadata.get('received_at') is not None and received_date(metadata['received_at']) is None)):
        raise ValueError('Invalid email context')
    return text, metadata
