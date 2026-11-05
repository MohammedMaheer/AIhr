# SmartHR Visual And Integration Acceptance

Date: November 5, 2026 (Asia/Calcutta). Application: https://effortsairecruiter.tech/.

## Implemented Fixes

- `static/js/dashboard-ui.js` provides the admin mobile drawer, backdrop, automatic closure after navigation, keyboard containment, Escape recovery and focus restoration. All six admin dialog-opening paths use shared modal isolation and labels; background scrolling is locked while a dialog is open.
- `templates/dashboard.html` names icon/search controls, routes the profile button correctly and limits active navigation styling to sidebar links. Narrow header text fits its controls. Generated edit-dialog fields and legacy role/company selects receive associated labels without changing form names or values.
- User creation no longer offers ignored welcome-email/password-change switches or falsely announces an email was sent. Unverified hardcoded plan prices were removed; plan values and account-creation behavior are unchanged. The uploaded-resume count is labeled as uploaded, not AI-analyzed.
- `main.py:read_root` supplies actual configured result-count and email-scan limits to `templates/index.html`. Search/import controls use these bounds and validate before submitting. Production currently allows up to 25 candidates and 50 emails per import, rather than displaying unsupported 100/1000 limits.
- `static/js/main.js` uses a compact search header, correct singular result labels, a clearer Compose Email command, guarded JD generation and disabled empty-preview exports. A corrupt local history cache no longer prevents application initialization. Existing successful data/ranking/provider behavior is preserved.
- `static/css/style.css` centers the mobile match-score circle, wraps long identity text and retains touch/focus/reduced-motion handling. Login password visibility has an accessible state, errors are announced and the footer year updates automatically.
- Narrow admin section headings and filters wrap without squeezing titles or search inputs; tables retain their own labeled horizontal scroll regions.
- `static/js/notifications.js` and `static/css/components.css` provide one bounded notification stack: four messages maximum, exact consecutive duplicates suppressed, safe text, named dismissal controls and persistent errors. Status messages no longer occupy the same position on top of each other. Search, login and admin navigation use the existing Efforts Solutions logo.
- Both scheduling dialogs now collect job title, company and explicit time zone. Additional email invitations require a job title and valid recipient. Server checks reject invalid dates/time zones, past interview times, oversized fields, header line breaks and unsafe meeting URLs before provider side effects.
- `services/email_branding.py` provides a responsive Efforts Solutions email header/footer and removes active HTML and unsafe links. `services/email_service.py` renders untouched built-in invitations with readable dates, time zone/UTC offset, duration and a short Join interview button. Stored templates are not overwritten; custom text and template variables remain supported.

## Browser Evidence

| Screen or workflow | Observed coverage |
| --- | --- |
| Login/session | Normal stored-credential sign-in succeeded; session-expiry recovery copy and redirect checks passed. No credentials were extracted, changed or published. |
| Recruiter search | Actual 320, 390, 768 and 1440 px geometry/screenshots; no page-wide overflow, clipped sampled heading/button/label controls or broken images. Desktop/mobile search fields reserve button space. |
| Admin dashboard/navigation | Desktop and 320/390 px review; actual drawer closure on navigation, focus on close control and background isolation checked. |
| Admin company dialog | Live 390 px keyboard check: Shift+Tab wraps to Cancel; Escape closes, restores the Add Company trigger, unlocks the page and keeps the mobile sidebar inactive. No company was created. |
| Admin user/profile/integrations | User modal opened without submission; unsupported switches absent. Profile route works; integration state displays the saved Microsoft account. Labels/header highlight were corrected after the first pass. |
| Upload/Outlook | 320 px import form fits; saved account is shown, password is optional for Outlook, and the actual 50-email maximum reaches the DOM. No attachments were imported in this pass. |
| Settings/reports | 320 px connection controls fit. Reports use their own horizontal table scrolling and retain pagination without expanding the page. |
| Existing candidate report | Authenticated report GET rendered scorecard, timeline, keywords and actions; 320/390 px layout fits. Mobile score-circle center delta is zero and contact text stays within its container. No HR decisions or notes were modified. |
| Scheduling | Existing candidate dialog opened and dismissed without submission. Latest general dialog checked at 320 px: enabling the additional invite makes job title and recipient required; empty job title and invalid email prevent submission and focus the invalid field. No meeting or actual interview invitation was created by these checks. |
| JD builder/notifications | 320 px form labels fit; empty Copy/Download are disabled. Repeating Generate with an empty job title produced one readable, named, dismissible error, not duplicate alerts; no AI request was made. Automated suites cover generation duplicate guards, manual preview edits and failure recovery. |
| Delivered email | Exactly one approved fictional test message was sent through the application's connected Microsoft HR mailbox. Microsoft accepted it, Gmail's connected recipient account confirmed it in Inbox, and the actual Gmail message was opened for visual review. The Efforts Solutions logo loaded at its intended 200 px width. It explicitly states that it is not an invitation, offer or calendar booking. |
| Browser console | Zero captured errors/warnings in the final sampled recruiter session. This is not an indefinite monitoring guarantee. |

