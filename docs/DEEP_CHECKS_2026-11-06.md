# SmartHR Deep Checks - 6 November 2026

## Scope

This release checks explicit search eligibility across parsing, SQL shortlisting,
and final filtering; upload indexing outcomes; safe upload feedback; and cache
isolation. It does not certify every production workflow, model accuracy on all
CVs, or million-user capacity. No model, prompt budget, original logo, existing
CV, OAuth credential, or calendar event is changed by these fixes.

## Reproduced Findings And Fixes

| Severity | Finding | Fix and source |
| --- | --- | --- |
| High | `English or Arabic` and `Python or Java` required both alternatives. | `services/requirements_logic.py`, `search_criteria.py`, `vps_local/discovery_shim.py`: shared bounded AND/OR tree, with parentheses and AND precedence, evaluated in both SQL and final filtering. |
| High | `Python and .NET` could drop .NET at the period; `proficient in English` also became a technical skill. | `search_criteria.py`: retain internal technology-name periods and distinguish spoken languages from skills. |
| High | Shortlisting and final filtering interpreted the same experience string differently. | `vps_local/profile_extractor.py`: reuse `search_criteria._parse_years_string`; correctly convert months and compound durations, retain conservative lower bounds for ranges, reject dates/non-finite values. |
| High | Local index failures, missing files, and unreadable files could return success-like operations and `vector_indexed: true`. | `vps_local/discovery_shim.py`, `main.upload_to_vector_datastore`: explicit indexing result, sanitized error code, and fail-closed local success check. Saved uploads remain saved even when indexing fails. |
| High | Search response cache keys relied on datastore identity without binding the local tenant or user. Shared-resource configurations could reuse another account's response. | `main.search_vector`: include bucket, datastore, validated local scope, user ID and company ID. |
| Medium | Upload feedback treated saved-but-unsearchable CVs as ready; filenames/provider errors were inserted into HTML without escaping. | `static/js/main.js`: escaped values, separate attention state and warnings for manual uploads and email imports. |
| Medium | Repeated clicks could start concurrent upload batches; queue changes could race active uploads. | `initializeUploadPage`: synchronous submission guard and disabled queue mutation until completion. |
| Low | The current-page upload-attempt counter said "Uploaded Today" and the file picker advertised a different batch size from the actual uploader. | `static/js/main.js`: label the counter "Files Processed This Session" and consistently show the existing 32MB batch grouping. |

The Boolean parser uses Python's standard AST parser over generated identifiers,
never `eval`. User terms remain bound SQL parameters. Size, nesting, term-count,
and node-count limits bound parsing work. Unsupported syntax falls back to the
existing conservative listed-term behavior; this is not a general natural-language
logic solver. Existing plain-AND result penalties are retained.

Experience ranges still represent a conservative scalar lower bound, not a full
uncertainty interval. Historical numeric metadata is not silently rewritten; new
extractions and normal analysis-profile updates use the unified conversion.

## Regression Coverage

- `tests/test_requirement_alternatives.py`: positive/negative OR and AND cases,
  nested clauses, precedence, technology periods, spoken languages, experience
  parity, malformed expressions, parser resource bounds and SQL parameterization.
- `tests/test_tenant_search.py`: real PostgreSQL/final-filter agreement using the
  real ingestion normalizer; cache isolation even with shared resource names.
- `tests/test_local_document_extraction.py`, `tests/test_upload_index_status.py`:
  missing source, empty/short text, successful indexing, exceptions, explicit local
  status, and retained cloud acceptance semantics.
- `tests/frontend_product.cjs`: actual DOM upload workflow, filename/error escaping,
  truthful indexing warnings, repeated-click guard and control recovery.

## Verification And Deployment

| Check | Observed result |
| --- | --- |
| Python 3.11, isolated restored PostgreSQL | 797 passed, no skips; synthetic provider calls only. |
| Network-isolated provider configurations | 754 passed in each of `auto` and `deepseek`; the 43 database-dependent skips were then exercised in the full restored-database run above. |
| Frontend | All 11 DOM suites passed, including the upload regressions. |
| Embedding compatibility | 105 fixtures; identical tokens/vectors, zero top-10 differences across 3,913 tenant vectors. |
| Dependency audit | 102 installed packages, zero known vulnerabilities, no skipped packages; `pip check` passed. |
| Live matching | Six synthetic Boolean SQL/final-filter checks, five experience conversions and 12 existing location/skill fixtures passed without paid AI. |
| Live query-plan samples | Java 12.138ms, SQL 17.058ms, .NET 13.922ms. These are individual database filter timings, not end-to-end search latency or a load test. |
| Authorization | All 28 discovered protected GET routes rejected anonymous access; candidate-state cross-tenant denial passed. |
| Public assets | All nine checked JS/CSS assets matched the tested source hashes. |
| Browser | Upload page checked at 1280x720 and 390x844; no horizontal page overflow or broken images; corrected copy fits, original logo retained, no browser console errors observed. Not an exhaustive visual certification of every view. |
| Microsoft | Expired access token refreshed through the normal application path; profile, mailbox metadata and default calendar returned HTTP 200; Teams available, calendar editable, refreshed credentials encrypted. No email send, attachment download, event write or consent change. |
| Health / operations | HTTP 200, zero restarts, zero paid-AI health-call delta; nginx and TLS valid. |

Deployed to `https://effortsairecruiter.tech/` as
`smarthr-app:clean-20261105t192229z` (UTC release timestamp). A private pre-release
rollback backup and database dump were retained. Only SmartHR was recreated;
the other 20 running containers retained their IDs and start times.

Deployment fingerprints preserved CV contents, candidate decisions/notes, saved
outreach, interviews and encrypted OAuth records. The subsequent expected OAuth
refresh updated only the saved Microsoft credentials through the normal encrypted
storage path. Counts remain: 4 users, 1 company, 4,191 upload records, 4,001 index
records, 139 searches, 6,237 saved results and 3 interviews. The LLM usage counter
remained 47 throughout the final live checks.

## Remaining Limits

- 87 existing NULL-vector records require separate investigation: 70 PDFs, 4 DOCX,
  and 13 legacy DOC files. Another older upload reference has no usable local source
  or index. No OCR/reprocessing approval is inferred for these files.
- Earlier approved DOCX recovery added 10 vectors and 10 audit entries without paid
  AI calls. This release must preserve those records and the original files.
- A labeled, representative recruitment benchmark is still required to measure
  AI accuracy, false negatives and recall. Passing deterministic fixtures is not
  an accuracy percentage for real applicants.
- No live email send, mailbox import or calendar mutation was performed this turn.
  Existing calendar test records were retained. Metadata checks and token refresh
  do not prove a new email send or meeting lifecycle succeeds.
- Full production load, failover, and offsite restore exercises remain separate
  work. Health checks must remain free of paid AI calls.
- Hosted GitHub Actions previously could not start because of account billing;
  local and isolated VPS test results must not be described as hosted CI success.
