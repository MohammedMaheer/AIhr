"""
email_service.py
================

Send customised emails to candidates (shortlist notice, interview invite,
rejection, custom). Supports three transports, in order of preference:

  1. **SMTP** (always available as a fallback) — configured via env vars
     SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM, or via
     config.json `email.smtp` section.
  2. **Microsoft Graph `/sendMail`** — when the recruiter has connected
     their Microsoft account (delegated) OR an app-only sender is configured.
  3. **Gmail API `users.messages.send`** — when the recruiter has connected
     their Google account.

Template rendering uses Jinja2 with autoescape on. Templates can reference
context vars: candidate_name, position, company, recruiter_name,
recruiter_email, interview_date, interview_time, interview_location,
meeting_join_url, custom_message.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any, Optional

import requests
from jinja2 import Environment, BaseLoader, select_autoescape

log = logging.getLogger(__name__)

# Sandbox Jinja env — templates come from DB strings, never the filesystem.
_jinja = Environment(loader=BaseLoader(),
                     autoescape=select_autoescape(["html", "xml"]),
                     trim_blocks=True, lstrip_blocks=True)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _load_email_config() -> dict:
    cfg: dict = {}
    try:
        with open("config.json", "r") as f:
            cfg = (json.load(f) or {}).get("email", {}) or {}
    except Exception:
        cfg = {}

    smtp = cfg.setdefault("smtp", {})
    smtp["host"]     = os.getenv("SMTP_HOST",     smtp.get("host")) or None
    _port_env = os.getenv("SMTP_PORT", "").strip()
    smtp["port"]     = int(_port_env) if _port_env else int(smtp.get("port") or 587)
    smtp["user"]     = os.getenv("SMTP_USER",     smtp.get("user")) or None
    smtp["password"] = os.getenv("SMTP_PASSWORD", smtp.get("password")) or None
    smtp["from"]     = os.getenv("SMTP_FROM",     smtp.get("from") or smtp.get("user")) or None
    smtp["use_tls"]  = str(os.getenv("SMTP_TLS", smtp.get("use_tls", True))).lower() not in ("0", "false", "")
    return cfg


def email_config() -> dict:
    return _load_email_config()


# ---------------------------------------------------------------------------
# Templating
# ---------------------------------------------------------------------------
def render_template(subject_tpl: str, body_tpl: str, ctx: dict) -> tuple[str, str]:
    """Render subject + body Jinja templates with `ctx`. Returns (subject, body)."""
    try:
        subj = _jinja.from_string(subject_tpl or "").render(**ctx)
    except Exception as e:
        log.warning(f"subject template render failed: {e}")
        subj = subject_tpl or ""
    try:
        body = _jinja.from_string(body_tpl or "").render(**ctx)
    except Exception as e:
        log.warning(f"body template render failed: {e}")
        body = body_tpl or ""
    return subj, body


def build_default_context(*, candidate_name: str, candidate_email: str,
                          position: Optional[str] = None,
                          company: Optional[str] = None,
                          recruiter_name: Optional[str] = None,
                          recruiter_email: Optional[str] = None,
                          interview_date: Optional[str] = None,
                          interview_time: Optional[str] = None,
                          interview_location: Optional[str] = None,
                          meeting_join_url: Optional[str] = None,
                          custom_message: Optional[str] = None,
                          extras: Optional[dict] = None) -> dict:
    ctx = {
        "candidate_name": candidate_name or "Candidate",
        "candidate_email": candidate_email or "",
        "position": position or "the role",
        "company": company or "our company",
        "recruiter_name": recruiter_name or "The Recruitment Team",
        "recruiter_email": recruiter_email or "",
        "interview_date": interview_date or "",
        "interview_time": interview_time or "",
        "interview_location": interview_location or "",
        "meeting_join_url": meeting_join_url or "",
        "custom_message": custom_message or "",
        "now": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    if extras:
        ctx.update(extras)
    return ctx


# ---------------------------------------------------------------------------
# Transport 1: SMTP
# ---------------------------------------------------------------------------
def _send_via_smtp(to: str, subject: str, body_html: str,
                   body_text: Optional[str] = None,
                   from_addr: Optional[str] = None) -> dict:
    cfg = email_config().get("smtp") or {}
    host = cfg.get("host")
    user = cfg.get("user")
    pwd  = cfg.get("password")
    sender = from_addr or cfg.get("from") or user
    if not (host and sender):
        return {"success": False, "provider": "smtp",
                "error": "SMTP not configured (SMTP_HOST / SMTP_FROM required)"}
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    # Always attach HTML last so most clients show it.
    msg.attach(MIMEText(body_html or body_text or "", "html", "utf-8"))
    port = int(cfg.get("port") or 587)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                if user and pwd:
                    s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                if cfg.get("use_tls", True):
                    try:
                        s.starttls()
                        s.ehlo()
                    except smtplib.SMTPException:
                        pass
                if user and pwd:
                    s.login(user, pwd)
                s.sendmail(sender, [to], msg.as_string())
        return {"success": True, "provider": "smtp", "error": None}
    except Exception as e:
        return {"success": False, "provider": "smtp", "error": f"SMTP send failed: {e}"}


# ---------------------------------------------------------------------------
# Transport 2: Microsoft Graph /sendMail
# ---------------------------------------------------------------------------
def _send_via_graph(token: str, sender_user: Optional[str],
                    to: str, subject: str, body_html: str) -> dict:
    who = sender_user or "me"
    base = (f"https://graph.microsoft.com/v1.0/users/{who}"
            if who != "me" else "https://graph.microsoft.com/v1.0/me")
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": body_html},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": True,
    }
    try:
        r = requests.post(
            f"{base}/sendMail",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            data=json.dumps(payload), timeout=20,
        )
        if r.status_code >= 400:
            return {"success": False, "provider": "microsoft",
                    "error": f"Graph sendMail {r.status_code}: {r.text[:300]}"}
        return {"success": True, "provider": "microsoft", "error": None}
    except Exception as e:
        return {"success": False, "provider": "microsoft", "error": f"Graph sendMail failed: {e}"}


# ---------------------------------------------------------------------------
# Transport 3: Gmail API
# ---------------------------------------------------------------------------
def _send_via_gmail(token: str, sender_email: Optional[str],
                    to: str, subject: str, body_html: str) -> dict:
    msg = MIMEText(body_html, "html", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    if sender_email:
        msg["from"] = sender_email
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    try:
        r = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            data=json.dumps({"raw": raw}), timeout=20,
        )
        if r.status_code >= 400:
            return {"success": False, "provider": "gmail",
                    "error": f"Gmail send {r.status_code}: {r.text[:300]}"}
        return {"success": True, "provider": "gmail", "error": None}
    except Exception as e:
        return {"success": False, "provider": "gmail", "error": f"Gmail send failed: {e}"}


# ---------------------------------------------------------------------------
# Public send
# ---------------------------------------------------------------------------
def send_email(*, to: str, subject: str, body_html: str,
               body_text: Optional[str] = None,
               prefer: str = "auto",
               organizer_user_id: Optional[int] = None,
               db=None) -> dict:
    """Send an email to a single recipient.

    `prefer`:
      - "auto" (default): try recruiter's connected Google → Microsoft → SMTP.
      - "smtp" / "gmail" / "microsoft": force a specific transport.

    Returns {success, provider, error}.
    """
    if not to:
        return {"success": False, "provider": "none", "error": "Missing recipient"}

    # Defer-import to avoid circular ref with calendar_service.
    from services.calendar_service import _get_valid_token  # type: ignore

    order: list[str]
    if prefer == "smtp":
        order = ["smtp"]
    elif prefer in ("gmail", "google"):
        order = ["gmail", "smtp"]
    elif prefer in ("microsoft", "graph", "teams", "outlook"):
        order = ["microsoft", "smtp"]
    else:
        order = ["gmail", "microsoft", "smtp"]

    last_err = None
    for transport in order:
        if transport == "smtp":
            res = _send_via_smtp(to, subject, body_html, body_text)
        elif transport == "gmail":
            if not (organizer_user_id and db):
                continue
            tok, email = _get_valid_token("google", organizer_user_id, db)
            if not tok:
                continue
            res = _send_via_gmail(tok, email, to, subject, body_html)
        elif transport == "microsoft":
            if not (organizer_user_id and db):
                continue
            tok, who = _get_valid_token("microsoft", organizer_user_id, db)
            if not tok:
                continue
            res = _send_via_graph(tok, who, to, subject, body_html)
        else:
            continue
        if res.get("success"):
            return res
        last_err = res.get("error")
    return {"success": False, "provider": "none",
            "error": last_err or "No email transport is configured. "
                                 "Connect Gmail/Outlook or set SMTP_* env vars."}


# ---------------------------------------------------------------------------
# Default templates (seeded into DB on first run by main.py)
# ---------------------------------------------------------------------------
DEFAULT_TEMPLATES: list[dict] = [
    {
        "kind": "shortlist",
        "name": "Default — Shortlisted",
        "subject": "You're shortlisted for {{ position }} at {{ company }}",
        "body": (
            "<p>Hi {{ candidate_name }},</p>\n"
            "<p>Great news — your profile stood out, and we'd love to move you "
            "forward in our hiring process for the <strong>{{ position }}</strong> "
            "role at <strong>{{ company }}</strong>.</p>\n"
            "{% if custom_message %}<p>{{ custom_message }}</p>{% endif %}\n"
            "<p>We'll be in touch shortly with the next steps. If you have any "
            "questions in the meantime, reply directly to this email.</p>\n"
            "<p>Best regards,<br>{{ recruiter_name }}<br>{{ company }}</p>"
        ),
        "is_default": True,
    },
    {
        "kind": "interview_invite",
        "name": "Default — Interview Invite",
        "subject": "Interview invitation: {{ position }} at {{ company }}",
        "body": (
            "<p>Hi {{ candidate_name }},</p>\n"
            "<p>Thanks for your interest in the <strong>{{ position }}</strong> "
            "role at <strong>{{ company }}</strong>. We'd like to invite you to "
            "an interview.</p>\n"
            "<ul>\n"
            "  <li><strong>Date:</strong> {{ interview_date }}</li>\n"
            "  <li><strong>Time:</strong> {{ interview_time }}</li>\n"
            "{% if meeting_join_url %}"
            "  <li><strong>Join link:</strong> "
            "<a href=\"{{ meeting_join_url }}\">{{ meeting_join_url }}</a></li>\n"
            "{% elif interview_location %}"
            "  <li><strong>Location:</strong> {{ interview_location }}</li>\n"
            "{% endif %}"
            "</ul>\n"
            "{% if custom_message %}<p>{{ custom_message }}</p>{% endif %}\n"
            "<p>Please confirm the slot by replying to this email. Looking "
            "forward to speaking with you.</p>\n"
            "<p>Best regards,<br>{{ recruiter_name }}<br>{{ company }}</p>"
        ),
        "is_default": True,
    },
    {
        "kind": "rejection",
        "name": "Default — Polite Rejection",
        "subject": "Update on your application for {{ position }}",
        "body": (
            "<p>Hi {{ candidate_name }},</p>\n"
            "<p>Thank you for taking the time to apply for the "
            "<strong>{{ position }}</strong> role at <strong>{{ company }}</strong>. "
            "After careful consideration, we've decided to move forward with other "
            "candidates whose experience more closely matches our current needs.</p>\n"
            "{% if custom_message %}<p>{{ custom_message }}</p>{% endif %}\n"
            "<p>We genuinely appreciate your interest and wish you the very best "
            "in your job search.</p>\n"
            "<p>Best regards,<br>{{ recruiter_name }}<br>{{ company }}</p>"
        ),
        "is_default": True,
    },
    {
        "kind": "custom",
        "name": "Default — Blank",
        "subject": "{{ position }} at {{ company }}",
        "body": (
            "<p>Hi {{ candidate_name }},</p>\n"
            "<p>{{ custom_message }}</p>\n"
            "<p>Best regards,<br>{{ recruiter_name }}<br>{{ company }}</p>"
        ),
        "is_default": False,
    },
]
