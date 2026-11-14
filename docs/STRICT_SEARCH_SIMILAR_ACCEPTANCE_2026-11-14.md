# Strict Search And Similar Profile Acceptance

## Scope

Release v2026.11.14.6 adds a separate, explicit similar-profile preview after a
zero-result exact search. Strict eligibility, existing score weights, logo,
original files, folder/tag/date semantics and candidate actions are preserved.
The preview uses local embeddings and existing indexed CV text, not a paid
provider. It is not a verified HR scorecard and makes no exact-match promise.

## Correctness Fixes

- Parse location clauses correctly when followed by numeric qualifications;
  do not parse the role before "based in" as the requested city.
- Treat recognized old address-parser duty fragments as unknown locations;
  do not reject genuine CVs solely on those corrupt indexed values. Future
  extraction uses word-bounded labels and the earliest known header place.
  Final AI/source eligibility verification still applies.
- Preserve selected company/folders/tags/date basis and range in the new
  preview. Omit the folder field for all authorized folders; reject an explicit
  empty folder selection. Never expand scope to fill a requested count.
- Require authentication, CSRF, company quota, validation and rate limits.
  Bound the retrieval pool, skill count and output size. Escape profile fields;
  cancel stale client requests and keep original exact search results intact.

## Local Verification

- 118 focused profile/precision tests passed.
- 14 new service/API tests and five real PostgreSQL scope tests passed, including
  disabled-ranking profile parity, an HNSW fixture, disconnect checks, capacity
  limits and real HTTP rate limiting. The final combined import/API/SQL sequence
  passed all 24 tests after fixing an existing import-smoke fixture that leaked
  replacement modules into later tests. This was caught before the first deploy.
- All 26 frontend DOM suites passed, including opt-in, fixed scope,
  all-folders handling, escaping and stale-response cleanup.
- Opt-in localhost browser/HTTP/worker/PostgreSQL workflows passed for existing
  search scopes and the new zero-result/similar path at 1440px and 390px widths.
  Screenshots were inspected; no horizontal overflow or dialog clipping found.
  These workflows use fictional CVs and mocked paid providers, not live AI.

## Live Verification

The first deployed checkpoint `0456086` passed all 1,177 tests in each isolated
production-runtime provider configuration. Backup restore matched all 23 tables,
restart preserved business records and unrelated containers, and runtime/static
hashes matched. Health checks added zero paid calls. Subsequent preview-only
hardening and its final production gates are recorded below.

Four real searches used the existing authorized principal and normal durable
submission/worker path over SSH. This is live backend/provider acceptance, not
a live browser session or HTTP-authentication acceptance. Each requested ten:

| Role And Hard Requirements | Returned | Worker Time | Task Tokens |
| --- | ---: | ---: | ---: |
| Data Analyst: Abu Dhabi, 0-5 years, SQL and Power BI | 1 | 13.89 s | 19,025 |
| Sales Manager: Abu Dhabi, 10-25 years, Sales and CRM | 0 | 12.76 s | 9,175 |
| HR Recruiter: Dubai, 20-25 years, Recruitment and Onboarding | 0 | 10.95 s | 17,014 |
| Accountant: Accounts Payable and Excel | 10 | 26.09 s | 77,801 |

Independent source review verified the expected sets, strict criteria,
folder/tag/received-date membership, unique files, descending scores, score
consistency and truthful shortfalls. Data's score was 77; accounting scores were
92/92/91/90/89/89/88/88/88/86. The sales sample was correctly excluded: a past
Abu Dhabi employer was not accepted as its current Sharjah address. No task
retry/provider failure occurred. The 29 original source files were unchanged
at preflight; integrity is rechecked at final acceptance.

Measured ledger delta was 38 successful calls, 92,712 input and 30,303 output
tokens, 123,015 total. Accounting regenerated its assessments; the anticipated
old-cache reuse was not observed and no token reduction is claimed for that run.
No paid calls were made by local QA, source review, scope probes or health checks.

Ten read-only stored-vector scope probes passed with no out-of-scope results;
sample median retrieval times were approximately 2-33 ms. These exclude query
embedding, AI generation and network latency and are not end-to-end timings.

## Preview Hardening

- Offer only for a freshly executed search in the original live user/workspace
  context. Saved history without that context must be rerun first; it cannot
  silently change a tenant-specific search into an admin-wide preview.
- Preserve indexed details even when advanced ranking is disabled. Materialize
  the selected tenant subset before ANN ranking for unfiltered previews too.
  Default exact-search paths and ranking weights are unchanged.
- Skip new inference after a detected disconnect. Bound count queries to five
  seconds, preview SQL statements to ten seconds and local preview inference
  to two concurrent workers per process. Client aborts do not kill an already
  running Python embedding thread; capacity remains held until it finishes.
- Post-deploy diagnostics reproduced first-use DDL lock contention while a
  read-only probe held a table snapshot. The preview now skips optional runtime
  schema initialization entirely: it only reads the already-installed schema,
  retaining its SQL deadline. A regression rejects any preview-time schema DDL.
  Default exact-search initialization is unchanged.

## Final Deployment

- Deployed source `fd9cdaebde17254900f7d4b583dbf1a4fc480fda`, tree
  `949e1ef5e89a0c51a9636576f687547219a8ec20`, image
  `smarthr-app:review-fd9cdae-20261114t115740z`. Follow-up documentation does not
  modify the tested runtime. Strict scoring/parsing code is identical to the
  checkpoint used for the real four-role acceptance above.
- All 1,182 backend tests passed independently under both production-matched
  provider configurations. All 26 frontend suites and both isolated browser
  workflows passed; final screenshots were inspected at desktop/mobile widths.
- The backup restored with all 23 table fingerprints matching. Restart preserved
  business records and unrelated containers. All 29 reviewed original CV hashes
  matched afterward. Temporary release QA containers were removed.
- HTTPS login/health/deep-health returned 200. Anonymous protected APIs and a
  CSRF-valid unauthenticated preview POST returned 401. Runtime/static hashes
  matched. Health checks and all final local probes added no paid calls.
- Final live local-preview results were 10 profiles in the original HR scope,
  zero for the future date and missing folder, and five for an explicitly changed
  UI tag. Independent SQL verified each selected set and original date bounds;
  no tag expansion or count padding occurred. All results were labeled indexed,
  unverified suggestions with unmet/unconfirmed requirements, not scorecards.
- The cold standalone diagnostic took 8.51 seconds including loading a separate
  local embedding model; its warm alternate-tag probe took 0.02 seconds. These
  tiny-cohort backend measurements are not normal UI latency benchmarks.
- Final ten-case stored-vector probes passed again without scope leaks or paid
  calls; median retrieval times were approximately 2-30 ms, excluding inference.

## Limitations

- Live browser control stopped because it could not safely verify the current
  browser URL. No further live browser automation was attempted this turn.
  Isolated browser tests are not represented as live visual acceptance.
- Indexed details can be incomplete. Similar profiles display that warning,
  the unmet/unconfirmed criteria and a link to the original CV for review.
- A request for ten returns ten only when ten verified eligible profiles are
  available; otherwise the existing truthful shortfall is retained.
- Bounded cohort checks are not a population-wide accuracy benchmark.
- GitHub-hosted CI was previously blocked by account billing restrictions;
  production-runtime gates must be reported separately from hosted CI.

Private candidate, mailbox, usage and integrity receipts are not published.
