"""Safe presentation for recruitment mail without changing delivery semantics."""
from datetime import date, datetime, time
from html import escape
import os
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from lxml import html

BRAND = "Efforts Solutions"
_TAGS = {"a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3", "h4",
         "hr", "i", "img", "li", "ol", "p", "span", "strong", "table", "tbody", "td",
         "th", "thead", "tr", "u", "ul"}
_DROP = {"script", "style", "iframe", "object", "embed", "form", "input", "button",
         "meta", "link", "base", "svg", "math", "video", "audio"}


def safe_url(value, *, mailto=False):
    if not isinstance(value, str) or any(c in value for c in "\r\n\x00"):
        return False
    try:
        parsed = urlsplit(value)
        if mailto and parsed.scheme == "mailto":
            return bool(parsed.path) and not parsed.query
        return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def display_time(day, clock, zone="UTC"):
    if not day or not clock:
        return day or "", clock or ""
    local = datetime.combine(date.fromisoformat(day), time.fromisoformat(clock)).replace(tzinfo=ZoneInfo(zone or "UTC"))
    offset = local.strftime("%z")
    date_text = f"{local.strftime('%A')}, {local.day} {local.strftime('%B %Y')}"
    time_text = local.strftime("%I:%M %p").lstrip("0") + f" ({zone or 'UTC'}, UTC{offset[:3]}:{offset[3:]})"
    return date_text, time_text


def branded_html(body, *, company=BRAND):
    if not isinstance(body, str) or len(body) > 262144:
        raise ValueError("Email content is too large")
    document = html.document_fromstring(body or "<p></p>", parser=html.HTMLParser(no_network=True))
    container = document.find("body")
    if container is None:
        raise ValueError("Email content cannot be empty")
    for node in list(container.iterdescendants()):
        if not isinstance(node.tag, str):
            node.drop_tree()
            continue
        tag = node.tag.lower()
        if tag in _DROP:
            node.drop_tree()
            continue
        if tag not in _TAGS:
            node.drop_tag()
            continue
        allowed = {"a": {"href", "title"}, "img": {"src", "alt", "width", "height"},
                   "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}}.get(tag, set())
        for attr in list(node.attrib):
            if attr not in allowed:
                del node.attrib[attr]
        if tag == "h2":
            node.set("style", "margin:0 0 20px;font:600 22px/1.3 Arial,sans-serif;color:#20252d;")
        if tag in {"td", "th"}:
            node.set("style", "padding:6px 16px 6px 0;vertical-align:top;text-align:left;")
        if tag == "a":
            if not safe_url(node.get("href"), mailto=True):
                node.attrib.pop("href", None)
            node.set("style", "color:#155e75;word-break:break-word;overflow-wrap:anywhere;")
            if node.text_content().strip() == "Join interview" and node.get("href"):
                node.set("style", "display:inline-block;padding:13px 22px;background:#155e75;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;")
        if tag == "img" and not safe_url(node.get("src")):
            node.drop_tree()
    if not container.text_content().strip() and not container.findall(".//img"):
        raise ValueError("Email content cannot be empty")
    content = escape(container.text or "") + "".join(html.tostring(child, encoding="unicode") for child in container)
    base = os.getenv("PUBLIC_BASE_URL", "https://effortsairecruiter.tech").rstrip("/")
    if not safe_url(base):
        base = "https://effortsairecruiter.tech"
    logo = escape(base + "/static/review/efforts-solutions-logo.png", quote=True)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;background:#f3f5f7;color:#20252d;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f5f7;"><tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e1e5eb;">'
        '<tr><td style="background:#171c24;padding:26px 28px;">'
        f'<img src="{logo}" width="200" alt="Efforts Solutions" style="display:block;width:200px;max-width:100%;height:auto;border:0;">'
        '<div style="font:13px Arial,sans-serif;color:#ffffff;margin-top:12px;">Recruitment</div></td></tr>'
        '<tr><td style="padding:28px;font:15px/1.65 Arial,Helvetica,sans-serif;color:#20252d;word-break:break-word;">'
        + content +
        '</td></tr><tr><td style="padding:18px 28px;border-top:1px solid #e1e5eb;font:12px/1.6 Arial,sans-serif;color:#5b6470;">'
        f'{escape(company or BRAND)}<br>Recruitment correspondence powered by Efforts Solutions'
        '</td></tr></table></td></tr></table></body></html>'
    )
