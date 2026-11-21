# Zero-Result Usage Reporting And Safe Cleanup

## Correction

`run_hr_scorecard_task` previously completed two early-return paths without the
token summary: no CVs in an explicit scope, and no eligible retrieved candidates
after JD preparation. The latter could have billed preparation calls even though
its missing progress field looked free to a reporting client.

Both paths now persist `token_tracker.get_summary()` and elapsed worker time using
the same fields as normal completion. The provider ledger is unchanged. No extra
inference is introduced; retrieval, strict eligibility, prompts, cache identities,
HR score weights, original logo and UI are unchanged. Historical completed records
are not rewritten or guessed from global provider totals.

## Completed Verification

Deployed runtime: `2f762d8c34d20ccdcb653c046bf83062e38f500d`.

- **1,264 backend tests passed per provider configuration** (`auto` and `deepseek`)
  in isolated production-matched images, with synthetic credentials/mocked AI.
- **27 frontend suites** and **three isolated browser/API/worker workflows** passed.
- **147 targeted regressions** cover durable persistence, both public status/results
  handlers, empty scope, empty retrieval, raw-query fallback, out-of-folder rejection
  and cached preparation. A fixture-only missing timestamp column was corrected
  so the results handler is tested against the real SQL reader, not a mock.
- A **23-table backup restore and persistent-volume recreation rehearsal** passed.
  Deployment preserved all business records and did not restart PostgreSQL.

Both real deployed-worker checks requested ten candidates and correctly returned
zero with a shortfall of ten. Both completed on their first attempt:

| Live Path | Reported Calls | Input Tokens | Output Tokens | Total Tokens | Worker Time |
| --- | --- | --- | --- | --- | --- |
| Existing scoped CVs, but required cold-calling/sales-target skills absent | 2 | 966 | 208 | 1,174 | 3.10 seconds |
| Nonexistent selected folder, rejected before preparation | 0 | 0 | 0 | 0 | 0.00 seconds, rounded |

Every reported call count and token total matched the corresponding provider-ledger
window exactly. Actual deployed status and results handlers returned the same saved
summary under the authorized existing actor; no CV scorecard was generated.
Public HTTPS task status/results URLs correctly rejected unauthenticated requests
with 401. These are live queue/handler checks, not authenticated browser-login
acceptance. Worker times exclude browser and queue delay.

The **entire paid acceptance cost was two successful calls / 1,174 tokens**.
There were no failed provider calls. Empty-scope, health, transport, integrity and
cleanup checks added no paid AI calls. No additional role/scorecard generation was
needed to verify this reporting-only change.

## Conservative Disk Review

The image dependency audit found no safe install-only QA-image targets under the
retention guards: their layers remain referenced by retained images. No Docker
image, container or volume is selected for removal, and an unused cleanup tool
will not be added to the application.

Cleanup is restricted to hash-verified redundant release sources and the exact
transfer archive created for this rollout. The archive can be removed only after
successful deployment, a complete matching extracted source snapshot, verified
archive bytes and an unmounted path. Extracted active/rollback snapshots, images,
CV originals, database/configuration backups and other applications remain intact.

Actual cleanup removed two verified obsolete source artifacts and this rollout's
redundant transfer archive. Filesystem free space increased by **57,556,992 bytes**
(57.6 MB) around the cleanup step. The archive was checked against the local Git
transfer bytes and complete retained extracted-source manifest before removal.

**575 backup files**, including legacy source/configuration backup directories,
were hash-identical before/after cleanup. All containers, including stopped ones,
kept their identities, start times, image references and mounts during cleanup.
The database and **22 unrelated running applications** also retained their
identities/start times across rollout. No Docker image, container or volume was
pruned, and no package/cache dependency needed by another app was removed.

This is **gross cleanup savings, not net whole-rollout savings**. The initial disk
snapshot had 18,860,621,824 free bytes; after rollout/testing/cleanup the measured
free space was 18,790,690,816 bytes. Retained release artifacts and concurrent
writes offset the cleanup. Monitoring reported **81.74% used**, still a capacity
warning. Larger deletion was not justified under the preservation constraints.

## Preservation

All **7,862 original referenced CV files** were hash-identical before/after, with
none missing. The complete resume-index row checksum was unchanged, including
embedding vectors, CV text, derived profiles, folders, tags, dates and email
context/provenance. No candidate-data or historical task-summary rewrite occurred.

Twenty of 23 business tables were unchanged after live acceptance; only task
records, search history and provider usage changed as expected. Cached analyses
and search results were unchanged. Served asset/source hashes, login, security
headers, protected-route authentication and explicit no-AI deep-health probes
passed. Resource limits/log rotation remain active, and temporary QA resources
were removed. There were no mailbox sends, calendar notifications or UI/logo edits.

## Limits

Safe savings may be modest because retained backups, image layers and unrelated
applications are deliberately untouched. Report actual reclaimed bytes rather
than summed virtual image sizes. New reporting fields apply to newly completed
tasks only. No population-wide accuracy or fresh live visual acceptance is claimed.
Keys, GitHub CI billing and off-site backup provisioning were not changed.
