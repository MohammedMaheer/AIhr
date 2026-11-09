# Folder And Import Visual Review

Release: `v2026.11.10.1`, 10 November 2026 (Asia/Kolkata).

## UI Changes

- Correct the selected File Upload / Email Scraping tab colors, including hover
  states. The selected email tab previously combined white text with a gray hover
  background.
- Hide the unrelated file queue in email mode and restore it, with its contents
  intact, when switching back to File Upload.
- Remove the technical batch-strategy panel and simplify completion messages and
  queue summaries. File size limits, adaptive batch sizing, retries, upload
  processing and indexing behavior are unchanged.
- Preserve provider, address and scan limit when an import finds no attachments
  or saves none, while clearing its submitted password. Successful imports retain
  the existing reset behavior and destination-folder refresh.
- Prevent global notifications from covering workspace-dialog controls. New
  notifications raised inside a workspace dialog appear in its layout rather
  than floating over its fields, close button or footer. Nested administration
  forms, safe text, dismissal and persistent error behavior are covered by tests.
- Keep the original recruiter logo, search scope semantics, prompts, models,
  scoring, Microsoft permissions and calendar/email delivery behavior unchanged.

## Visual And Flow Checks

The controlled browser matrix used real application HTML/CSS/JavaScript with an
explicitly opted-in, local-only fictional ingestion server. It never forwards
requests to production APIs, creates customer CVs or calls an AI provider.
The helper's default write-disabled behavior remains unchanged.

| Viewport | Checked Workflows |
| --- | --- |
| 320 x 740 | Existing/new upload destinations, invalid paths, two-file bulk completion, new destination promotion, email modes and connection state, empty/error responses, folder/tag/date selections, filter dialog, validation and unobstructed close controls. |
| 390 x 844 | Same workflows, including inline dialog errors and phone scrolling. |
| 768 x 1000 | Same workflows at tablet width. |
| 1440 x 1000 | Same workflows at desktop width. |

All four cases passed without page-level JavaScript errors or horizontal page
overflow. Screenshots were inspected for tab contrast, layout, wrapping, labels,
notifications and dialogs. In particular, a persistent-toast obstruction of the
filter close button was reproduced and corrected rather than bypassed with a
forced click. Invalid date ranges keep the dialog open; earlier scope selections
remain checked when reopening it after a search.

These visual import responses are fixtures, not real mailbox-import acceptance.
Real storage/extraction/PostgreSQL/worker coverage is in
`tests/test_folder_tag_e2e.py`; the earlier live Outlook query fix is documented in
`docs/FOLDER_TAG_E2E_2026-11-09.md`. Browser viewport overrides are temporary, and
no real interview, outbound message or production upload is needed for visual QA.

## Controlled Cleanup

The user requested smoke/invalid resume cleanup and review of genuine unreadable
CVs before deletion. Inspection distinguished disposable fixtures from genuine
candidate data; a QA role or the phrase "smoke testing" is not a test CV.

- Removed eight stale, explicitly named smoke-upload records whose original
  files were already absent and which had no indexed or historical candidates.
- Quarantined one verified 17-byte placeholder named `existing.pdf`, containing
  only a PDF marker and the word `existing`, with no PDF objects or CV content.
  Removed its two duplicate upload records and its non-vector index record.
- Retained the database snapshot, exact deleted rows and placeholder bytes in a
  private permission-restricted backup, with 11 transactionally recorded audit
  entries. Historical search results were preserved, including any historical
  reference to the invalid placeholder; those references were not purged.
- Verified unchanged fingerprints for all other upload/index rows, candidate
  actions, search history/results, interviews, connected credentials, notes and
  outreach records. No paid AI call was made.
- The active totals changed from 4,191 to 4,181 upload rows and from 4,001 to
  4,000 index records. These are record counts, not unique-person counts.
- All 4,000 source files referenced by the remaining index records were present. A bounded storage walk
  found no remaining files matching the confirmed numeric smoke-fixture pattern.
  The live dashboard displayed the corrected 4,181 uploads.

### Genuine CVs Retained For Review

| Classification | Records | Treatment |
| --- | ---: | --- |
| Scanned/textless PDFs | 53 | Retained; lack of selectable text does not make a CV invalid. |
| Legacy Word documents | 13 | Retained for conversion/recovery. |
| Text recoverable by the bounded review parser | 13 | Retained for a separate indexing repair decision. |
| Word files without extracted body/table text | 3 | Retained; image/text-box content needs further review. |
| Genuine-looking files with PDF/Word parser failures | 4 | Retained for repair or explicit removal approval, not silently deleted. |

The 86 retained records are not all corrupt or unsuitable candidates. A private
file-level CSV was produced for the user; filenames, CV content, source paths,
backup material and raw operational receipts are excluded from Git.

## Release Results

- All 942 backend tests passed without skips against a fresh isolated PostgreSQL
  database with the vector extension and example configuration; the database was
  removed. All 19 frontend suites and changed-JavaScript syntax checks passed.
- Offline comparison retained identical tokenization, embeddings and top-ten
  rankings for 105 fixtures against 3,913 tenant vectors. Runtime smoke/dependency
  consistency checks passed. All 102 installed packages matched the advisory scan
  without known findings or skipped packages; this is not an OS-image audit.
- Deployed `smarthr-app:clean-20261109t195514z`, immutable image
  `sha256:d21bc65a113fc070777ff859a96e18eb1f9b8e645de7b360cb999d9029635544`,
  with a private rollback/database backup. No migration or provider-key change
  was needed. Existing business/OAuth/outreach fingerprints were preserved by
  deployment, and all 20 unrelated containers remained untouched.
- Fresh public asset hashes matched source. Private routes rejected anonymous
  access. The app was healthy with zero restarts and no sampled post-deploy
  tracebacks or HTTP 500 responses.
- Live authenticated Chrome checks at desktop and 390-pixel phone width confirmed
  existing/new destinations, invalid-path feedback, connected Microsoft prefill,
  selected-tab contrast, hidden email-mode file queue and multi-folder/tag/date
  layout. Test selections and viewport overrides were reset afterward.
- Live library searches showed no `smoke_` or `existing.pdf` records, and clearing
  the search restored the 4,181-row library. No live import or paid search was
  submitted through the browser.
- A bounded read of the real Microsoft mailbox validated three supported
  attachments and received dates, without importing or persisting them. The
  deployed search API passed 132 read-only scope checks, validating 1,575 returned
  rows with zero out-of-scope results. These handler checks inject test identities;
  actual authenticated UI controls were checked separately in Chrome.
- Workspace folder/tag/upload counts matched the real database for three
  permitted identities. There were 4,000 known upload-date records and no known
  historical email-received dates. Paid AI call count remained 47 throughout.

## Remaining Limits

Cross-browser/device hardware certification, live production imports and a new
paid-AI accuracy/load assessment are not claimed by the fixture screenshots.
Unknown historical received dates and the unverified offsite restore remain
separate limitations. Two genuine upload rows without an index entry and one
legacy tracking path without a resolvable original were also retained, not
misclassified as disposable test data. Backend matching and token usage policy
are unchanged. Hosted CI success is not claimed by the local/VPS test results.
