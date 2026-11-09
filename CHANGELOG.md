# Release History

Releases use dated annotated Git tags. Each deployed version records its tested
source commit, deployment evidence and remaining limitations in the commit body.
Tags and shared commits are not rewritten. Runtime secrets, customer voice notes,
CVs and private audit receipts are excluded from Git.

## v2026.11.10.1 - 2026-11-10

### Folder And Import Visual Polish

- Verify folder/tag/date controls, bulk upload and email import at desktop,
  tablet and phone widths using isolated fictional browser flows.
- Fix selected-tab contrast and modal notification obstruction. Hide unrelated
  file controls in email mode, preserve the file queue, shorten upload messages
  and retain empty/failed-import settings while clearing submitted passwords.
- Add modal/nested-form and import-flow regressions plus an explicitly opted-in
  local ingestion fixture. Upload batching, backend criteria and AI behavior are
  unchanged; the original recruiter logo remains intact.
- Remove eight verified stale smoke records and quarantine one invalid placeholder
  asset, with private backup and audit records. Preserve historical reports and
  genuine candidate data; retain 86 unindexed CVs for repair/removal review.
- All 942 fresh-PostgreSQL tests, 19 frontend suites and four responsive fixture
  flows passed. Deploy `clean-20261109t195514z`; live desktop/phone controls,
  cleaned library totals, three-attachment mailbox read and 132 scoped retrieval
  checks passed with zero new paid AI calls and 20 unrelated containers preserved.
- See `docs/FOLDER_IMPORT_VISUAL_REVIEW_2026-11-10.md` for evidence and limits.

## v2026.11.09.4 - 2026-11-09

### Folder, Tag And Date End-To-End Verification

- Fix the live Outlook `InefficientFilter` rejection with a shared, date-sort-safe
  attachment query in the connected and older credential-based Graph paths.
- Add real HTTP-to-storage/PostgreSQL/index tests for bulk and email ingestion,
  folder/subfolder/tenant boundaries, tags, date cutoffs, cache isolation, queued
  fallback and persisted result scope. Paid AI and external Graph responses are
  fixtures in these isolated write tests.
- Exercise real frontend scope controls through search submission, distinct
  pending requests, unchanged earlier result scopes and empty-selection guards.
- Correct CI to provide the vector extension and run all frontend suites.

### Verification And Deployment

- All 942 isolated PostgreSQL backend tests and 19 frontend suites passed.
  Deployed `clean-20261109t174922z` with rollback material, preserving business
  data, OAuth/outreach records and all 20 unrelated containers.
- Post-deploy live mailbox read validated three attachments without importing
  them. Across 132 read-only deployed search checks, 1,575 returned rows stayed
  within their selected scope. No paid AI calls were added.
- Offline tokenization, embeddings and top-ten rankings are unchanged. Runtime
  advisory checks covered all 102 installed packages without known findings.
- See `docs/FOLDER_TAG_E2E_2026-11-09.md` for exact coverage and limitations,
  including unknown historical received dates and intentionally no live imports
  or paid-AI accuracy evaluation.

## v2026.11.09.3 - 2026-11-09

### Folder And Tag Feedback

- Reviewed all three supplied voice notes locally without uploading audio or
  making paid transcription/AI calls; kept recordings/transcripts out of Git.
- Replace upload-folder suggestions with an explicit existing-folder dropdown,
  new-folder action, validated name entry and refresh. Preserve drafts and late
  responses; refresh a newly uploaded indexed destination into the dropdown.
- Email imports honor an explicit destination exactly, including existing email
  folders, instead of adding a second prefix. The unspecified default is unchanged;
  existing files and candidate ownership are not modified.
- Add searchable tag choices, workspace-scoped searchable counts and stored tags
  in CV previews. Retain strict multi-folder/tag/date filtering, provider-received
  dates, role permissions, original branding and AI matching behavior.
- Add UI, PostgreSQL scope and both email-entrypoint contract regressions. See
  `docs/FOLDER_TAG_ACCEPTANCE_2026-11-09.md` for acceptance and limitations.

### Verification And Deployment

- All 935 isolated PostgreSQL backend tests and 19 frontend suites passed.
  Nine changed-view responsive cases passed at 320/768/1440 pixels; live folder
  selection, multiple tags/dates and database-parity checks passed.
