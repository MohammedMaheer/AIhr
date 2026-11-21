# Managed Desktop Worker Pool

**Status: tested in staging, not deployed.** A company admin enrolls or
revokes a worker once. Desktop workers run separately from recruiter web
sessions, and there are no per-job authorization prompts. Random desktops
on the network are not trusted automatically.

## Routing

1. The VPS first saves the original CV and tracks it as usual. On the healthy
   path, it handles the embedding itself. The staged coordinator only
   offers desktop work when the existing VPS upload worker slots are full.
2. The pool selects a ready, recently seen worker in the same tenant with
   no active lease. One job per desktop bounds its load. Full, paused,
   stale or revoked workers are not offered new work. If the entire pool
   is occupied, the VPS takes the normal path.
3. The worker proves possession of its enrolled signing key before it gets
   the VPS-extracted text. The signed lease binds the worker, tenant, deadline,
   pinned model and exact text digests. The VPS checks signatures, expiration,
   vector shape and original file state before its existing index writer
   receives a result.
4. After a timed-out lease, the pool can try a different worker once. If
   no safe desktop can finish, the VPS indexes the existing originals.
   Late, duplicate and already-revoked results cannot complete the job.

The pilot stores worker presence, reservations and saved-job references in
PostgreSQL. The pending job can be reconstructed without sending the files
through upload again. Broker metadata contains storage references, not a
second copy of CV text. Leases and recovery are driven by the staged runner,
not by a public production endpoint or an always-on scheduler.

## End-To-End Results

The final run used two independently enrolled, native Windows worker processes
on one workstation, 18 synthetic PDFs per trial, and the deployed app image
with isolated storage and pgvector on the VPS. The workload induced busy
upload slots without deliberately loading the live service. The timings are
staged application CPU and wall time, not production host-wide load.

| Gate | Result |
| --- | --- |
| VPS CPU, median of three save-to-index trials | **462.17 ms direct vs. 155.44 ms managed**, **66.37% less** |
| VPS model inference per 18-file group | **Three batched calls vs. zero** on the managed path |
| End-to-end wall time, median | **0.44 s direct vs. 0.54 s managed**, including the staged relay |
| Rank parity | **70/70** ordered comparisons passed, including 10 exact candidates and scoped folder, tag and date searches |
| Numerical parity | Minimum cosine similarity **0.99999988**; maximum rank-score difference **0.00000025** |
| Pool and fallback | Full worker skipped, all-full pool fell back, real worker stopped and lease expired, coordinator memory reset, another worker completed the same saved job, and revoked results were refused |
| Trust | Admin-only enrollment, cross-tenant revocation denial, signed heartbeats, altered-text and altered-vector rejection, duplicate and late result rejection |

No paid AI calls or production candidate data were used. Production code,
logo, ranking rules and the batch size of eight were not changed. The native
worker uses [ONNX Runtime's CPU execution provider](https://onnxruntime.ai/docs/execution-providers/)
and [Ed25519 signing](https://nodejs.org/api/crypto.html) with separate
ephemeral device and coordinator keys in the pilot.

## Before Production

The CPU gate passed. The worker pool has not been connected to the live
upload service. A production release still needs a managed agent installer
with protected persistent device keys, authenticated admin enrollment and
revocation, a deadline-driven scheduler around the durable job state, and
live monitoring and rollout controls. Validate service restarts, key rotation,
simultaneous publishes and per-tenant enrollment on separately managed
physical machines. Windows was tested; other platforms are not certified by
this pilot. A trusted signing key authenticates a worker, not its computations,
so host management and enrollment policy remain part of the security boundary.

To reproduce the isolated run from `tests/local-upload-pilot`, use
`npm ci --ignore-scripts`, `npm run prepare-assets`, set the approved
`PILOT_BASELINE_SSH` and cached `PILOT_BASELINE_IMAGE` values, and run
`npm run verify-managed-worker`. The same isolated VPS requirements as
`verify-handoff` apply. No production service is restarted.
