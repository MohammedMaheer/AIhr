# Integrations Setup — Teams, Google Meet, Email

This document explains how to enable:

1. **Microsoft Teams** meeting links on scheduled interviews.
2. **Google Meet** meeting links on scheduled interviews.
3. **Email sending** to candidates (shortlist notice, interview invitation,
   rejection, custom) — via SMTP, Gmail, or Outlook/Graph.

Backend workflows exist, but credentials alone do not prove that mail delivery
or meeting creation works. Administrator consent, recruiter connection, provider
licensing/policy and an owner-approved mailbox/calendar acceptance test are
required before production activation. Interviews can be saved with an explicit
meeting/email warning when a provider is unavailable; that is not a successful
online meeting or delivered invitation.

---

## What the app does for you automatically

- New tables (`email_templates`, `interview_emails_sent`, `oauth_tokens`)
  and new columns on `scheduled_interviews` (`meeting_provider`,
  `meeting_join_url`, `meeting_event_id`, `search_result_id`) are created
  on first startup. Idempotent — safe to redeploy.
- Four default global email templates are seeded on first run
  (Shortlist / Interview Invite / Rejection / Blank). Each tenant can edit
  these or add their own via `GET/POST/PUT/DELETE /api/email-templates`.
- The existing **Schedule Interview** modal now has:
  - a provider dropdown (None / Google Meet / Microsoft Teams)
  - a "send invite email" checkbox
- New endpoint `GET /api/integrations/status` returns which integrations are
  configured / connected for the current user.
- New endpoint `POST /api/send-candidate-email` sends a templated email to
  any candidate.

---

## 1. Microsoft Teams (Graph API)

You have two options. **Pick one.**

### Option A — Delegated OAuth (each recruiter signs in once) ✅ recommended

Each recruiter clicks **Connect Microsoft** in the main Settings screen and
signs in. Tokens are stored encrypted. The recruiter is the meeting organiser.
Teams interviews require an eligible Microsoft 365 mailbox, Teams licensing and
organization policy. Do not promise Teams support for personal Microsoft accounts.

1. Go to <https://portal.azure.com> → **Azure Active Directory** →
   **App registrations** → **New registration**.
2. Name: `SmartHR Integration`.
3. Supported account types: *Accounts in any organizational directory and
   personal Microsoft accounts*.
4. Redirect URI (Web): `https://effortsairecruiter.tech/api/oauth/microsoft/callback`
5. After creation, open **Certificates & secrets** → **New client secret** →
   copy the **Value** immediately.
6. Open **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Delegated** → add:
   - `Calendars.ReadWrite`
   - `Mail.Read`
   - `Mail.Send`
   - `User.Read`
   - `offline_access`
7. Have the organization's authorized administrator review the requested access;
   approval requirements depend on its Microsoft policies. Share `/microsoft-approval`.
8. Set credentials through the VPS's secure environment configuration, never Git:
   ```
   MS_TENANT_ID=<your-specific-tenant-guid>
   MS_CLIENT_ID=<Application (client) ID>
   MS_CLIENT_SECRET=<the secret Value>
   MS_REDIRECT_URI=https://effortsairecruiter.tech/api/oauth/microsoft/callback
   ```
9. After a controlled restart, recruiters connect from Settings. Administrator
   approval alone does not connect a recruiter or confirm a live mailbox.

The app uses calendar-backed Teams meetings (`/me/events`), not the standalone
`/onlineMeetings` API. `OnlineMeetings.ReadWrite` is not required. `Mail.Read`
covers Outlook CV imports; `Mail.Send` covers additional candidate email.

### Option B — App-only / client credentials (one shared mailbox)

This is an operator-only alternative, not part of the public delegated approval
request. It can give broad application access and requires a separate security
review and mailbox restrictions. Do not enable it merely to bypass recruiter
sign-in, and do not alter the existing shared registration's grants blindly.

1. Same app registration as above, but add **Application** permissions
   instead of (or in addition to) Delegated:
   - `Calendars.ReadWrite`
   - `Mail.Send`
2. **Grant admin consent** (required for Application permissions).
3. Set on the VPS:
   ```
   MS_TENANT_ID=<your-tenant-guid>
   MS_CLIENT_ID=...
   MS_CLIENT_SECRET=...
   MS_SENDER_USER_ID=interviews@yourdomain.com   # the mailbox to act as
   ```
4. No per-user OAuth needed. The app will request a client_credentials
   token automatically when a recruiter selects "Teams".