- Deployed `clean-20261109t165952z`, retaining rollback/backup data and preserving
  existing business records, connected accounts and 20 unrelated containers.
  App/converter health, asset/access/document checks and zero-paid-AI health
  checks passed. Original prompts, scoring and offline vector rankings are unchanged.
- Historical received dates remain unknown; no live mailbox import, paid-AI
  accuracy/load evaluation or cross-browser certification is claimed.

## v2026.11.09.2 - 2026-11-09

### Visual Verification And Polish

- Verified all eight workspace views in Chrome, with a 24-case responsive
  route/overflow matrix at 320, 768 and 1440 pixels. Inspected sign-in, public
  permission review, email composer, scheduling and administration dialogs.
- Corrected provider-specific import guidance, malformed-address validation,
  stale connection responses, duplicate submissions, reset states and failure
  totals. Preserve Outlook credentials support and Gmail help.
- Restore keyboard focus after asynchronous CV preview, improve active navigation
  contrast and phone touch targets, compact mobile results and wrap the narrow
  administration toolbar. Original top-left recruiter branding remains unchanged.
- Display experience units correctly, preserve zero experience and replace empty
  keyword charts with an honest unavailable state without changing saved scores.
- Remove one candidate-PII debug dump and fix the local viewer fixture MIME type.

### Verification

- All 18 frontend suites and 926 isolated PostgreSQL backend tests passed.
- Live PDF/DOCX pages and branded email-preview HTML rendered correctly. Local
  fictional PDF/DOCX/DOC/scanned-PDF/TXT views, page/zoom controls, field validation,
  provider choices, errors and keyboard focus were exercised without real sends.
- Search prompts, criteria, scoring and AI provider configuration are unchanged.
  Full paid-AI speed/accuracy, real delivery/calendar acceptance and cross-browser
  load testing are not newly certified by this UI release.
- Deployed `clean-20261109t144549z`; public asset hashes, tenant access controls,
  document handlers and live narrow-screen administration passed. App/converter
  healthy with no restarts, business records and 20 unrelated containers preserved,
  rollback backup retained, and health checks produced zero paid AI calls.

## v2026.11.09.1 - 2026-11-09

### Fixed

- Corrected a real preview integration blocker: the application CSP prohibited
  child frames and its default frame header also denied the self-hosted viewer.
- Permit same-origin child previews only. Allow embedding only for the exact
  PDF.js viewer page, retain application clickjacking protection, and restrict
  viewer connections to local/blob/data resources instead of external services.
- Add regression checks for effective application/viewer framing policy and all
  required viewer runtime bundles, including the ignored-by-default build folder.

### Verification And Deployment

- 926 backend tests passed without skips on an isolated PostgreSQL restore;
  all 17 frontend suites passed. Runtime advisory/secret checks and unchanged
  embeddings/rankings for 105 fixtures and 3,913 tenant vectors passed.
- Deployed `clean-20261109t072310z`. Public CSP/frame headers, viewer assets/MIME
  types, anonymous/tenant access checks and original PDF/DOCX/DOC/TXT handlers
  passed. The unchanged converter retained its source/image-bound rehearsal.
- App and converter are healthy; rollback/database backup retained, existing
  records and 20 unrelated containers preserved. Preview and health checks made
  no paid AI calls. Refresh an already-open app page to receive the new CSP.

### Remaining Limitations

- Fresh browser pixel-level verification is still unavailable. The new header
  checks verify public policy delivery, not the final rendered PDF canvas.
- Missing original PDFs and the other documented data/operational limitations
  from v2026.11.09.0 are unchanged.

## v2026.11.09.0 - 2026-11-09

### Added And Fixed

- Format-aware CV previews: original PDFs/scans, privately converted DOC/DOCX and
  complete original TXT content, with a separate extracted-text fallback.
- Self-hosted, lazy PDF.js viewer with page/zoom/search controls and document
  scripting/AI model downloads disabled. Isolated, network-disabled Word renderer
  uses bounded resources, deadlines and a short authorization-checked memory cache.
- Escaped report rendering, stale-response protection, honest filter/error states,
  valid-page recovery and accessible destructive-action confirmation.
- Compact mobile dashboard/reports/upload metrics, reachable scheduling actions,
  notification/navigation layering and cleaner settings/outreach layouts.
- Fixed JD skill-input exceptions and whitespace-only submissions; improved
  control labels, keyboard navigation, sign-in fields and reduced-motion support.
