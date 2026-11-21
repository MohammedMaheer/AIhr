# Recruiter Workflow Reliability Review

## Findings And Fixes

| Priority | Finding | Change |
| --- | --- | --- |
| High | An open application form could submit question numbers after a page edit. A page could also close while the application was validating its CV. | `get_public_application_page` provides the revision. `submit_public_application` checks it before processing and rechecks the published page and active company under a short transaction before reserving the submission. |
| High | Any successful HTTP status, including a gateway's HTML response, could display an application receipt without a successful API write. | The application frontend requires explicit success and retains the draft on a failure. Initial load failures are retryable and distinct from a closed page. |
| Medium | Changing question order or wording made saved answers ambiguous. | Store the original question beside each answered field using an additive JSONB column. Recruiters see the historical prompt, with numeric labels for older applications that predate snapshots. |
| Medium | An older job-page response could render after the company selection was cleared. A late CV response could open a preview after refreshing the library. | Invalidate old workspace responses, abort obsolete library reads, and only open a preview from a current row. Add retry controls for failed workspace reads. |
| Medium | Recent searches could show a perpetual loader or an empty state during an outage. Dates and match badges wrapped on desktop. | Display a bounded, retryable failure and accept responses only for the current dashboard request. Keep compact columns readable without changing overall layout. |

## Verification

- **1,304 passed** in an isolated PostgreSQL/pgvector environment with synthetic
  secrets, plus **5 subtests**. This includes opt-in Chromium-to-HTTP-to-Postgres
  flows for application intake/review/interview and exact/similar search scopes.
- **27 frontend suites passed**. Tests cover dashboard recovery, job-page changes
  during submission, stale responses, native form validation, document preview,
  search scope, bulk upload, mail-import UI and keyboard/dialog states.
- Chromium fixture checks passed at **320, 390, 600, 900, 1,280 and 1,440 px**.
  Additional dashboard, scheduling, history, JD builder, settings, administration,
  and native document-render checks passed at four widths. Desktop and mobile
  screenshots were inspected, and PDF canvases were checked for visible content.
- VPS deployment was scoped to SmartHR. Public health and exact static asset
  bytes were verified post-switch. The database fingerprints checked during
  deployment, other container identities, logo and AI ledger remained unchanged.
  All 7,862 referenced CV originals matched their pre-deployment SHA-256 hashes.
- The previous image and Compose configuration were retained. The migration is
  additive: image rollback does not require dropping answer snapshots or backfilling
  older records. The runtime dependency set was unchanged.

## Remaining Limits

Older responses do not have a reliable question snapshot; displaying an inferred
prompt would misrepresent what the applicant answered. Clients without a revision
field remain supported; the final transaction still rechecks the page and company.

Provider responses and paid model output were not requalified live in this pass.
No real emails or calendar invitations were sent, and no paid AI calls were made.
The VPS is still a single-host deployment. External alerts, an approved off-site
restore drill, and sustained concurrency/latency measurements remain separate
production-readiness work.
