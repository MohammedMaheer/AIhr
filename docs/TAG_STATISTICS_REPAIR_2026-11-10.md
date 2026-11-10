# Search Statistics And Local Tag Repair

Release: `v2026.11.10.3`, 2026-11-10.
Production: https://effortsairecruiter.tech/

## Scope

Two narrowly scoped corrections, with no UI, search scoring, prompts, model,
authentication, dependency or database schema changes. No paid AI calls were
made. No CVs were deleted or overwritten.

## Corrections

### Search Statistics

`DatabaseManager.get_user_search_stats` in `database.py` previously joined each
search history to its candidate results before counting. A search returning
several candidates therefore counted several times and biased the average
results per search.

The query now scopes history once and computes per-search statistics from those
rows. Candidate match-score averages are calculated separately, retaining their
existing candidate weighting. The response fields, optional company scope,
user ownership, inclusive 7/30-day cutoffs and null-score behavior are preserved.
Independent SQL references matched all five returned statistics fields for all
three active accounts. Their corrected owned-search totals are 78, 1 and 1.
The primary activity totals and candidate status cards were already correct and
remain unchanged.

### Missing Tags

`tags_from_text` in `services/resume_filters.py` previously missed existing
multiword category evidence when document extraction placed line breaks, tabs,
nonbreaking spaces or repeated spaces between the words. It now normalizes
whitespace before applying the same ten category rules, in the same order.

An exact, reviewed change set was rehearsed in a restored database before live
application. The production transaction updated only `search_tags` on 48
records and wrote 48 audit entries. It restored 49 category memberships; 24 CVs
received their first supported category. Tagged records increased from 5,369
to 5,393. All 7,842 records now agree with the local extractor, with zero
remaining formatting-related misses and no existing tag removed.

The update was guarded by row, extracted-text and original-file hashes,
an advisory transaction lock, exact old-value checks and a pre-apply backup.
Post-update checks confirmed:

- All 7,832 non-null vectors, CV text, original files and index identities stayed
  unchanged; the ten previously held non-vector records were not reprocessed.
- All dates, storage locations, company ownership and non-target rows stayed
  unchanged. No global metadata/date refresh was performed.
- Uploads, search histories/results, candidate decisions, connected OAuth data,
  interviews, notes, email/template records and recovery provenance were preserved.
- The recorded paid-LLM counter remained at 47 before and after the work.

## Verification

| Check | Result |
| --- | --- |
| Full backend suite, isolated fresh PostgreSQL with pgvector | 1,026 passed, zero skipped |
| Frontend regression suites | All 19 passed |
| Statistics regressions | Uneven candidate counts, repeated result totals, empty history/results, user/company scope and exact date boundaries passed |
| Tag regressions | All ten categories across five whitespace forms, negative examples and real SQL retrieval in both modes passed |
| Database restore and tag-only repair rehearsal | Passed; private temporary databases removed |
| Deployed folder/tag/date search matrix | 132 cases, 1,575 returned rows, zero scope violations |
| Newly restored tag memberships | All 49 verified in basic and advanced retrieval: 98 API checks |
| Membership dates | All 49 checked with real received/uploaded day bounds and their actual folder/company scope |
| Dashboard and library/folder/tag inventory parity | Passed for all three active accounts |
| Offline embedding compatibility | 105 fixtures, identical tokenization, zero embedding/score delta, no top-ten ranking mismatches against 7,831 tenant vectors |
| UI preservation | All 434 live static/template file checksums unchanged |
| Production health | Public health HTTP 200, deep health healthy, paid AI probe skipped, app restart count zero at verification |
| Other applications | All 20 unrelated running containers retained their IDs and start times |

Deployed-handler checks used the real production database with read-only
connections and injected test identities inside a separate process. They did
not bypass production authentication or write search history. Repaired-record
checks reused each existing stored vector as the query to test filter inclusion
without model inference. The broader matrix used real cached local embeddings
in offline mode. Neither is a paid-AI semantic accuracy evaluation or a public
browser/login test.

## Deployment And Recovery

- Live image: `smarthr-app:clean-20261110t024406z`.
- Image ID: `sha256:953b147cda3c08693dd5f1dba8b3f17948d90e3a7496e83e1962e5e81327834c`.
- Retained private database dumps, prior source/image configuration, exact
  old/new tag values and transactional audit entries for recovery. Customer
  records, credentials and private operational receipts are not published.
- Deployed only SmartHR's tested application update. No schema migration,
  paid model switch or production PostgreSQL setting change was required.
- Restore rehearsal initially hit the test container's shared-memory limit
  while rebuilding an index. Rerunning test restores with bounded, serial
  maintenance succeeded; this did not alter the production database settings.

## Remaining Limits

The rules intentionally cover ten categories, not every profession. An untagged
CV is not necessarily damaged or irrelevant, and no categories were invented
to raise coverage. Existing unavailable historical email dates remain unknown.
Previously held damaged/supporting files remain retained for review.

Six existing test warnings concern framework deprecations and pytest's cache on
a read-only source mount; no tests failed. Dependencies are unchanged and the
102-package runtime inventory matches the retained advisory report with zero
known findings at that scan. This is not a new OS-level vulnerability audit.

No live mailbox import, outgoing email/calendar action, browser certification,
load test or paid-AI accuracy benchmark was performed in this repair release.
No claim of universal error-free behavior or measured end-user latency
improvement is made.