- Preserved the original recruiter logo, CVs, recruitment records and search scoring.

### Verification And Deployment

- 924 backend tests passed with no skips in an isolated PostgreSQL restore; all
  17 frontend DOM suites passed. Eight workspace views passed the responsive
  route/overflow matrix at 390, 768 and 1440 pixels before the preview extension.
- Real isolated DOC/DOCX conversion retained two-page fictional documents and
  original hashes; scanned PDF retained both pages. After deployment, read-only
  handlers with injected identities returned available PDF/DOCX/DOC/TXT previews.
  Anonymous access and cross-tenant access were rejected. Public viewer asset
  hashes and JavaScript/WASM MIME types passed.
- 102 runtime packages passed advisory scanning; the proposed Git tree passed the
  secret scan. Offline embeddings/top-ten rankings remained identical for 105
  fixtures and 3,913 tenant vectors. No paid AI calls or CV reindexing were performed.
- Deployed app `clean-20261109t012232z` plus the isolated preview worker. Both are
  healthy with zero restarts. Rollback/database backup exists; business records,
  saved credentials, outreach and all 20 unrelated VPS containers were preserved.
  Health checks still skip AI probes and added no AI calls.

### Remaining Limitations

- Final format-aware preview browser visuals were not verified because browser
  control was disabled; the user explicitly requested deployment anyway.
- Eight sampled older PDF records have missing originals. Text fallback cannot
  reconstruct original page layout; formatted previews need source restoration.
- Damaged/encrypted Word documents and substituted fonts can limit conversion.
  Existing missing vectors, historical-date gaps, hosted-CI billing restrictions
  and unverified offsite recovery remain. See `docs/UI_AUDIT_2026-11-09.md`.

## v2026.11.06.3 - 2026-11-06

### Added And Fixed

- Refined the CV library with file-type icons, readable dates and sizes, explicit
  empty/error states, accessible preview controls and direct page navigation.
  Pending searches and stale preview responses cannot overwrite the current view.
- Made folder, role/skill and date filters easier to scan, with folder search,
  date presets, removable active selections and synchronized result-view filters.
  Hidden checked folders retain their selection; an empty explicit scope never
  silently becomes All folders. Month-end date presets are bounded correctly.
- Moved the shared upload destination folder before the upload controls and added
  existing-folder suggestions without overwriting a user's in-progress edit.
- Refined administration tabs, local list search, status/limit labels and mobile
  forms. Keyboard navigation, pending-submit feedback and stale-dialog guards
  preserve the existing authorization and self-account protections.
- Fixed mobile toolbar overflow and collapsed search controls. Preview and form
  dialogs retain readable content, reachable actions and bounded scrolling.
  The original top-left logo, backend search criteria, scoring and AI prompts
  remain unchanged.

### Verification And Deployment

- 901 backend tests passed with no skips against an isolated PostgreSQL restore;
  all 15 frontend DOM suites passed. New coverage includes filter synchronization,
  invalid/empty scopes, pagination, date boundaries and stale asynchronous views.
- Browser visual checks covered desktop, tablet and mobile layouts using fictional
  local fixtures. After deployment, the authenticated live browser confirmed
  4,191 uploaded CVs, working pagination (26-50 of 4,191), mobile administration
  and dialog alignment, upload-folder suggestions and connected search filters.
  Checked mobile views had no horizontal overflow; no console errors were
  observed during these live flows. No live search or production write was sent.
- Offline compatibility retained identical tokenization, embeddings and top-ten
  rankings for 105 fixtures and 3,913 tenant vectors. All 102 installed runtime
  packages passed the advisory scan; the reviewed Git tree passed the secret scan.
- Deployed `clean-20261106t100021z`; public asset hashes, access protections,
  deployed-handler scope/count checks and healthy startup passed. The private
  rollback/database backup exists. Original CV contents, business records, HR
  decisions, notes, OAuth credentials, outreach and all 20 other running VPS
  containers were preserved. Health checks made no paid AI calls.

### Remaining Limitations

- This UI release does not establish new live AI accuracy, latency or provider
  acceptance results. It made no paid AI calls, sent no email/calendar invitations
  and did not reprocess CVs or change candidate decisions.
- 87 older records still lack searchable vectors; historical email-received dates
  remain unknown. Local tags are text-evidence labels, not qualification proof,
  and upload totals count records rather than unique people.
