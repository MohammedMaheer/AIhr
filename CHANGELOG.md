# Release History

Releases use dated annotated Git tags. Each deployed version records its tested
source commit, deployment evidence and remaining limitations in the commit body.
Tags and shared commits are not rewritten. Runtime secrets, customer voice notes,
CVs and private audit receipts are excluded from Git.

## In Progress

- One recruiter workspace with permission-scoped administration controls.
- Browser Back/Forward navigation within the recruiter workspace; retire the
  separately styled administration page.
- Clickable upload/search totals and a paginated resume library.
- Named bulk/email upload folders and strict multi-folder search scopes, including
  saved jobs, history and request/cache identities.

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
