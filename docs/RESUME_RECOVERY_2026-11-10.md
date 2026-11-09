# Offline Resume Recovery - 10 November 2026

## Original 86-Record Review

| Outcome | Records | Treatment |
| --- | ---: | --- |
| Recovered CVs | 76 | Indexed locally; original bytes preserved. |
| Structurally damaged PDFs | 2 | Retained for user review and replacement, not deleted. |
| Low-confidence scanned CV | 1 | Retained; a clearer source or manual transcription is needed. |
| Supporting documents | 7 | Retained without indexing them as separate candidate CVs. |

Recovery used PDFium text extraction, bounded Word XML extraction, isolated
LibreOffice conversion, English/Arabic Tesseract OCR and one visually reviewed
MuPDF reconstruction. An otherwise readable CV had a third page containing only
an empty design background; all three pages were visually reviewed before its
native text was accepted. The separate low-resolution CV failed additional local
OCR attempts and was not forced through the acceptance gate.

The existing 384-dimensional MiniLM model generated the vectors from its cached
local weights. Processing containers had no network, database credentials or API
keys. Originals and model weights were mounted read-only. No paid AI calls were
made, and no source files or candidate records were deleted.

The original corpus retained 4,000 index records and 4,181 upload records. Its
searchable count increased from 3,914 to 3,990. These are document/record counts,
not a deduplicated count of people. Exact file-level outcomes and review copies
remain private and are excluded from Git.

## Full-Text Search Handoff

- `services/recovered_text.py` reads accepted local text only for the authorized
  company, storage bucket, exact folder/filename and SHA-256 of the original
  downloaded bytes. Ambiguous identities and changed source/text hashes fail
  closed. Unregistered files retain their normal extraction behavior.
- The additive `20261110_resume_recovery.sql` migration stores provenance and
  text hashes, without changing existing identity, ownership or date columns.
- Both existing file-content helpers in `main.py` use the trusted full-text
  lookup. This prevents a recovered vector from reaching search assessment with
  empty or partial native extraction.
- Updates were rehearsed in isolated database restores, then applied with exact
  row/source-hash guards and transactionally recorded audit entries. Existing
  non-target records and original files were preserved.

## Verification

- All 959 backend tests passed without skips against isolated PostgreSQL with
  pgvector. This includes real database and full-download recovery regressions.
- All 19 frontend test files passed. No UI, prompts, paid model, scoring rules or
  candidate matching policy changed in this release.
- All 86 original file hashes were rechecked. The 76 repaired CVs passed 304
  deployed-helper retrieval/isolation checks, including complete text, exact
  original bytes, changed-file rejection and wrong-company rejection. Median
  full-file retrieval was approximately 2.3 ms in the maintenance process; this
  is not an end-user network or paid-scorecard latency measurement.
- The deployed retrieval handlers passed 132 read-only scope checks with zero
  out-of-scope results. Test identities were injected; this is not a new browser
  sign-in or paid candidate-assessment test.
- Offline comparison of 105 fixtures retained identical tokenization, vectors
  and top-ten rankings against the existing 3,913 tenant vectors.
- The clean runtime passed import/dependency checks. Its 102 Python packages
  matched the previously retained zero-advisory scan without skipped packages;
  this does not constitute an OS-package security audit.
- The deployed image is `smarthr-app:clean-20261109t202124z`, immutable ID
  `sha256:74a451e9cff677dcd48597be5ac2fe8254160c6db6a2baa9c25af4db57973398`.
  Deployment preserved business/OAuth/outreach records and did not restart or
  replace any of the 20 unrelated containers. Health checks skipped paid AI.

## Limits

OCR confidence is a conservative screening measure, not proof of character-level
perfection. Supporting files, low-confidence text and damaged originals require
human review. No paid accuracy benchmark, live email send, new calendar event,
offsite restore or hosted CI success is claimed by these checks.

## Separate 2026 Mailbox Import

The user separately authorized received 2026 resume attachments from the connected
HR Microsoft mailbox. An annual inventory followed Graph pagination to completion
and excluded sent, draft, outbox, junk and deleted-folder trees. It found 4,981
supported PDF/Word attachments in 4,738 received messages. All attachment
downloads completed; exact file hashes skipped 981 duplicates, leaving 4,000
distinct documents for local processing. Receipt dates, originals and private
per-file journals are retained.

| Final Annual Import Outcome | Documents |
| --- | ---: |
| New CVs published in `Mailbox 2026` | 3,842 |
| Exact file duplicates skipped | 981 |
| Additional identical-text duplicates skipped | 9 |
| Uncertain/supporting documents retained privately for review | 149 |
| Total supported attachments processed | 4,981 |

All 4,000 distinct new documents completed the offline pass. The 149 held records
include 25 supporting documents, 46 low-confidence OCR cases, 68 document-type
questions, four parser/page-limit exceptions, two insufficient-text cases and
four text-quality cases. They were not published or deleted. Independent checks
showed that the parser exceptions include long documents; a parser exception is
not automatically classified as a damaged CV.

The full 3,842-record transaction passed an isolated restore rehearsal before
publication. Existing rows and connected accounts were preserved. Source files
were copied without changing their bytes, with company ownership, actual email
received dates, derived tags, matching local vectors and per-record audit entries.
The resulting corpus has 7,842 index records, 7,832 searchable vectors and 8,023
upload records. The ten older held originals remain unchanged.

Every published CV passed deployed full-text retrieval and source-hash checks,
including 11,526 hash/company isolation checks, ten original download-wrapper
samples, eight vector-scope checks and three received-date inventory checks.
The 132-check deployed API scope matrix passed again with zero out-of-scope rows.
These checks used the real local embedding model and database but blocked paid
candidate assessments. The paid-call counter stayed at 47; this work added zero
paid calls. A closing mailbox read found no newer supported attachments between
the initial snapshot and 10 November 2026, 03:28 IST. This was a one-time import,
not a new recurring mailbox-sync service.

Annual file-level outcomes remain in a private local HTML/CSV review package.
No mailbox bodies, customer filenames, CV text, raw receipts or backup material
are included in this release. Graph paging follows the documented
[message-list behavior](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0).
