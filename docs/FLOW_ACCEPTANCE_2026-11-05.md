# Recruitment workflow acceptance

## Release

- Date: 5 November 2026.
- Application: https://effortsairecruiter.tech/ on the existing VPS.
- Verified outreach release image: `smarthr-app:clean-20261105t130836z`.
- Image identity: `sha256:2b4d19c2648ae9a93fae900f29aba78d96033458cf0396ebe1d023725586e472`.
- Only SmartHR was recreated. All 20 unrelated containers retained identity and start time.
- The original top-left AI Agent Recruiter logo and mobile header are restored. Efforts Solutions branding remains in recruitment emails and Microsoft approval material.
- Private deployment receipts and rollback material are retained on the server, not in Git.

## Changes

### Outreach and presentation

- Added an in-app email composer with six presets, editable drafts and a branded server-rendered preview.
- Role, explicit work location and explicitly stated salary ranges can prefill from the current query. Candidate nationality, residency and salary are not guessed. Optional authorization/current-salary questions are off by default.
- Preview is required before sending. Changes invalidate the review. Sending is guarded against repeated clicks and ambiguous delivery outcomes; an explicitly selected sending account cannot silently fall back to another mailbox.
- Added private, owner/workspace-scoped saved templates with create, edit, version checks and confirmed soft deletion. Existing global/default templates are unchanged.
- Saved-template defaults replace the current candidate's details with reusable fields. Template syntax is bounded and validated; candidate/query text is literal in the normal composer.
- Meeting choices are derived from connected account capabilities. An unconnected Google account does not appear as an available Meet integration.
- Search progress uses nontechnical copy, truthful backend progress, lightweight animation and reduced-motion support. It does not make additional AI requests.

### Interview lifecycle

- New interviews retain role, explicit time zone and stable organizer-account identity.
- Owners can edit their own interview's role, time, duration, location, interviewer and private notes. The candidate, recipient and organizer are not silently replaced.
- Calendar edits change the existing event, preserving attendees and online-meeting content. Private HR notes are not copied into calendar updates.
- Cancellation also cancels the linked calendar event. It is not a local-only delete. A confirmation is required, and the booking remains as cancelled with an audit record.
- Durable operation records are committed before provider writes. Pending/uncertain operations block another mutation until checked. Reconciliation reads the existing event; it does not create replacement events.
- Completed local changes and audit entries commit atomically. Reconciliation compares time, title, location and cancellation status.
- History is paginated and scoped to the owner/workspace. Cancelled records are read-only. Legacy bookings without a recorded time zone require a deliberate selection before editing; no historical zone was invented.

### Validation, privacy and responsiveness

- Fixed `/api/users` masking an authorization rejection as a server error.
- Company user responses and profile audit snapshots no longer include password hashes.
- Invalid new passwords are checked before writing other profile changes.
- Empty JD requests and malformed skill lists are rejected before calling AI. Blocking JD helpers run off the event loop without changing valid prompts/results.
- Manual JD editing removes the placeholder's icon/centering state.
- Uploaded multiline JD text preserves word boundaries when inserted into the existing single-line search input.
- Removed the artificial dashboard initialization delay.
- Corrected the global-handler diagnostic to recognize namespaced handlers such as schedule history; real missing handlers are still reported.
- A popup opened during a brief restart exposed a JSON parsing error. Interview/template/preview failures now use readable fallback messages. Non-JSON mutation responses still lock the uncertain outcome instead of allowing an unsafe retry; regression tests cover both read and mutation failures.

## Verification

