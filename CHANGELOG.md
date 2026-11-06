# Release History

Releases use dated annotated Git tags. Each deployed version records its tested
source commit, deployment evidence and remaining limitations in the commit body.
Tags and shared commits are not rewritten. Runtime secrets, customer voice notes,
CVs and private audit receipts are excluded from Git.

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
