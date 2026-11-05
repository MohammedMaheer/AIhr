# Search precision and indexing review

## Scope

This follow-up checks strict criteria eligibility, extraction, cached-result filtering
and the unindexed-document backlog. It does not change AI prompts, provider, UI,
embedding model, ranking weights, candidate decisions or historical reports.

## Corrected Issues

| Problem | Correction |
| --- | --- |
| `Dubai, UAE` admitted other UAE cities | A country qualifier no longer becomes an alternate location. Explicit `Dubai or Abu Dhabi` still works. |
| An unrelated client location or `not Abu Dhabi` expanded a query | Alternatives must belong to the primary location's explicit OR/slash list. Client/negative clauses are not added as choices. |
| Shared country words and partial cities counted as matches | Complete aliases are canonicalized; country-to-city inference is one-way and does not override an explicitly different country. |
| A relocation-only parenthetical became location evidence again | Empty primary-location evidence stays empty after removing the qualifier. |
| Java matched JavaScript; SQL matched NoSQL | Shared bounded token rules now apply in both PostgreSQL shortlisting and final filtering. Legitimate versions, ASP.NET and explicitly recognized SQL dialects remain valid. C and R requirements are retained. |
| Native-language labels could be rejected because `na` appeared inside `native` | Unknown-language markers use complete words. Inferred/assumed/not-provided labels cannot satisfy final criteria; N/A is preserved during splitting. |
| Nine months became nine years; zero years could be replaced by fallback data | Month-only values are converted to years and explicit zero experience survives profile merging. |
| Malformed nested candidate fields could raise during filtering | Invalid structures become unknown evidence and are excluded by strict filtering, without aborting the batch. |
| Table-only DOCX CVs produced empty indexing text | Local indexing now includes table rows, with the existing 80,000-character output bound. Unreadable files do not become invented text. |

Strict search still returns fewer than requested when enough verified matches are
not available; it never pads results with known mismatches. The candidate count
control and all existing UI workflows are unchanged.

## Verification

- 134 focused parser/profile/extraction tests passed locally.
- Full supported-runtime PostgreSQL restore suite: 730 passed, zero skipped.
- Network-isolated auto and DeepSeek modes: 691 passed, 39 database-dependent skips each; those integration cases ran in the full restore suite.
- All 11 frontend DOM suites passed. No new visual design or UI asset change was made in this batch.
- 105 embedding fixtures: identical tokenization and embeddings. Similarity rankings and scores against 3,903 tenant vectors were unchanged. Corrected eligibility filtering is intentionally different for the identified false matches.
- Runtime: 102 packages audited, zero known advisories, zero skipped packages; CPU-only image and dependency checks passed.
- Existing scorecard reuse was reviewed: new searches reapply current strict criteria after cached assessment retrieval and before persistence. There was no blanket cache invalidation or unnecessary forced AI reassessment.
- These fixtures verify specified rules, not overall real-CV model accuracy or high-traffic capacity. No paid AI call, email or calendar notification was initiated by this review.

## Index Backlog

Read-only production inventory found 97 rows without vectors, all marked
`no_text_extracted`. All 97 have nonempty local source files:

| Format | Rows |
| --- | ---: |
| PDF | 70 |
| DOCX | 14 |
| Legacy DOC | 13 |

A bounded sample inspected three PDFs and three DOCX files locally without returning
CV text or invoking OCR/AI services. The PDFs had no extracted text on the first two
pages. Two sampled DOCX files had recoverable table text but no paragraph text; the
third could not be read by the installed parser. These sample findings must not be
extrapolated into a claim that every PDF needs OCR or every DOCX is recoverable.

The 4,191 upload rows represent 4,000 distinct bucket-qualified upload identities
plus 11 older non-bucket references. One distinct upload reference has neither an
accessible source within the storage boundary nor an embedding identity. Reconcile it against backups or
its original source; do not silently delete history, assign a different CV or guess
tenant ownership.

The initial inventory was read-only. Following explicit approval, 14 missing-vector
DOCX records were prepared in a network-disabled, CPU/memory-bounded worker using
the same cached local embedding model. Ten yielded usable text and were recovered;
four remained unreadable. No OCR service or AI API was used.

The update was restricted to unchanged, tenant-owned rows whose vectors were still
NULL. Original source hashes and all other index rows were checked. Ten recovery
audit records committed with the ten updates; a private pre-update row snapshot is
retained on the VPS. Repeating the completion check did not reapply the updates.
No original CV file, previous non-NULL vector, company assignment, candidate
decision, search history, email or interview record was changed by recovery.

Post-recovery missing vectors: **87** (70 PDFs, 4 DOCX and 13 legacy DOC files).
PDF/legacy Word conversion and the unresolved upload reference remain untouched.

## Release And Limits

Deployed release: `smarthr-app:clean-20261105t135109z`.
Image: `sha256:4c7f94cb97d78db0fd4c2af2aed4b44033a1681fe6cc963c99c87c7a190fa6d6`.
Live source hashes matched; 12 synthetic eligibility checks passed in the active
container without running a paid search. Read-only PostgreSQL shortlist plans for
Java, SQL and .NET took approximately 13-21 ms. These timings exclude embeddings,
AI assessment, networking and rendering and are not end-to-end search benchmarks.
Public assets and all 28 protected read routes were checked. The application was
healthy with zero restarts, and health checks had zero AI-call delta. Deployment
preserved all 20 unrelated containers. Private deployment/recovery receipts are not
published with source.

Outstanding work includes OCR/legacy Word handling, remaining DOCX readability,
source reconciliation, labeled real-CV accuracy/recall evaluation, broader mixed
language/skill Boolean grammar, high-traffic tests and off-site restore verification.
No claim of perfect parsing, a universal accuracy percentage or measured monthly
cost savings is made.
