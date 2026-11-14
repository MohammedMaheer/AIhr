# Strict Search And Similar Profile Acceptance

## Scope

Release v2026.11.14.6 adds a separate, explicit similar-profile preview after a
zero-result exact search. Strict eligibility, existing score weights, logo,
original files, folder/tag/date semantics and candidate actions are preserved.
The preview uses local embeddings and existing indexed CV text, not a paid
provider. It is not a verified HR scorecard and makes no exact-match promise.

## Correctness Fixes

- Parse location clauses correctly when followed by numeric qualifications;
  do not parse the role before "based in" as the requested city.
- Treat recognized old address-parser duty fragments as unknown locations;
  do not reject genuine CVs solely on those corrupt indexed values. Future
  extraction uses word-bounded labels and the earliest known header place.
  Final AI/source eligibility verification still applies.
- Preserve selected company/folders/tags/date basis and range in the new
  preview. Omit the folder field for all authorized folders; reject an explicit
  empty folder selection. Never expand scope to fill a requested count.
- Require authentication, CSRF, company quota, validation and rate limits.
  Bound the retrieval pool, skill count and output size. Escape profile fields;
  cancel stale client requests and keep original exact search results intact.

## Local Verification

- 118 focused profile/precision tests passed.
- 10 new service/API tests and three real PostgreSQL scope tests passed.
- All 26 frontend DOM suites passed, including opt-in, fixed scope,
  all-folders handling, escaping and stale-response cleanup.
- Opt-in localhost browser/HTTP/worker/PostgreSQL workflows passed for existing
  search scopes and the new zero-result/similar path at 1440px and 390px widths.
  Screenshots were inspected; no horizontal overflow or dialog clipping found.
  These workflows use fictional CVs and mocked paid providers, not live AI.

## Live Verification

Production-runtime gates, deployment and bounded real-provider strict searches
are pending at this source checkpoint. Results will be recorded after execution.

## Limitations

- Live browser control stopped because it could not safely verify the current
  browser URL. No further live browser automation was attempted this turn.
  Isolated browser tests are not represented as live visual acceptance.
- Indexed details can be incomplete. Similar profiles display that warning,
  the unmet/unconfirmed criteria and a link to the original CV for review.
- A request for ten returns ten only when ten verified eligible profiles are
  available; otherwise the existing truthful shortfall is retained.
- Bounded cohort checks are not a population-wide accuracy benchmark.
- GitHub-hosted CI was previously blocked by account billing restrictions;
  production-runtime gates must be reported separately from hosted CI.

Private candidate, mailbox, usage and integrity receipts are not published.