The implemented calendar-backed workflow does not need
`OnlineMeetings.ReadWrite.All`. A future standalone-meeting, recording,
transcript or shared-mailbox feature requires its own reviewed permission design;
those permissions must not be added speculatively.

---

## 2. Google Meet (Google Calendar API)

Google Meet links can only be generated as part of a Google Calendar event
on a real user's calendar. You **must** use per-recruiter delegated OAuth
(service accounts cannot create Meet links on Workspace users without
domain-wide delegation, which we intentionally don't ask for).

1. Open <https://console.cloud.google.com> → select / create a project.
2. **APIs & Services** → **Library** → enable:
   - **Google Calendar API**
   - **Gmail API**           ← only if you also want to send mail via Gmail
3. **APIs & Services** → **OAuth consent screen**:
   - User type: **External** (or Internal if Workspace).
   - Scopes (Add): `.../auth/calendar.events`, `.../auth/gmail.send`,
     `openid`, `email`, `profile`.
   - Add yourself as a Test user while in testing mode.
4. **APIs & Services** → **Credentials** → **Create credentials** →
   **OAuth client ID** → **Web application**.
   - Authorised redirect URI:
     `https://effortsairecruiter.tech/api/oauth/google/callback`
5. Copy the Client ID + Client Secret into env vars on the VPS:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   GOOGLE_REDIRECT_URI=https://effortsairecruiter.tech/api/oauth/google/callback
   ```
6. Restart. Recruiters visit
   `https://effortsairecruiter.tech/api/oauth/google/start` to connect.

---

## 3. Email sending

You have **three** transports. The app picks them in this order
(`prefer="auto"`):

1. **Gmail API** — if the recruiter connected their Google account (above).
2. **Microsoft Graph `/sendMail`** — if the recruiter connected Microsoft.
3. **SMTP** — fallback, always works if configured.

You only **need** SMTP for emails to work at all. The OAuth transports are
nice extras that make the email appear sent from the recruiter's personal
mailbox.

### SMTP (recommended baseline)

Pick any provider:

#### Option A — Gmail with App Password
- Enable 2FA on the Google account, then create an **App Password**:
  <https://myaccount.google.com/apppasswords>.
- Env vars on the VPS:
  ```
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=you@yourdomain.com
  SMTP_PASSWORD=<the 16-char app password>
  SMTP_FROM="SmartHR Recruiting <you@yourdomain.com>"
  SMTP_TLS=true
  ```

#### Option B — SendGrid / Mailgun / Postmark / Resend
- Create an SMTP credential in the provider's dashboard.
- Set the four `SMTP_*` env vars to the provider's values (e.g.
  `SMTP_HOST=smtp.sendgrid.net`, `SMTP_USER=apikey`,
  `SMTP_PASSWORD=<api-key>`).

#### Option C — Microsoft 365 SMTP
- Tenant admin must enable SMTP AUTH on the mailbox.
- `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`, etc.

### Wiring env vars into the VPS

On the VPS at `/opt/smarthr/docker-compose.yml`, add the env vars to the
`smarthr-app` service:

```yaml
services:
  smarthr-app:
    environment:
      MS_CLIENT_ID:        "..."
      MS_CLIENT_SECRET:    "..."
      MS_TENANT_ID:        "common"
      MS_REDIRECT_URI:     "https://effortsairecruiter.tech/api/oauth/microsoft/callback"
      MS_SENDER_USER_ID:   ""           # only for app-only mode
      GOOGLE_CLIENT_ID:    "..."
      GOOGLE_CLIENT_SECRET: "..."
      GOOGLE_REDIRECT_URI: "https://effortsairecruiter.tech/api/oauth/google/callback"
      SMTP_HOST:           "smtp.gmail.com"
      SMTP_PORT:           "587"
      SMTP_USER:           "you@yourdomain.com"
      SMTP_PASSWORD:       "..."
      SMTP_FROM:           "SmartHR Recruiting <you@yourdomain.com>"
      SMTP_TLS:            "true"
```

Then `docker compose -f /opt/smarthr/docker-compose.yml up -d`.

---

## Verifying

After deploy, hit:

```
GET /api/integrations/status
```

Example response:

```json
{
  "success": true,
  "google":    { "client_configured": true,  "connected": false, "account_email": null },
  "microsoft": { "client_configured": true,  "connected": false, "tenant_app_only": false },
  "smtp":      { "configured": true, "host": "smtp.gmail.com", "from": "..." }
}
```