| Area | Evidence | Limit |
| --- | --- | --- |
| Backend suite | 642 passed, zero skipped, against a private PostgreSQL restore | External delivery providers are stubbed in mutation tests |
| Network-isolated provider modes | 610 passed and 32 database-dependent skips in each of auto and DeepSeek modes | The database tests were then run without skips in the restore suite |
| Frontend suites | All 11 DOM suites passed, covering security, state, navigation, integrations, dashboard, polling, admin, product, notifications, outreach and lifecycle | DOM suites complement, not replace, visual checks |
| Migration | Exact deployment SQL rehearsed on a private restore; CV and preexisting booking contents preserved | Not a verified off-site disaster recovery exercise |
| Search compatibility | 105 fixtures; identical tokenization/embeddings; 3,903 tenant vectors; zero top-10 ranking mismatches and score deltas | Equivalence is not a new labeled accuracy benchmark |
| Runtime | 102 installed packages audited; zero known advisories and zero skips; `pip check` and CPU-only image checks passed | No scanner can establish absence of all vulnerabilities |
| Public deployment | Nine asset hashes match; 28 protected read routes return 401 anonymously | No intrusive load or penetration test against the shared production VPS |
| Live browser | Original logo, restored results, all six presets, branded preview, template manager, required fields, interview details/cancel confirmation and connected-provider choices checked | Real records were not edited or cancelled during visual inspection |
| Responsive browser | Desktop 1440, tablet 768 and mobile 390/320 layouts inspected across the affected screens; checked modal/page bounds | Not every screen/state on every physical device |
| Microsoft calendar lifecycle | One explicitly approved fictional Teams event created in the UI, rescheduled once, then cancelled; Microsoft read-back verified time, unchanged join link and subsequent 404; all three notifications received in Gmail | Only this controlled fixture was changed; not a certification of all tenant policies or recurring events |
| Health cost | `/health` and `/health/deep?llm=1` return 200 with zero AI-call delta | This does not disable paid searches explicitly initiated by users |
| Preservation | Users, companies, CVs, embeddings, searches, results, notes, interviews and outreach records preserved | Normal later user actions may change counts |

The observed post-deployment counts were 4 users, 1 company, 4,191 upload records,
4,001 embedding rows, 139 search histories, 6,237 saved results and 2 original interviews.
One approved fictional calendar test was subsequently added, so there are now 3 interview
records, including the retained cancelled fixture. Its edit/cancel operations completed,
and `SCHEDULE_INTERVIEW`, `EDIT_INTERVIEW` and `CANCEL_INTERVIEW` audit entries remain.
No additional recruitment email or paid AI request was initiated by this acceptance run.
An earlier, separately approved branded test email was already received and visually
checked; it was not resent. The approved calendar test sent exactly its native invitation,
update and cancellation, all observed in the recipient inbox. The optional additional
invitation email was off. The original real interviews were not edited or cancelled.

## Performance and cost

- Search prompts, model selection, eligibility rules and ranking behavior were preserved. No quality claim is based solely on faster execution or fewer tests.
- Templates, context prefills, progress animation, previews and template CRUD use zero AI tokens.
- Existing exact-request search coalescing and bounded failure handling remain intact. No background AI health probe was enabled.
- Added owner/date and operation-history indexes for the new paginated schedule and audit views. Database/provider work is off the async event loop.
- Offline warm embedding measurements were approximately 0.082 seconds baseline and 0.079 seconds candidate for the same 12-text batch. These informal single-run timings are not evidence of a statistically established search speedup.
- No verified equal-usage invoice comparison, new monthly bill or before/after per-token price evidence is available. Removing unnecessary calls reduces usage; it does not itself reduce a provider's published token rate. No percentage saving or demand-based explanation was invented. Private billing figures are not published with the source.

## Remaining Limitations

1. The controlled Microsoft organizer create/reschedule/cancel round trip and recipient cancellation delivery passed. Shared-mailbox edge cases, recurring series and other tenant policies are not certified by that one test; unsupported recurring changes fail closed.
2. A disconnected Google calendar cannot be live-tested as connected. No broader Microsoft permissions were granted during these checks.
3. Compose-send guards are not durable cross-device email idempotency. A transactional outbox/provider reconciliation remains future work. Original interview creation also retains its existing partial-failure handling; the new durable ledger covers edits and cancellations.
4. There are 97 embedding rows without usable vectors. Investigate source readability and indexing with scoped approval; do not silently fabricate or bulk replace CV data.
5. Labeled criteria-matching evaluation, agreed concurrency/load testing, off-site restore and failover certification remain outstanding. No "10/10" or issue-free guarantee is justified.
6. GitHub-hosted Actions was blocked by an account billing lock on the preceding published revision. The local/isolated gates above were run directly; publishing a workflow is not evidence that hosted CI ran.
7. TLS was valid with about 35 days remaining at inspection. On-server backups exist, but off-site recovery was not verified.

## Operational Safeguards

The release gate refused active searches, unexpected source/compose drift, unsafe
startup pruning and data/credential mismatches. It retained private rollback material,
ran the migration before activation and checked health and preservation afterward.
Do not automatically resend mail, recreate meetings or retry a calendar mutation after
an ambiguous response. Check the original provider item first. Restoring old application
code must not discard the additive schema, audit operations or newly created records.
