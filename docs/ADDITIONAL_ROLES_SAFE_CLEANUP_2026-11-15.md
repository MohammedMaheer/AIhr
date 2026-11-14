# Additional Role Acceptance And Safe Cleanup

## Scope

Release v2026.11.15.2 changes only the reviewed release-source cleanup tool and
its tests/documentation. Application code, logo, UI, provider settings, strict
CV eligibility and HR scoring remain unchanged. Real CVs and backups are retained.

## Cleanup Safeguard

The prior cleanup wrapper compared its dry-run and applied target sets only
after deletion. Although targets were independently verified and constrained to
redundant SmartHR source artifacts, this did not bind deletion to the operator's
reviewed plan. Applying now requires the dry-run `plan_sha256`. The digest binds
target paths, receipt evidence and canonical container identities/mounts. A changed
plan is rejected before removal, and source hashes are rechecked during apply.

Active/mounted releases, the two newest deployed snapshots and the current
predecessor remain protected. No CV, backup, private configuration, Docker image,
container, volume or unrelated application file is a cleanup target.

## Completed Verification

Deployed runtime: `7bdd1d02867ce76f7b980b72cf97f9fa87603eef`.
Production-matched isolated suites passed **1,260 tests per provider configuration**
(`auto` and `deepseek`, synthetic credentials and mocked inference). This includes
12 focused cleanup regressions. All **27 frontend suites** passed. A 23-table backup
restore and persistent-volume recreation rehearsal passed before rollout.

Seven live durable-worker searches completed on their first attempt:

| Role / Requirement | Requested / Returned | Result |
| --- | --- | --- |
| HR Recruiter; Recruitment | 10 / 10 | Ten fresh provider scorecards; descending scores 91, 90, 90, 89, 88, 88, 84, 84, 79, 77. |
| Network Engineer; at least 15 years; base CCNA | 10 / 0 | Correct exact-credential rejection: the CV lists completed CCNA Security, not the separately requested base CCNA. Its experience requirement passed. |
| Same experience requirement; CCNA Security | 10 / 1 | Exact listed credential accepted; score 93; truthful shortfall of nine. |
| Identical CCNA Security repeat | 10 / 1 | Same scorecard/score, cached; zero new provider calls or tokens. |
| Graphic Designer; Photoshop | 10 / 1 | Full-CV scorecard 79; truthful shortfall of nine. |
| Salesforce Developer; 3-5 years; Salesforce and CRM | 10 / 1 | Full-CV scorecard 93; the CV states nearly four years of relevant experience. |
| Sales Executive; cold calling and sales targets | 10 / 0 | The sales-tagged Salesforce developer lacks those required skills and was excluded. An organizational tag is not proof of role eligibility. |

Every returned candidate was independently checked against CV source text, tenant,
folder, tag, selected date basis/range, required skills and strict scorecard criteria.
Scores were finite, descending and consistent across stored results and nested
scorecards. No weaker candidates were added to satisfy a ten-result request.
The networking source explicitly states total experience of 15 years and names
CCNA Security among completed certifications; the rejection was not a lost CV or
an experience-parsing failure. No matching or scoring rule was relaxed.

Ten additional read-only stored-vector folder/tag/date combinations passed,
including multiple selections and upload-versus-received dates, with zero
out-of-scope rows. Thirty-two retrievals at concurrency four had zero errors and
208.87 ms p95. These are stored-vector retrieval measurements, not full AI latency
or a large-scale load test.

## Measured API Usage

This session added **40 successful provider calls**, **96,190 input tokens** and
**30,549 output tokens**, totaling **126,739 tokens**. No provider failures occurred.
The HR search used fresh scorecards, not the previously saved versions; it alone
used 80,797 tokens. All other positive CV cohorts contained one candidate each to
bound additional inference. No model, prompt, scoring or provider setting changed.

The exact networking search took 12.14 seconds of worker processing; its cached
repeat took 0.03 seconds and added zero calls/tokens. These figures exclude browser
and queue delay, and cache expiry/restart can require preparation calls again.
Cleanup, health checks and read-only retrieval probes made no paid AI calls.

One existing observability gap remains: zero-hit completion after JD preparation
omits the task-level token summary. The provider ledger correctly recorded 1,175
preparation tokens for the sales-mismatch search, with no candidate scorecard
generated. Session totals above include those tokens; a missing summary is not
treated as zero cost. Adding that summary is a narrowly scoped follow-up, not a
reason to change search/scoring behavior in this operations-only release.

## Cleanup And Preservation

Applied the reviewed digest-bound plan and removed **eight redundant source
artifacts**, reclaiming **174,645,248 bytes** (174.6 MB / 166.6 MiB) as measured by
filesystem free space immediately before/after cleanup. This is gross cleanup
savings, not net release growth: the new image, backup and rollback source copies
were retained. Disk usage after rollout, testing and cleanup was **80.52%**, still
a capacity warning. No global Docker pruning was attempted.

All **116 retained backup files** were hash-identical before/after cleanup. Every
container, including stopped containers, retained its identity, start time, image
reference and mounts during cleanup. The running database and **22 unrelated
running applications** also retained their identities/start times across rollout.
The two newest deployed source snapshots and the active predecessor remain intact.

All **7,862 original referenced CVs** were hash-identical before/after, with none
missing. A whole-index checksum verified unchanged CV text, embedding vectors,
tenant/folder/bucket scope, tags, dates and email context/provenance. The existing
scorecard-save path refreshed derived candidate profiles normally; no bulk reindex
or manual candidate-data rewrite was performed. Seventeen business tables were
unchanged; the six expected changed tables hold task/history/results, provider
usage, cached analyses and derived resume profiles.

HTTPS health, login, protected-route authentication, CSRF-aware unauthenticated
rejection and served source/asset hashes passed. Explicit `llm=true` health checks
still skipped inference. Monitoring, resource limits and log rotation remain active;
temporary QA resources were removed. No mailbox sends or calendar notifications
were made, and the logo/UI/application source is unchanged from v2026.11.15.1.

## Limits

These are bounded source-reviewed examples, not a population-wide hiring-accuracy
percentage, 10/10 reliability guarantee or fresh authenticated live-browser visual
audit. The tests use the actual deployed queue, worker, database and provider under
an authorized existing account, rather than a browser-authentication acceptance
claim. Automatic tags are organizational filters, not verified qualifications.
Broader disk cleanup requires ownership-specific review; genuine candidate files,
backups and shared Docker resources remain protected. No keys, CI billing or
off-site backup provisioning was changed.
