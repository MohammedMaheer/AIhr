# Upload Recovery And Desktop Assist Pilot

The manual upload queue no longer replays a batch after an ambiguous failure.
A disconnected request or a gateway error can occur after the server has
saved some files. Retrying blindly can create duplicate CVs because each
upload generates a new storage identity.

| Condition | Recruiter upload behavior |
| --- | --- |
| Offline before sending | Keep selected files in the open tab. Resume manually when connected. |
| Explicit rate limit (`429`) | Retry at most twice automatically, honor usable `Retry-After` values, and wait for manual action if the requested pause is longer than 30 seconds. |
| Explicit size rejection (`413`) | Split a multi-file group into smaller groups. Do not replay an unchanged oversized file. |
| Missing, timed-out, or incomplete response | Mark sent files **Unconfirmed** and direct the recruiter to Resume Library. Continue only untouched files on the next Start Upload. |

The queue does not claim that files were saved after an unconfirmed request.
Completed or unconfirmed files are not submitted again by Start Upload.
Closing or reloading the tab can lose pending selections. The app does not
write CVs into persistent browser storage. The logo, server batching,
ranking, candidate applications and mailbox imports are unchanged.

## Desktop Assist

The loopback pilot now tests dynamic routing with simulated server-issued
leases. It reuses an eligible, consenting desktop's already-running model
only when the VPS is reachable, reports pressure, has saved the original and
grants the desktop a time-limited job on the VPS-extracted text. A healthy
or unavailable server, expired or incomplete lease, cold model, phone,
tablet or other ineligible device does not trigger local computation. A
desktop assist is capped at 1.5 seconds and stops on cancellation, page
backgrounding, or connectivity loss. Its vector is a comparison result
only; it cannot write to the shared search index.

An offline VPS cannot accept originals, save metadata or make results
searchable. Desktop compute alone cannot replace it. Before enabling real
offload, implement a durable server job and a single trusted index writer,
with idempotent recovery and independent verification of results. Actual
index availability during a VPS outage requires a reachable standby backend.

## Verification

- All 27 frontend suites passed. The upload recovery browser suite passed at
  1440, 768, 390 and 320 px, including busy retry, dropped response and no
  automatic duplicate submission. Long filenames and messages wrap.
- The isolated pilot passed 12 routing cases, including cold no-download,
  healthy, busy, unreachable, uncommitted, ineligible, expired, opt-out and
  interrupted work. A warm eligible assist produced the same vector on the
  same synthetic text. The existing 12 device fallback cases also passed.
- The production release contains the upload JavaScript change only. The
  desktop policy, model and tests are not served by the production app.
  Live health passed with the LLM probe skipped. The logo, backend, CV and
  AI ledger fingerprints, and other containers were unchanged across the
  switch. Neither test requires live CV data, provider requests or paid AI.
