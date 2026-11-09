# Folder, Tag And Date End-To-End Verification

Release: `v2026.11.09.4`, 9 November 2026.

## Issue Found And Fixed

The connected Outlook import failed against the real mailbox with HTTP 400,
`InefficientFilter`. Both Microsoft message-list implementations combined sorting
by received date with a filter containing only `hasAttachments`.

`services/graph_mail.py` now supplies a shared attachment-message filter which
places the received-date property first, using the earliest representable date
rather than a recent cutoff. The older credential-based branch in
`main.scrape_outlook_attachments` uses the same filter. Newest-first ordering,
attachment limits, selected destination, mailbox identity checks and permissions
are unchanged. A regression test emulates the previously rejected query shape.

This follows [Microsoft's filter and order-by requirements](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0#using-filter-and-orderby-in-the-same-query).

## Ingestion-To-Search Tests

`tests/test_folder_tag_e2e.py` exercises the actual HTTP handlers with isolated
PostgreSQL schemas, temporary storage, valid fictional DOCX files, real document
extraction, local evidence-based tagging and index metadata writes. External
Graph HTTP responses, query embeddings and final AI assessments are deterministic
fixtures. These tests are not paid-provider accuracy evaluations.

| Scenario | Verified Result |
| --- | --- |
| Multiple CV bulk upload into a named folder | Files, tracking rows, vectors, tags and upload dates are stored for the chosen destination. |
| Both email-import entry points | Actual Graph response parsing, attachment normalization, folder placement and received-date recording run through to indexed records. |
| Attachment selection and import failure | Inline/unsupported files are skipped; Graph denial is an error, not empty-success, and adds no files. |
| Folder boundaries | Selected folders include their descendants, not similarly named siblings; another selected folder is included only when requested. |
| Filename and tenant boundaries | Same names in different folders resolve to the correct original; another tenant is excluded even in a shared bucket/folder. |
| Tags and combined scope | Any selected tag may match, but folder, tag and date restrictions all apply together. An empty intersection stays empty. |
| Received-date boundary | April 30 at 23:59:59 UTC is included; May 1 at midnight and missing received dates are excluded from April. |
| Date basis | Uploaded and Email received use their respective metadata, not interchangeable guessed timestamps. |
| Retrieval modes and cache | Advanced/basic retrieval and repeated broad-to-narrow requests preserve scope. Missing folders return zero; explicit empty selections are rejected. |
| Durable search worker | Queued request, optimized query, raw-query fallback, actual original-file extraction, assessment input and persisted results retain the selected cohort. |
| Requested count versus eligible cohort | Asking for ten when only one CV qualifies returns that one, never nine out-of-scope replacements. |

`tests/frontend_polling.cjs` also mounts the real folder/tag/date controls and
submits through `performRealSearch`. It verifies exact POST payloads, distinct
pending requests after changing any scope, preservation of earlier result scope,
empty-selection blocking and explicit reset to All folders. Existing upload UI
tests cover existing/new destinations and the exact bulk/email payloads.

## Live Deployment Verification

- Deployed image: `smarthr-app:clean-20261109t174922z`.
- Immutable image ID:
  `sha256:48a8965d071eb44586ba8331faaee3f0c6e5da43258d1e39bc48b71b48025fa8`.
- The real connected Microsoft mailbox returned three supported attachments from
  three messages after deployment. All three passed document-payload validation
  and had received timestamps. Bytes remained in memory; no production import,
  outgoing message, calendar operation or new permission grant was performed.
- 132 deployed search-handler checks across three permitted identities, two
  retrieval modes and two queries validated 1,575 returned rows against independent
  metadata eligibility checks: zero out-of-scope rows. Cases covered multiple
  folders/tags, both date bases, combined restrictions, empty cohorts and cache
  reuse. Additional invalid-range/empty-selection checks returned HTTP 422.
- These API checks use injected test identities with real deployed handlers,
  offline cached query embeddings and a read-only production database connection;
  they are not new browser sign-ins or an external network/load benchmark.
- Workspace inventories, all ten tag-category counts, upload totals and library
  handlers matched database counts. Public assets matched source hashes and
  sampled private routes rejected anonymous requests.
- Business-table fingerprints remained unchanged; deployment preserved OAuth,
  candidate decisions, notes, interviews, outreach and templates. All 20 unrelated
  containers were untouched. SmartHR is healthy with zero restarts.
- Public health and deep-health returned HTTP 200; even an explicit LLM health
  request skipped inference. Paid AI usage remained at the same 47 logged calls.

## Regression And Release Gates

- All 942 backend tests passed without skips against an isolated PostgreSQL
  restore, using the non-secret example configuration. The private restore was
  removed afterward. A second run against a fresh private database with only
  the vector extension enabled also passed all 942 tests; that database was
  removed as well.
- All 19 frontend suites passed, including the new controls-to-request checks.
- Offline comparison of 105 fixtures against 3,913 tenant vectors found identical
  tokenization and embeddings, with zero top-ten ranking differences.
- Candidate runtime smoke checks and dependency consistency passed. The advisory
  scan covered all 102 installed packages, with zero skipped packages or known
  findings. This is not an OS-image or vulnerability-free certification.
- Converter proof was reused only after checking unchanged converter source and
  its immutable image identity. UI, prompts, scoring, models and provider settings
  are unchanged by this release. A private database/source rollback backup was
  retained before the SmartHR-only restart; no schema migration was needed.
- GitHub CI now enables `vector` in a pgvector-capable isolated database and runs
  every `frontend_*.cjs` suite. Publishing the workflow does not establish a hosted
  green run; the previously observed account billing limitation is separate.

## Remaining Boundaries

- Historical records have zero known email-received timestamps. Received-date
  filters correctly exclude them; upload dates are not substituted. New imports
  preserve the real provider timestamp.
- Existing missing-vector records and missing originals remain separate data
  quality issues. This release does not fabricate those records or expand search
  outside the selected scope to compensate.
- Live attachment reading and isolated full ingestion were tested separately to
  avoid adding customer data during verification. An actual production import was
  intentionally not performed. Live paid-AI accuracy, large-load capacity,
  cross-browser visual certification and offsite restore are not newly certified.

Private operational receipts, mailbox material, filenames and customer CVs are
excluded from this report and from Git.