Then test:

1. Visit `/api/oauth/google/start` (while logged in) → consent screen →
   redirected back with `?integration=google&status=connected`.
2. Schedule an interview with **Provider = Google Meet** → check the
   response includes `meeting.join_url`. Same for Teams.
3. Schedule an interview with **Send invite email** ticked → candidate
   receives a templated message. Confirm an entry was written to
   `interview_emails_sent`.

---

## API summary (for future frontend work)

| Method   | Path                                          | Purpose                                  |
|----------|-----------------------------------------------|------------------------------------------|
| GET      | `/api/integrations/status`                    | Which integrations are wired             |
| GET      | `/api/oauth/google/start`                     | Begin Google OAuth (302 redirect)        |
| GET      | `/api/oauth/google/callback`                  | Google callback                          |
| GET      | `/api/oauth/microsoft/start`                  | Begin Microsoft OAuth                    |
| GET      | `/api/oauth/microsoft/callback`               | Microsoft callback                       |
| POST     | `/api/oauth/{google\|microsoft}/disconnect`   | Forget the user's token                  |
| GET      | `/api/email-templates?kind=`                  | List templates (company + globals)       |
| POST     | `/api/email-templates`                        | Create company template                  |
| PUT      | `/api/email-templates/{id}`                   | Update company template                  |
| DELETE   | `/api/email-templates/{id}`                   | Delete company template                  |
| POST     | `/api/send-candidate-email`                   | Send templated email to a candidate      |
| POST     | `/api/schedule-interview`                     | Now accepts `meeting_provider`, `send_invite_email`, `email_template_id` |

### Template placeholders (Jinja2)

All templates can use: `{{ candidate_name }}`, `{{ candidate_email }}`,
`{{ position }}`, `{{ company }}`, `{{ recruiter_name }}`,
`{{ recruiter_email }}`, `{{ interview_date }}`, `{{ interview_time }}`,
`{{ interview_location }}`, `{{ meeting_join_url }}`,
`{{ custom_message }}`, `{{ now }}`.

---

## Troubleshooting

OAuth callback session fix (November 5): if an earlier Microsoft/Google return showed `Not authenticated`, start a fresh connection from Settings rather than reloading that callback URL. Login and OAuth start now set the authentication cookie to Secure/HttpOnly/SameSite=Lax; the CSRF cookie remains Strict and unsafe-request validation remains enabled. Existing signed-in sessions receive the corrected cookie when linking starts. Truly missing/expired sessions return to sign-in with a recovery notice and require a fresh connection after login. Use the same browser throughout. See [verification and release details](OAUTH_SESSION_FIX_2026-11-05.md).

| Symptom                                                       | Fix                                                                                       |
|---------------------------------------------------------------|-------------------------------------------------------------------------------------------|
| `Google account not connected`                                | Recruiter must visit `/api/oauth/google/start`.                                           |
| Microsoft Graph HTTP 401/403                                  | Check the connected account, the actual mail/calendar scopes, mailbox licensing and tenant policy. Calendar-backed Teams events use `Calendars.ReadWrite`; do not add standalone meeting or blanket application permissions as a generic fix. |
| SMTP authentication/configuration error                       | Check provider credentials and supported authentication; use an App Password only where the provider allows it. Do not disable MFA. |
| Email outcome unknown (`delivery_unknown`)                    | Check Sent Items and the recipient's inbox before retrying. The app deliberately stops cross-provider fallback after an ambiguous send to reduce duplicate delivery. |
| Calendar outcome unknown (`calendar_event_maybe_created`)     | Check the organizer's calendar before scheduling again; a lost response does not prove that event creation failed. |
| Interview saved but `meeting.error: ... Invalid start time`   | Frontend sent malformed date/time; both fields must be set.                               |
| `Token exchange failed: invalid_grant`                        | Redirect URI mismatch — must match exactly between Azure/Google console and env var.      |
| Templates fail to render                                      | Check the body uses valid Jinja2 syntax; review `interview_emails_sent.error_message`.    |

An accepted send is not proof of Inbox delivery. Provider response bodies and raw credential exception details are no longer exposed in integration errors. A saved unusable personal Microsoft connection requires reconnecting; it must not silently choose the shared app-only mailbox. The scheduling form blocks overlapping submissions but does not provide cross-device/server-side idempotency. See [the failure-hardening verification](INTEGRATION_FAILURE_HARDENING_2026-11-04.md).
