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
- Prepare SmartHR-only app/database CPU, memory, PID and bounded log policies
  for the inspected shared two-core/8GB VPS. Preserve all persistent mounts and
  exact database binaries. Rehearse database-container recreation on an isolated
  restored named volume before any production restart.
- Add a local five-minute health/capacity timer. It makes no provider call, sends
  no email, and never restarts services automatically. Log only state transitions
  and bounded issue codes. This is local visibility, not external paging.
- Replace the unsupported claim that support was automatically notified with
  an honest instruction to contact the administrator if a display error persists.

## Verification Checkpoint

- 51 focused schema, tenant, similar-scope and operations tests passed locally.
- The new asset test verified version, digest, SRI and the existing logo.
- Real canvas-pixel checks rendered the existing candidate keyword chart with
  its CDN blocked at 1440px and 390px. Fictional fixtures only; no real AI calls.
  Screenshots were inspected and retained privately.
- Full production-runtime regressions, persistent-volume recreation rehearsal,
  rollout, local monitor installation and final preservation checks are pending
  at this source checkpoint. Only completed evidence will be attested afterward.

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
