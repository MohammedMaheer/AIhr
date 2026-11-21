# Multi-Role Ten-Candidate Acceptance

## Method

Use the normal authenticated production search UI with ten candidates requested.
Choose small, real, company-owned cohorts by folder, tag and email-received dates.
Review source CV evidence privately before defining expected candidate sets.
Independently validate returned membership, date/tag/folder scope, strict parsed
criteria, finite descending scores and consistent nested/database scores.
No candidate selection, emails, calendar events or original-file edits occur.
Private CVs, contact information and raw receipts are not published.

## Observations Before Deployment

| Scenario | Requested | Returned | Worker Time | Tokens |
| --- | ---: | ---: | ---: | ---: |
| Accountant: Accounts Payable and Excel | 10 | 10 | 35.57 s | 77,343 |
| Identical accounting repeat | 10 | 10 | 2.61 s | 1,138 |
| DevOps: 4-6 years, Terraform and Azure | 10 | 1 | 11.74 s | 17,704 |
| Designer: Adobe Illustrator, partial indexed skills | 10 | 0 (defect) | Retry occurred | See usage ledger |

Accounting has exactly ten source-supported matches in a 13-CV scoped cohort;
all ten returned with scores 92 through 88. Its repeat reused all ten scorecards,
preserved scores and ordering, and used about 98.5% fewer tokens on this sample.
The two-CV infrastructure cohort contains only one supported DevOps match;
the other was assessed but correctly excluded rather than padding the request.

The design cohort exposed a retrieval defect: a genuine design CV explicitly
lists Adobe Illustrator, while its partial profile only contains other skills.
Retrieval treated the absent indexed term as a proven failure before full CV
verification. The focused fix supplements query-specific source evidence in
runtime profiles and the already-scoped SQL supplemental pool. Final strict
scorecard verification remains mandatory; a text mention is not a hiring decision.

## Post-Deployment Acceptance

| Scenario | Requested | Returned | Worker Time | Tokens |
| --- | ---: | ---: | ---: | ---: |
| Same Illustrator design query after fix | 10 | 1 | 11.42 s | 9,654 |
| Accounting repeat after restart | 10 | 10 | 2.47 s | 1,134 |
| Accounting repeat at mobile width | 10 | 10 | 1.64 s | 1,138 |

The recovered design result is the source-reviewed Illustrator-qualified CV;
its score is 67, not an inflated strong-fit score. Accounting retained the exact
same ten candidates and scores after restart and at mobile width. Independent
folder, tag and uploaded-date exclusions returned zero before and after release.
Post-deploy empty scopes did not reuse the populated accounting results.
All real requests used a count of ten. Thirteen search submissions completed:
twelve acceptance scenarios passed, and one retained pre-fix reproduction
documents the corrected design defect. No assessment/provider failure occurred;
one pre-fix task needed a second claim while worker processes recycled.

Read-only post-deploy retrieval checks used an existing stored vector, not model
inference: accounting/design/infrastructure exact SQL and runtime sets agreed
with 10/1/1 matches, with median retrieval times 28.92/11.22/10.01 ms respectively
over three repetitions. These exclude query embedding, AI and network latency.
Ten additional folder/tag/uploaded/received-date cohort probes had no scope leaks.

## Regression And Release Gates

- 108 profile and precision tests passed locally.
- 30 real PostgreSQL tenant/criteria/parity tests passed locally.
- Desktop/mobile browser-to-API-to-worker-to-SQL workflow passed, completing ten
  fictional searches with provider mocks. This is not live-provider evidence.
- All 1,152 tests passed independently under both auto and DeepSeek configurations
  using the VPS's installed dependencies in isolated, network-restricted QA.
- All 23 frontend suites passed. No logo, CSS, template, scoring prompt, score
  weight, result-count rule, source CV, provider key or production schema changed.
- Backup/restore matched all 23 business-table fingerprints. Deployment preserved
  those records and all unrelated container identities/start times. Eighteen
  reviewed original documents retained identical hashes across the release.
- The deployed code revision is `49e4f8511968839aed6d4c2b848c3f5b07668966`,
  source tree `0205030e7646818fc280935ef010a5d26acefae2`, image
  `smarthr-app:review-49e4f85-20261114t060952z`.
  This follow-up documentation does not modify that tested runtime code.
- Health/login checks returned 200; protected anonymous APIs returned 401;
  served assets and runtime source hashes matched. Deep health skipped AI and
  added no provider calls. No isolated QA containers remained.
- Live UI actions exercised scopes and results at desktop/mobile dimensions.
  The mobile screenshot and DOM confirmed ten results and no horizontal overflow
  at 390 px. Desktop DOM flows passed, but desktop screenshot capture produced
  an incomplete compositor image and artifact export was denied; this is not a
  full desktop pixel-level visual certification. Temporary sizing was reset.

## API Budget

This round's usage-ledger delta was 42 successful provider calls, 84,199 input
and 26,205 output tokens, 110,404 total. At conservative peak uncached input/output
rates of USD 0.30/1.20 per million tokens, that is approximately USD 0.05671.
Cached/off-peak billing may be lower; this is an estimate, not an invoice.
Rates: [DeepSeek official pricing](https://api-docs.deepseek.com/quick_start/pricing/).
Read-only cohort planning, original-file hashes, SQL parity, local tests and
health checks made no paid AI calls.

## Limitations

These cohorts establish exact eligibility and score consistency for reviewed
samples, not universal recall, objective percentage accuracy, globally optimal
ranking among unassessed CVs, or predictive validity of employment outcomes.
One pre-fix design task was reclaimed while workers recycled; its second attempt
completed. The precise recycling trigger was not isolated. Worker lifecycle
latency remains worth monitoring under traffic. Hosted GitHub CI has separately
been blocked by account billing; local/runtime tests do not mean hosted CI passed.
Normal search history and provider usage records are retained as audit evidence.
Token estimates use recorded provider usage, not an invoice or a pricing guarantee.