Screenshots remain in local audit output, outside the published source tree. Browser control was interrupted and then restored; observed checks were resumed rather than represented as uninterrupted certification.

## Automated And Live-Service Evidence

| Check | Result |
| --- | --- |
| Backend | 537 passed, no skips, on an isolated PostgreSQL restore using non-secret example configuration; temporary restore removed. Six existing deprecation/read-only pytest-cache warnings remain. |
| Offline provider modes | 521 passed, 16 DB-dependent skips each for auto and DeepSeek; the restore suite covers those cases. |
| Frontend | Nine suites passed: security, candidate state, navigation, integrations, dashboard, polling/submission reuse, admin UI, product controls and notifications. JavaScript syntax passed. |
| Ranking | 105 synthetic inputs; identical tokenization/384-dimensional embeddings; 3,903 stored tenant vectors; zero top-10 mismatch or score delta. |
| Dependencies | 102 installed Python packages scanned, zero skipped and zero known advisories at scan time; CPU-only image and dependency consistency checks passed. |
| Real AI acceptance | One fictional CV/JD through the actual backend/provider functions: two DeepSeek calls, 3,842 input and 1,578 output tokens, 8.57 seconds. Complete scorecard; all five explicit skills matched; matching location/experience retained and wrong location rejected. Repeating the identical keyword assessment made zero extra provider calls. No real candidate data or business records were involved. |
| Microsoft | Existing encrypted account remains usable with unchanged identity/permissions; Graph profile, mailbox-metadata and calendar reads returned 200, with Teams supported. One approved test email was accepted, audited and confirmed in the recipient Inbox. No calendar event was created; that acceptance gate remains open. |
| Health/security | Public asset hashes match the tested release. Protected anonymous requests remain 401; callback recovery checks pass. Health/deep-health returned 200 with zero AI-call counter increase during a quiet interval. |
| Network | Existing gzip delivered the 456,621-byte main JS as 82,477 bytes, about 82% smaller, with public one-hour cache headers. One sampled fetch took 212 ms; this is not global p95 latency. No reverse-proxy change was needed. |

## Deployment

Release `20261105T110646Z` was activated as `smarthr-app:clean-20261105t110646z`, image ID `sha256:9a1f1bf51b587f72ab7177db2d5700f9bfe0d17db0825c5a0260567111dd1f71`. Guarded activation verified business data, encrypted OAuth credentials and all 20 unrelated containers. Private rollback material is retained. No passwords, permission grants, candidates or notes were changed by the visual checks. The sole intentional outbound side effect was the approved fictional test email and its audit record; zero events or AI calls were made by that email test.

## Remaining Gates

1. GitHub Actions reports an account billing lock before any job steps run. Source publishing is authorized and available, but hosted CI cannot be called green until the owner resolves that lock; no billing changes were made by this audit.
2. Controlled mailbox attachment import and Teams/calendar creation still need acceptance. One branded Microsoft email is now confirmed delivered, but that does not certify every recipient, mail client or spam policy. Compose Email remains a standard mail-client action; Graph delivery was tested separately through the application's actual email service. A local-file browser preview and mail-app navigation were blocked by browser policy and were not bypassed; visual mail verification used the actual approved message received in Gmail.
3. Labeled CV/JD precision/recall and production whole-search p50/p95 are not yet measured. One synthetic acceptance case and unchanged embeddings do not prove universal matching accuracy. Name-only/identity intent is not a certified exact-name filter; historical semantic results must not be described as exact identity matches.
4. 97 existing documents have no usable text/vector. Classify scanned, encrypted, legacy DOC and non-CV content before adding OCR/reindexing. Never fill a candidate count with off-criteria or fabricated results.
5. Durable cross-device outreach idempotency, off-site disaster recovery, sustained load/failover, physical Safari/mobile and complete WCAG acceptance remain separate work. These checks improve the application; they do not establish an issue-free or minimum-possible-token guarantee.
