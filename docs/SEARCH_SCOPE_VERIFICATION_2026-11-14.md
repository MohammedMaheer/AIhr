# Search Scope And Preparation: v2026.11.14.1

## Changes

The query and keyword preparation functions depend on the exact job-description
text, not a recruiter's identity. Their existing cache can now be shared only by
authenticated tenant administrators/users with the same verified positive
integer company ID and company code. The complete original query, operation,
configured provider and model remain part of the cache key. Other operations and
super administrators retain their existing per-user boundaries.

The cache remains process-local, limited to 128 successful entries for 15 minutes,
with independent result copies and single-flight handling of identical work.
Failures, fallbacks and incomplete responses are not retained. A repeated team
search can avoid the two preparation calls, but still performs its own authorized
folder/tag/date retrieval and candidate assessment. No CV text, candidate result,
scorecard or search permission is shared by this change. First-use searches and
searches after expiration/restart still incur the normal preparation work.

Invalid folder/date input was already rejected before an API submission, but the
initial search animation ran first and hid the form. Both composers now validate
before clearing the draft or starting loading/animation. The existing warning
presentation, API-side validation and visual design remain unchanged.

## Verification

- Nineteen preparation-cache tests cover full-query identity, provider/model and
  operation separation, tenant isolation, missing/malformed identities, TTL/LRU,
  independent copies, failure recovery, concurrent work and token accounting.
  Synthetic usage demonstrates two initial preparation calls and none for an
  identical same-company peer request. This is not a production bill estimate.
- All 23 frontend suites pass, including invalid-scope draft preservation in
  both composers, exact folder/tag/date POST payloads, retry cleanup and stale
  result isolation.
- The opt-in `tests/browser_search_scope.py` starts a real loopback HTTP server,
  durable worker and disposable PostgreSQL schema. Fictional bulk Word CVs and
  Graph attachments are parsed, stored and indexed locally. Ten searches across
  1440px and 390px browsers verify received-date boundaries, upload-date metadata,
  multiple folders/tags, descendants versus sibling folders, filter-dialog and
  bottom-composer scope, empty results and tenant exclusion. Empty selections and
  reversed dates must send no task and must retain the visible draft. Across both
  recruiters only the original two preparation calls execute.
- Authenticated live desktop/mobile inspection verifies the existing controls,
  quick-tag synchronization, active chips and invalid-date feedback. At 390px,
  the document width remains 390px. Test selections were cleared afterward; no
  paid search, email, event or candidate-state action was submitted.

## Read-Only Live Retrieval

A separate child process uses production read-only database connections and one
already-stored vector. Model API keys are empty in that child only. It calls the
actual local retrieval implementation and compares returned IDs to an independently
queried eligible cohort before and after scoped searches. No DDL or production
record is changed. Ten cases passed with no out-of-scope IDs:

| Scope | Eligible CVs | Returned |
| --- | ---: | ---: |
| Folder | 3,862 | 25 |
| Folder and tag | 1,277 | 25 |
| Multiple folders and tags | 2,462 | 25 |
| Folder, tag and upload month | 1,277 | 25 |
| Upload month | 3,862 | 25 |
| Single upload day | 20 | 20 |
| Folder, tag and received month | 41 | 25 |
| Received month | 143 | 25 |
| Single received day | 1 | 1 |
| Nonexistent folder | 0 | 0 |

Three repetitions per case took approximately 2-27 ms median retrieval time in
the predeployment probe, with 0.01-6.06 ms filter SQL execution. These are not
browser, embedding, queue or end-to-end AI search latency measurements. Large
cohorts are checked for correct membership and a full requested page; cohorts
of 25 or fewer also require complete set equality. Paid AI usage did not change.

## Boundaries And Release Gates

The browser/backend tests use fixture authentication, mocked Graph responses,
deterministic embeddings and verified synthetic scorecards. Storage, parsing,
HTTP, task lifecycle, filtering and SQL persistence are real. These tests do not
measure live semantic embedding/model accuracy or validate mailbox permissions.
Prompt text, full-CV inputs, original hard criteria, ranking, score thresholds,
requested-count behavior, existing scorecard cache signatures, logo and layout
are unchanged. No accuracy gain or end-to-end latency percentage is claimed.

Publication requires an explicit-path source review and secret scan. Deployment
requires the complete backend suite in both provider modes using production
dependency versions, plus a verified backup restore. Only the SmartHR app is
recreated, with rollback available; unrelated applications and production data
must be preserved. The immutable source/image mapping, actual runtime test counts,
live hash/health checks and final deployment outcome are recorded in GitHub PR #1.
