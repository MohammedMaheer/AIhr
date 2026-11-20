# Desktop Offload Release Gate

**Decision: do not enable browser offload in production.** The staged flow
kept rankings and fallback correct, but could not reduce VPS embedding work
while protecting the shared index from incorrect browser results.

## What Was Tested

- The deployed SmartHR image ran in a disposable, network-isolated VPS stack
  with actual MiniLM, pgvector and local storage. It used synthetic users and
  18 synthetic PDFs per trial. No production database, CVs or AI credentials
  were mounted.
- The reference used the authenticated multipart upload route and the live
  batch size of eight. The comparison used the same route with a test-only
  storage-first hook and a simulated busy signal. A real Chrome worker
  received the server-extracted text under a staged, expiring lease. The
  browser's calls were relayed to authenticated FastAPI test clients, not
  public production endpoints.
- The staging verifier used the real VPS index writer and real SQL search.
  It indexed only vectors generated from the original files by the server.
  No submitted browser vector became authoritative.

| Gate | Result |
| --- | --- |
| Ranking and criteria | **49/49** ranked comparisons matched exactly, including an exact 10-candidate search and folder, tag and date filtering. |
| Busy-only handoff and fallback | Passed: no lease for healthy or cold paths; expired or abandoned work recovered on the VPS; duplicate completion did not write a second index row. |
| Data boundaries | Passed: another tenant could not claim or submit a job; a submitted but unverified vector was not searchable; malformed responses were rejected. |
| Incorrect browser result | A normalized but incorrect result failed the comparison. The independently computed VPS result remained authoritative. |
| Less VPS inference | **Failed.** Both paths embedded all 18 texts in the same `8, 8, 2` VPS calls. The warm browser handoff also took longer in the measured test. |

On the repeat run, direct VPS batching took **0.43 to 0.77 seconds**. The two
already-warm handoffs took **1.21 to 1.37 seconds**. These timings include
staged transport; they are not production upload latency. The busy signal
and abandoned-lease recovery were controlled test scenarios, not a production
scheduler or a load test. Previous standalone browser GPU benchmarks do not
remove the VPS verification work. The ordinary pilot tests also passed.

## Recommendation

Keep the deployed VPS batching and recovery behavior. A managed desktop
worker may be viable if administrators want to operate it as a trusted,
authenticated backend worker with restricted job access. An ordinary browser
session does not establish that the model ran correctly. Job tokens, a model
version, valid shape and normalized vector length only establish protocol
boundaries. Keep the VPS as the fallback and sole writer until a trusted
worker can be enrolled and benchmarked without introducing new ranking risk.

## Reproduce

From `tests/local-upload-pilot`, install the pinned Node dependencies and
prepare the pinned model assets. Set `PILOT_BASELINE_SSH` and
`PILOT_BASELINE_IMAGE` for an authorized VPS and its cached SmartHR image.
The VPS needs the cached pgvector 17 image and read-only MiniLM model volume.
Then run `npm run verify-handoff`. The launcher creates a private network and
temporary containers, validates their labels before cleanup, and does not
restart or mutate the live application. No paid AI calls are made.