- GitHub-hosted CI remains blocked by the account billing lock. Offsite backup
  and disaster-recovery readiness have not been independently verified.

## v2026.11.06.2 - 2026-11-06

### Added And Fixed

- One recruiter workspace with permission-scoped administration controls.
- Browser Back/Forward navigation within the recruiter workspace; retire the
  separately styled administration page.
- Clickable upload/search totals and a paginated resume library.
- Named bulk/email upload folders and strict multi-folder search scopes, including
  saved jobs, history and request/cache identities.
- Local role/skill tags plus independent Uploaded and Email received date ranges.
  Dates unavailable in historical imports are not inferred or silently substituted.
- Empty explicit scopes stop before paid AI preparation; selected subsets are
  filtered before nearest-candidate ranking. Existing scoring/prompts are retained.
- The dashboard loads immediately instead of waiting for an artificial animation
  timer. The original recruiter logo remains unchanged.

### Verification And Deployment

- 901 backend tests passed with no skips against an isolated PostgreSQL restore;
  all 14 frontend DOM suites passed. Full workspace bootstrap, Back/Forward,
  role controls, folder boundaries, tag/date filters, cache separation, previews
  and count/list parity are covered.
- Offline compatibility: 105 fixtures and 3,913 tenant vectors retained identical
  embeddings, tokenization and top-ten rankings. Existing scoring/prompts/models
  were not changed. All 102 installed runtime packages passed the advisory scan.
- Deployed `clean-20261106t063644z`; public asset hashes and anonymous-route
  protections passed. Deployed handlers also passed with the real database and
  injected test identities, not a new real-user browser sign-in.
- Cached-text metadata recovery added tags to 2,343 index records and recovered
  known upload dates for 4,001 records. It was rehearsed on a private restore and
  verified idempotent; original files, vectors and source fields were unchanged.
- Business records, HR decisions, notes, connected OAuth credentials, outreach
  records and all 20 other running VPS containers were preserved. Rollback files
  and a database backup were retained privately. Health is green with zero
  restarts; health checks made no paid AI calls. The reviewed Git tree passed
  the secret scan.

### Remaining Limitations

- Fresh browser/visual inspection is blocked by disabled browser control. DOM
  checks are not a substitute for pixel-level desktop/mobile verification.
- Historical email-received dates were not stored and remain unknown. New email
  imports retain the provider's date; Received-date filters exclude unknown dates
  rather than substituting upload dates. Tags are local text-evidence labels,
  not proof that a candidate meets a qualification. Untagged CVs remain available
  when no tag filter is selected.
- 87 existing records still lack searchable vectors. This release did not perform
  OCR, reparse original CVs, send emails/calendar invitations or run new paid AI
  acceptance tests. Upload totals count upload records, not unique people.
- GitHub-hosted CI remains blocked by the account billing lock. An offsite backup
  and disaster-recovery restore have not been independently verified.

## v2026.11.06.1 - 2026-11-06

### Fixed

- Active candidate decisions no longer disappear from dashboard counts after
  30 days. Counts and click-through lists use the same user/workspace scope.
- Legacy status case variants are aggregated consistently.
- Failed or malformed count responses display unavailable values instead of
  fabricated zeros. Stale responses cannot overwrite a newer dashboard view.
- The rejected subtitle describes current status rather than an obsolete monthly
  time filter. The layout and original recruiter logo are unchanged.

### Verification

- 851 backend tests passed in isolated PostgreSQL; all 11 frontend DOM suites passed.
- 105 embedding fixtures and 3,913 tenant vectors retained identical rankings.
- 102 installed runtime packages audited with no known vulnerabilities.
- Deployed as `clean-20261106t051724z`; read-only live count/list parity, public
  asset hashes, healthy startup and preservation checks passed.
- Browser verification remains conditional on browser-control access being enabled.

## v2026.11.06.0 - 2026-11-06

Baseline source: `f4c28d6`, deployed before this feedback batch.

- Hardened upload quotas with per-company transaction locks, bounded worker
  offloading and DOCX package validation; retained existing UI and AI scoring.
- 842 backend tests and 11 frontend suites passed. Existing 168 DOCX packages
  remained compatible; original CVs, OAuth credentials and other VPS apps were
  preserved. See `docs/UPLOAD_RELIABILITY_2026-11-06.md`.
