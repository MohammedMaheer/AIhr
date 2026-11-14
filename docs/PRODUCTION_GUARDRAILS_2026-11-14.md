# SmartHR Reliability And Frontend Guardrails

## Scope

Release v2026.11.14.7 preserves the application logo, layouts, search criteria,
score weights, provider selection, credentials, original CVs and existing data.
GitHub billing/CI remediation and off-site backups are excluded at the owner's
request. Existing local backups are retained; no new external storage is added.

## Changes

- Self-host the same Chart.js 4.6.1 distribution resolved by the former unversioned
  CDN URL. Verify exact SHA-256/SHA-384 bytes, retain its license and enforce SRI.
  Remove the unused CDN from script-src. No chart or score configuration changes.
- Move local search schema preparation to explicit, bounded ASGI startup. Ordinary
  and similar retrieval no longer execute DDL or commit schema changes. Missing
  required schema prevents readiness; optional model warmup remains separate.
- Apply SmartHR-only app/database CPU, memory, PID and bounded log policies
  for the inspected shared two-core/8GB VPS. Preserve all persistent mounts and
  exact database binaries. Rehearse database-container recreation on an isolated
  restored named volume before any production restart.
- Add a local five-minute health/capacity timer. It makes no provider call, sends
  no email, and never restarts services automatically. Log only state transitions
  and bounded issue codes. This is local visibility, not external paging.
- Replace the unsupported claim that support was automatically notified with
  an honest instruction to contact the administrator if a display error persists.

## Completed Verification

- 51 focused schema, tenant, similar-scope and operations tests passed locally.
- Full backend suites passed independently in production-matched `auto` and
  `deepseek` configurations: **1,199 passed per configuration**. Five existing
  deprecation warnings remain. Paid providers were mocked and QA was isolated.
- All **27 frontend DOM suites** passed. Three isolated real-browser/API/worker/
  SQL workflows passed for selected search scope, similar profiles and application
  upload/index/shortlist/interview handling. These do not send live invitations.
- The new asset test verified version, digest, SRI and the existing logo.
- Real canvas-pixel checks rendered the existing candidate keyword chart with
  its CDN blocked at 1440px and 390px. Fictional fixtures only; no real AI calls.
  Screenshots were inspected and retained privately.
- The complete reviewed source tree passed redacted secret scanning. Private
  configuration, operational receipts, mailbox data and CVs are not published.

### Live Read-Only Retrieval

Ten live database cases covered selected folders, multiple folders, tags,
uploaded/received date ranges, single-day boundaries and empty scope. Each case
was repeated three times and compared against an independent eligible-ID query:
no out-of-scope result and no missing eligible result within the requested limit.

The final run's per-case median retrieval time was **1.61-28.42 ms**. A separate
32-request, four-worker folder/tag probe completed without errors: **74.76 ms
p50, 116.64 ms p95**, 152.17 ms maximum. It also checked descending similarity
scores. Retrieval ran in a read-only transaction with a stored embedding, without
schema DDL or model inference. These figures measure SQL/vector retrieval only,
not full AI response time, hiring accuracy or sustained production capacity.

## Deployment And Preservation

Runtime source `8f76f64c444fbae60c54096ab8f59aa9eb270fa0` is live in immutable
image `smarthr-app:review-8f76f64-20261114t151213z`. The final documentation-only
attestation does not change that deployed runtime.

- A private PostgreSQL backup restored successfully on an isolated named volume.
  Stopping/removing/recreating that QA database container preserved all 23 table
  fingerprints before production recreation was allowed.
- The live database uses the same pinned database image and existing named
  volume. All **23 business-table fingerprints** still match the pre-rollout
  snapshot. All **7,862 referenced original files** are present and their complete
  before/after SHA-256 sets match (1,635,188,633 bytes checked).
- All **22 unrelated running containers** retained their IDs and start times.
  No global pruning, Docker-daemon restart, unrelated app restart or CV deletion.
- Live app limits are 1.75 CPUs, 3 GiB RAM and 384 PIDs; database limits are
  1 CPU, 2 GiB RAM and 256 PIDs. Each has five rotating 10 MB log files. These
  are shared-host guardrails, not a throughput or availability guarantee.
- The installed five-minute systemd monitor is active and its last run succeeded.
  It confirms both services healthy, log/resource limits present and AI checks
  skipped. Disk usage is **80.65%**, correctly producing a capacity warning.
- HTTPS login, health, security headers, protected-route rejection and deployed
  asset/source hashes passed. Even `/health/deep?llm=true` skipped the paid LLM.
  All release-labeled QA containers, networks and volumes were removed.
- This work added **zero paid AI calls**; the usage-log count remains 247. No
  email/calendar notification or candidate mutation was performed by live checks.

## Boundaries

This is not a blanket 10/10, representative hiring-accuracy certification, live
provider acceptance or 10K/100K/1M-user capacity claim. Email-body retrieval needs
separate source attribution and eligibility tests; bodies are not blindly merged
into CV facts in this release. Broad module rewrites, score changes, new paid
providers, credential rotation and global VPS cleanup are deliberately avoided.

Disk headroom warnings are reported, not hidden by increasing thresholds. The
local timer does not establish off-site disaster recovery or an external alert
delivery path. Exact operational defaults and rollback steps are documented in
`deploy/vps/GUARDRAILS.md`.

Authenticated live desktop/mobile visual acceptance was not performed in this
release because browser URL-policy verification previously stopped access.
The visual evidence above is explicitly isolated QA. No credential rotation,
GitHub billing work or off-site backup setup was attempted, per owner direction.
