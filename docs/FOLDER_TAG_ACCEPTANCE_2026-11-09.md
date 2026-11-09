# Folder And Tag Feedback Acceptance

Release: `v2026.11.09.3`, 9 November 2026.

## Voice Feedback Review

All three supplied recordings were transcribed locally using cached speech-model
files, with network access disabled for transcription. Audio and raw transcripts
remain private and are excluded from source control. No transcription API or
application AI provider was used. The recordings requested:

| Requirement | Implementation |
| --- | --- |
| One recruiter interface, including permission-scoped administration | Retained the unified workspace, role guards, clickable totals, CV library and browser Back/Forward behavior from the earlier accepted releases. |
| Name bulk-upload folders and reuse an existing folder | Replaced the browser-dependent suggestion list with a labelled native destination dropdown, explicit new-folder button, named-folder field and refresh action. |
| Put email-imported CVs in the chosen folder | Both email entry points now honor an explicit destination exactly. Selecting an existing `email_attachments/...` path no longer nests that prefix again. Requests without a destination retain the default email-import folder. Existing files are not moved. |
| Select multiple folders when searching | Retained explicit multi-folder selection, including subfolders but excluding similarly named siblings, other buckets and other tenants. An empty explicit selection cannot silently search everything. |
| Capture role/skill tags and search only selected areas | Retained automatic local text-evidence tagging. Added searchable tag choices, workspace-scoped searchable counts and visible stored tags in CV previews. Selected tags remain selected when the choices are filtered. |
| Search by date, month/year and recent periods | Retained Uploaded and Email received date bases, explicit date bounds and recent-period presets. Both email import contracts preserve the provider's received timestamp. Unknown historical received dates remain unknown. |

## Behavior Details

- New folders become storage destinations when files are uploaded, not empty
  database records when the new-folder button is pressed. After a successful
  upload, an indexed destination is refreshed into the existing-folder dropdown.
- New-folder drafts survive switching between existing/new choices. Slow defaults,
  folder refreshes and stale responses cannot replace a typed name or a new page.
- Blank names, relative segments, empty path segments, absolute paths and Windows
  separators are rejected by the UI; server-side path sanitization still applies.
- Available destinations are restricted to the upload bucket within the current
  user's permitted workspace. New and existing CVs retain the original ownership
  and search-authorization boundaries.
- Tag counts describe searchable index records in the workspace, not only the
  currently selected folders and not unique people. A CV may have several tags,
  so those counts are not additive. Counts do not include missing-vector records.
- Multiple selected tags match any selected category; that category scope is
  combined with the chosen folders, date range and the job's matching criteria.
  Classification tags are not proof that a candidate meets a qualification.
- No arbitrary custom tags, model prompts, ranking rules or AI provider settings
  were introduced. Tag display/counting reads existing local metadata and makes
  no paid AI calls. No historical data rewrite is required for this release.

## Verification

- Added direct UI regression coverage for existing/new choices, safe option text,
  destination-bucket filtering, path validation, draft preservation, late defaults,
  exact bulk/email payloads, post-upload refresh, load errors and stale pages.
- Extended real PostgreSQL tests for tenant-scoped tag totals/searchable counts,
  multiple folder/tag retrieval boundaries, and stored tags in authorized previews.
- Extended both email-import HTTP contracts for exact named/existing destinations,
  original received dates and the unchanged default when no destination is sent.
- Extended tag filtering and preview tests for retained selections, numeric counts
  and escaped tag text. Browser checks cover desktop/phone controls and previews.

## Release Results

- All 935 backend tests passed without skips against an isolated PostgreSQL
  restore; the restore was removed. All 19 frontend suites passed.
- Nine hydrated responsive checks passed for uploads, expanded search filters and
  the CV library at 320, 768 and 1440 pixels. Native folder choices, new-folder
  validation, multiple folders/tags, date presets and tagged PDF previews were
  exercised visually. Screenshots use fictional records and remain local/private.
- Live browser checks confirmed the available destinations, editable new-folder
  entry and all ten tag-category counts. Scoped deployed handlers matched direct
  database counts for three permitted identities without modifying metadata or
  invoking AI. Handler tests use injected test identities, not new user sign-ins.
- Offline comparison preserved tokenization, embeddings and top-ten rankings for
  105 fixtures and 3,913 tenant vectors. No prompts, scoring or models changed.
- Deployed `clean-20261109t165952z` with a retained rollback/database backup. App
  and converter are healthy with zero restarts. Public assets, access boundaries,
  PDF/DOCX/DOC/TXT handlers and health checks passed. Candidate data, file/index
  fingerprints, OAuth/outreach records and all 20 unrelated containers were preserved.
- Runtime advisory checks covered all 102 installed packages without findings;
  the proposed Git tree passed its secret scan. Health/verification added zero
  paid AI calls. No real mailbox import or outgoing message was performed.

These checks do not certify new live mailbox imports, paid-AI accuracy or large
load capacity. The known missing original files/index vectors, unknown historical
received dates, cross-browser acceptance and offsite-backup limitations remain.
