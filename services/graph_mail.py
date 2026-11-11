"""Bounded Graph mailbox reads with safe pagination and explicit failures."""
import base64
import hashlib
import re
import time
from urllib.parse import quote, urlsplit

import requests


MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_IMPORT_BYTES = 50 * 1024 * 1024
# Graph requires the sort field first in $filter; retain all message dates.
ATTACHMENT_MESSAGE_FILTER = "receivedDateTime ge 0001-01-01T00:00:00Z and hasAttachments eq true"


def _graph_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "graph.microsoft.com"
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or not parsed.path.startswith("/v1.0/")):
        raise ValueError("Unsafe Microsoft Graph pagination URL.")
    return url


def _get(session, url, params=None):
    _graph_url(url)
    for attempt in range(3):
        response = session.get(url, params=params, timeout=(5, 30), allow_redirects=False)
        if response.status_code in (429, 503):
            try:
                delay = max(0, float(response.headers.get("Retry-After", 2 ** attempt)))
            except (ValueError, TypeError):
                delay = 2 ** attempt
            if attempt == 2 or delay > 20:
                raise RuntimeError("Microsoft mailbox is busy or throttled. Retry the import later.")
            response.close()
            time.sleep(delay)
            continue
        if response.status_code == 401:
            raise RuntimeError("Microsoft connection expired. Reconnect the mailbox in Integrations.")
        if response.status_code == 403:
            raise RuntimeError("Microsoft denied mailbox access. Approve Mail.Read and reconnect the mailbox.")
        if response.status_code != 200:
            raise RuntimeError(f"Microsoft mailbox read failed (HTTP {response.status_code}); no empty import was reported.")
        data = response.json()
        response.close()
        if not isinstance(data, dict):
            raise RuntimeError("Invalid Microsoft Graph response.")
        return data


def _pages(session, url, *, params=None, max_pages=100):
    seen = set()
    for _ in range(max_pages):
        if url in seen:
            raise RuntimeError("Microsoft returned a repeated pagination link.")
        seen.add(url)
        data = _get(session, url, params)
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")
        if not url:
            return
        _graph_url(url)
        params = None
    raise RuntimeError("Microsoft pagination exceeded the safe import limit. Use a smaller import.")


def collect_resume_mail(token, limit, *, include_attachment, classify_context, identity_scope=""):
    limit = max(1, min(int(limit), 500))
    results, total_bytes = [], 0
    with requests.Session() as session:
        session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
        messages = _pages(session, "https://graph.microsoft.com/v1.0/me/messages", params={
            "$filter": ATTACHMENT_MESSAGE_FILTER, "$top": min(limit, 100),
            "$orderby": "receivedDateTime desc", "$select": "id,subject,from,receivedDateTime,body,hasAttachments"})
        for index, message in enumerate(messages):
            if index >= limit:
                break
            message_id = message["id"]
            subject = message.get("subject") or "No Subject"
            body = (message.get("body") or {}).get("content") or ""
            related = classify_context(subject, body)
            base = "https://graph.microsoft.com/v1.0/me/messages/" + quote(message_id, safe="") + "/attachments"
            attachments = []
            for attachment in _pages(session, base, max_pages=20):
                filename = attachment.get("name") or ""
                if attachment.get("isInline") or not include_attachment(filename, related):
                    continue
                if attachment.get("@odata.type", "#microsoft.graph.fileAttachment") != "#microsoft.graph.fileAttachment":
                    continue
                if int(attachment.get("size") or 0) > MAX_ATTACHMENT_BYTES:
                    raise RuntimeError("A resume attachment exceeds the 20 MB limit. Import it separately.")
                data = attachment
                if not data.get("contentBytes"):
                    data = _get(session, base + "/" + quote(attachment["id"], safe=""))
                encoded = data.get("contentBytes") or ""
                if len(encoded) > (MAX_ATTACHMENT_BYTES * 4 // 3) + 8:
                    raise RuntimeError("A resume attachment exceeds the 20 MB limit.")
                try:
                    content = base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError) as exc:
                    raise RuntimeError("Microsoft returned an invalid attachment; no partial import was accepted.") from exc
                if not content:
                    continue
                total_bytes += len(content)
                if total_bytes > MAX_IMPORT_BYTES or len(content) > MAX_ATTACHMENT_BYTES:
                    raise RuntimeError("Mailbox import exceeds 50 MB. Reduce the message limit.")
                clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)[:180]
                identity = hashlib.sha256(
                    (identity_scope + ":" + message_id + ":" + attachment["id"]).encode()).hexdigest()[:16]
                attachments.append({"filename": f"graph_{identity}_{clean}", "original_filename": filename,
                                    "content": content, "content_type": data.get("contentType") or "application/octet-stream",
                                    "stable_identity": True})
            if attachments:
                results.append({"id": message_id, "from": ((message.get("from") or {}).get("emailAddress") or {}).get("address", "Unknown"),
                                "subject": subject, "date": message.get("receivedDateTime") or "Unknown",
                                "body_plain": body, "body_html": "", "snippet": body[:500],
                                "attachments": attachments, "has_resume_attachment": True})
    return results
