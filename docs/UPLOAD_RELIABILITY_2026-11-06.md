# Upload Reliability Checks - 6 November 2026

## Scope

This batch hardens manual uploads and imported email attachments. The UI, logo,
AI provider/model, prompts, scoring and result schemas are unchanged. No real
mailbox import, email send, calendar write or CV reprocessing is performed.

## Findings And Fixes

| Severity | Reproduced issue | Change |
| --- | --- | --- |
| High | Database errors during quota checks allowed uploads to continue. | `main._check_resume_upload_limit`: unavailable/malformed quota state returns a sanitized HTTP 503 before writes. |
| High | Separate quota checks could let concurrent clients take the same remaining slot. | `database.resume_upload_lock`, `main._store_resume_upload`: lock the active company row, recheck quota, write the file and insert tracking in one database transaction. Indexing runs after commit. |
| High | A tenant context without its company ID could produce an unowned upload. | Both upload paths reuse the existing `_get_company_id` authorization guard before writing. Super-admin system uploads retain their existing behavior. |
| High | DOCX validation accepted arbitrary ZIP signatures and did not bound expanded data. | `services/document_validation.py`: inspect Word package metadata before parsing, bound entries/expanded sizes/XML parts, and reject encrypted, duplicate or unsafe file parts. Applied to incoming files and both DOCX extraction paths. |
| Medium | Synchronous storage, tracking and local indexing ran on the API event loop. | Shared upload worker offloads blocking work, with two active workers per API process. Cancellation does not release capacity while its thread is still writing. |
| Medium | Unknown-size files were read without a per-file read bound; missing size metadata could raise TypeError. | Read at most `MAX_FILE_SIZE + 1`, tolerate absent size metadata, retain existing 10MB rejection. |
| Medium | Upload/mail handlers changed expected HTTP errors into 500 and returned raw infrastructure exceptions. | Preserve intentional HTTP status codes; use safe error messages and exception-type-only failure logs. |

The quota still counts tracked upload records, as before, not unique file hashes.
Null/zero configured limits retain the legacy 1,000-record default. Company locks
are shared across API processes through PostgreSQL, not an in-memory-only lock.

## DOCX Compatibility

Limits: 2,048 ZIP entries, 64MiB expanded content in total and 16MiB per XML or
relationship part. The guard reads directory metadata only, not CV text. A
harmless empty `/` directory entry is allowed for compatibility with an existing
Word exporter; absolute/traversal file entries remain rejected.

Pre-deployment inventory accepted all 168 existing DOCX packages: 164 indexed,
4 unindexed. No source files or database records were modified. Passing archive
validation does not imply that a scanned/image-only CV contains extractable text.

## Verification

| Check | Result |
| --- | --- |
| Isolated Python 3.11/PostgreSQL regression run | 842 passed, no skips; no real provider requests. Includes two connections competing for the last upload slot, rollback, disabled companies and commit-before-indexing checks. |
| Network-isolated provider configurations | 795 passed and 47 database-dependent skips in each of `auto` and `deepseek`; those skips were covered by the full database run above. |
| Frontend DOM regressions | All 11 suites passed. No frontend source or layout changed in this release; no new browser visual certification is claimed. |
| Embedding compatibility | 105 fixtures and 3,913 tenant vectors: identical tokenizer inputs, vectors and top-10 rankings. |
| Runtime dependencies | 102 packages audited, no known vulnerabilities or skipped packages; `pip check` passed. |
| Existing DOCX package compatibility | All 168 packages accepted; metadata reads only, no text returned or files changed. |
| Live source/guard checks | Deployed source hashes matched; in-memory Word extraction, invalid-DOCX rejection and quota guards passed. No real uploads were performed. |
| Authorization and assets | 28 protected GET routes rejected anonymous requests; cross-tenant state denial passed; nine public JS/CSS hashes matched tested source. |
| Health and AI usage | HTTP 200, zero restarts, no startup tracebacks or observed HTTP 500s; health AI-call delta 0 and stored LLM-call count unchanged at 47. |

Deployed to `https://effortsairecruiter.tech/` as
`smarthr-app:clean-20261106t033712z`. A private pre-release database dump and rollback
copy were retained. Only SmartHR was recreated; the other 20 containers retained
their IDs and start times. Resume fingerprints, business counts, encrypted OAuth
credentials and saved outreach records were preserved. Counts remain 4,191 upload
records, 4,001 index records, 3,914 vectors, 139 searches, 6,237 results and 3 interviews.

These checks establish the scoped behavior above, not a production search latency
percentage or a general AI accuracy score. No paid model calls, real email sends,
mailbox imports or calendar changes were made for this release.

## Remaining Limits

- Storage and PostgreSQL are not a distributed transaction. A crash or database
  commit failure after the physical file write can still leave an orphaned or
  replaced object. This batch does not delete files as compensation.
- Uploads do not yet have durable, content-aware request idempotency. Retrying an
  uncertain network outcome can create another tracking record. Per-process worker
  capacity is not a server-wide distributed queue or a million-user capacity claim.
- `initializeUploadPage` still reduces batch size after all HTTP failures. Permanent
  quota/authentication failures should use status-aware stopping rather than repeated
  smaller-batch attempts; network-uncertain retries also need idempotency first.
- Archive metadata limits reduce oversized-package risk; they are not a complete
  document-parser sandbox or a guarantee against every malicious PDF/XML file.
- The 87 existing NULL-vector records remain untouched. OCR/legacy conversion,
  representative AI accuracy measurement, sustained load tests and verified offsite
  disaster recovery remain separate work.
- Hosted GitHub Actions previously could not start because of account billing;
  isolated VPS test evidence must not be represented as hosted CI success.
