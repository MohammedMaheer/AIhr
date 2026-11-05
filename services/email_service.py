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
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any, Optional

import requests
from jinja2 import BaseLoader, TemplateError, nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

from services.integration_errors import provider_failure

log = logging.getLogger(__name__)

_jinja = ImmutableSandboxedEnvironment(loader=BaseLoader(), autoescape=True,
                                     trim_blocks=True, lstrip_blocks=True)
_jinja.globals.clear()
_jinja.filters = {name: _jinja.filters[name] for name in
                  ("escape", "e", "default", "d", "lower", "upper", "title", "capitalize", "trim")}
_ALLOWED_NODES = (nodes.Template, nodes.Output, nodes.TemplateData, nodes.Name,
                  nodes.Const, nodes.If, nodes.Compare, nodes.Operand,
                  nodes.And, nodes.Or, nodes.Not, nodes.Filter, nodes.CondExpr)
_MAX_TEMPLATE = 32768
_MAX_RENDERED = 262144


def validate_template(template: str) -> None:
    """Allow substitutions, safe filters and conditions, not executable Jinja."""
    if not isinstance(template, str) or len(template) > _MAX_TEMPLATE:
        raise ValueError("Email templates must be text of at most 32,768 characters.")
    try:
        tree = _jinja.parse(template)
        pending = [(tree, 0)]
        count = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if depth > 32 or count > 1000 or not isinstance(node, _ALLOWED_NODES):
                raise ValueError("Email templates support named variables, conditions and basic text filters only.")
            if isinstance(node, nodes.Name) and node.name.startswith("_"):
                raise ValueError("Private template variables are not allowed.")
            if isinstance(node, nodes.Filter) and node.name not in _jinja.filters:
                raise ValueError("This email template filter is not supported.")
            pending.extend((child, depth + 1) for child in node.iter_child_nodes())
    except (TemplateError, RecursionError) as exc:
        raise ValueError("Invalid email template syntax.") from exc


def _render_bounded(template: str, ctx: dict, *, html: bool) -> str:
    validate_template(template)
    context = {}
    if not isinstance(ctx, dict) or len(ctx) > 100:
        raise ValueError("Invalid email template context.")
    for key, value in ctx.items():
        if not isinstance(key, str) or key.startswith("_") or type(value) not in (str, int, float, bool, type(None)):
            raise ValueError("Email template variables must be simple values.")
        if len(str(value)) > 8192:
            raise ValueError("Email template variable is too long.")
        context[key] = value
    try:
        compiled = _jinja.overlay(autoescape=html).from_string(template)
        parts, length = [], 0
        for part in compiled.generate(**context):
            length += len(part)
            if length > _MAX_RENDERED:
                raise ValueError("Rendered email is too large.")
            parts.append(part)
        return "".join(parts)
    except TemplateError as exc:
        raise ValueError("Email template could not be rendered safely.") from exc


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
    subj = _render_bounded(subject_tpl or "", ctx, html=False)
    body = _render_bounded(body_tpl or "", ctx, html=True)
    if "\r" in subj or "\n" in subj:
        raise ValueError("Email subjects cannot contain newlines.")
    return subj, body


