# Adjacent Backup Recovery Review

## Outcome

Published as **v2026.11.16.1** after the recovery review on 15 November (IST).
This is an **audit/evidence-only release**, not a claim that backup compression was
applied. A user-confirmed cleanup in another chat changed the VPS inventory during
review. No archival or original-backup deletion was applied by this turn. The last
manual recovery copy was left uncompressed and all surviving compressed nightly
copies were restore-tested without changing application behavior.

The initially observed backup directory contained approximately 10.44 GB: five
manual SQLite snapshot sets and three gzip-compressed nightly copies. The separate
retention run, recorded at 23:25 IST on 15 November, removed four older manual
snapshots and retained one. Those actions are not attributed to this audit and
were deletions, not lossless archival by this work.

The other chat subsequently created a fresh nightly copy. Final retained storage
is **6,200,545,280 allocated bytes (approximately 6.20 GB)**, comprising the last
manual snapshot and four compressed nightly groups. Final host free space was
approximately 38.67 GB; the host-space change belongs to concurrent work and normal
live writes, not compression savings claimed here.

## Why No Further Compression

The fresh dry run found only one remaining manual snapshot and zero eligible old
sets under the conservative keep-recent policy. Its apply phase was never invoked.
Compressing that last ready-to-use recovery copy would conflict with the separate
retention policy's retained-manual-copy assumption. Existing nightly files are
already compressed and expected by the scheduled backup/recovery code.

An archival prototype was tested in isolation but was not shipped as a project
feature or applied to production backups. It remains private audit material. No
unused experimental application dependency, runtime change or recurring cleanup
was installed.

## Recovery Tests

The other chat's fresh backup job briefly held the existing backup lock. The first
verification attempt correctly refused to overlap it. After it finished, the
batch verification acquired the shared retention lock and the existing exclusive
backup lock to obtain a stable inventory.

All **four** compressed nightly groups were tested with the existing backup
module's restore verifier. Each test restored into a newly created isolated
scratch directory and verified:

- The compressed archive SHA-256 against its saved manifest.
- The restored database SHA-256 against the original snapshot hash.
- Full SQLite `integrity_check`.
- Every recorded table row count.
- Stored original-attachment and archived-file byte totals.

All checks passed. The remaining manual database also passed a read-only immutable
full integrity check, required-table/state checks and file/history byte accounting.
Its empty WAL and recovery sidecars were retained, not removed or rewritten.

All **14 original backup/status/manifest/lock files** matched their hashes before
and after the successful batch verification. Backup script/configuration/unit
fingerprints were unchanged across that verification; the daily timer remains
active. All temporary restore directories were removed. No live database was
overwritten, checkpointed or repaired.

Verification ran with a half-core CPU quota, 512 MiB memory cap and low I/O priority.
Only temporary restored files were deleted by the verification code; originals
remained intact.

## Application Preservation

- All 7,862 SmartHR CV originals remain byte-identical. Their hashes also match
  the previous completed audit, across the concurrent cleanup interval.
- All 23 HR table fingerprints and runtime source/logo hashes match the fresh
  post-cleanup baseline. All 117 retained HR backup/pointer files, four existing
  cold archive/manifest files and 51 volume names match that baseline.
- All 27 container and 11 reviewed native-service identities remain unchanged.
  This audit performed no application rebuild, restart or core/UI/logo change.
- Live HTTPS, security headers, authentication guards, deployed asset hashes and
  app/database/deep health checks passed. The monitor reports healthy.
- The AI ledger remains 312 calls / 980,393 tokens: zero new paid search,
  generation, embedding or other AI-provider calls by this work. Health skipped AI.
- Forty-eight existing cleanup/archival safety tests passed locally. Previous
  application release-suite results are historical, not presented as newly run.

The adjacent live SQLite database continues its existing maintenance writes. A
read-only `quick_check` passed; byte-identical unrelated live business data and
full unrelated-app workflow testing are not claimed.

## Limits And Attribution

The four externally deleted historical snapshots are not available at their
original paths. A newer valid backup is not proof of byte-for-byte preservation
of every older snapshot; that preservation is explicitly **not claimed**. This
audit did not attempt filesystem undelete or alter the other chat's retention
settings, backup schedule or operational decisions.

These remain same-VPS backups, not off-site disaster recovery. No reboot, failover
or live-database replacement was performed. Private logs, full per-app paths,
configuration, database contents, prototypes and detailed receipts remain outside
GitHub. Runtime remains `2f762d8c34d20ccdcb653c046bf83062e38f500d`.