def build_default_context(*, candidate_name: str, candidate_email: str,
                          position: Optional[str] = None,
                          company: Optional[str] = None,
                          recruiter_name: Optional[str] = None,
                          recruiter_email: Optional[str] = None,
                          interview_date: Optional[str] = None,
                          interview_time: Optional[str] = None,
                          time_zone: Optional[str] = None,
                          duration_minutes: Optional[int] = None,
                          interview_location: Optional[str] = None,
                          meeting_join_url: Optional[str] = None,
                          custom_message: Optional[str] = None,
                          extras: Optional[dict] = None) -> dict:
    ctx = {
        "candidate_name": candidate_name or "Candidate",
        "candidate_email": candidate_email or "",
        "position": position or "Career opportunity",
        "company": company or "Efforts Solutions",
        "recruiter_name": recruiter_name if recruiter_name and recruiter_name.casefold() not in {"super admin", "admin", "administrator"} else "Recruitment Team",
        "recruiter_email": recruiter_email or "",
        "interview_date": interview_date or "",
        "interview_time": interview_time or "",
        "interview_location": interview_location or "",
        "meeting_join_url": meeting_join_url or "",
        "custom_message": custom_message or "",
        "time_zone": time_zone or "UTC",
        "duration_minutes": duration_minutes or "",
        "now": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    from services.email_branding import display_time
    ctx["interview_date_display"], ctx["interview_time_display"] = display_time(
        interview_date, interview_time, time_zone or "UTC")
    if extras:
        ctx.update(extras)
    return ctx


def render_candidate_email(subject_tpl, body_tpl, ctx):
    """Upgrade only untouched built-in templates; preserve custom template text."""
    for template in DEFAULT_TEMPLATES:
        if subject_tpl == template["subject"] and body_tpl == template["body"]:
            if template["kind"] == "interview_invite":
                body_tpl = (
                    "<h2>Interview invitation</h2><p>Dear {{ candidate_name }},</p>"
                    "<p>We would like to invite you to interview for <strong>{{ position }}</strong> at <strong>{{ company }}</strong>.</p>"
                    "<table><tr><td><strong>Date</strong></td><td>{{ interview_date_display }}</td></tr>"
                    "<tr><td><strong>Time</strong></td><td>{{ interview_time_display }}</td></tr>"
                    "{% if duration_minutes %}<tr><td><strong>Duration</strong></td><td>{{ duration_minutes }} minutes</td></tr>{% endif %}"
                    "{% if interview_location and not meeting_join_url %}<tr><td><strong>Location</strong></td><td>{{ interview_location }}</td></tr>{% endif %}</table>"
                    "{% if meeting_join_url %}<p><a href=\"{{ meeting_join_url }}\">Join interview</a></p>{% endif %}"
                    "{% if custom_message %}<p>{{ custom_message }}</p>{% endif %}"
                    "<p>Please reply to confirm your availability or request another time.</p>"
                    "<p>Kind regards,<br>{{ recruiter_name }}<br>{{ company }}</p>"
                )
            break
    subject, content = render_template(subject_tpl, body_tpl, ctx)
    from services.email_branding import branded_html
    return subject, branded_html(content, company=ctx.get("company"))


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
    submission_started = accepted = False
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as s:
                if user and pwd:
                    s.login(user, pwd)
                submission_started = True
                s.sendmail(sender, [to], msg.as_string())
                accepted = True
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.ehlo()
                if cfg.get("use_tls", True):
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                if user and pwd:
                    s.login(user, pwd)
                submission_started = True
                s.sendmail(sender, [to], msg.as_string())
                accepted = True
        return {"success": True, "provider": "smtp", "error": None}
    except Exception as e:
        log.warning("SMTP transport error: %s", type(e).__name__)
        if accepted:
            return {"success": True, "provider": "smtp", "error": None}
        rejected = isinstance(e, (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
                                  smtplib.SMTPDataError))
        return provider_failure("smtp", "email", uncertain=submission_started and not rejected)


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
            log.warning("Graph sendMail rejected: status=%s", r.status_code)
            return provider_failure("microsoft", "email", status_code=r.status_code)
        return {"success": True, "provider": "microsoft", "error": None}
    except Exception as e:
        log.warning("Graph sendMail outcome unavailable: %s", type(e).__name__)
        return provider_failure("microsoft", "email")


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
            log.warning("Gmail send rejected: status=%s", r.status_code)
            return provider_failure("gmail", "email", status_code=r.status_code)
        return {"success": True, "provider": "gmail", "error": None}
    except Exception as e:
        log.warning("Gmail send outcome unavailable: %s", type(e).__name__)
        return provider_failure("gmail", "email")


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
            tok, who = _get_valid_token("microsoft", organizer_user_id, db, delegated_actor=True)
            if not tok:
                continue
            res = _send_via_graph(tok, who, to, subject, body_html)
        else:
            continue
        if res.get("success"):
            return res
        if res.get("delivery_unknown"):
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
