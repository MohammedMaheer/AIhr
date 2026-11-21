# Verified Whole-VPS Space Reduction

## Scope

Operations-only release v2026.11.15.4 reviews storage across the VPS without
rebuilding or restarting applications. Current CV originals, live databases,
uploads, credentials, active/rollback code and shared container storage remain
protected. There are no AI generation or search calls in this work.

## Measured Results

Whole-filesystem measurements include the new archives and recovery indexes, not
just removed source files. Sizes below are decimal GB/MB. Live applications
continue writing, so free space fluctuates after these checkpoints.

| Measurement | Before | After |
| --- | ---: | ---: |
| Free bytes | 18,711,244,800 | 20,370,206,720 |
| Used bytes | 84,187,467,776 | 82,528,505,856 |
| Used percentage | 81.80% | 80.19% |

**Actual net space reclaimed: 1,658,961,920 bytes, approximately 1.66 GB.**

| Reviewed collection | Sets / files | Original bytes | Verified archive bytes |
| --- | ---: | ---: | ---: |
| Old SmartHR audit backups | 45 / 384 | 1,087,641,976 | 109,163,692 |
| Unreferenced older runtime-test snapshots from another app | 5 / 10 | 917,457,697 | 263,445,024 |

All bytes remain recoverable. The oldest baseline and two newest eligible sets in
each collection remain unarchived. Customer-source/export snapshots, nightly and
manual backups, current/rollback releases, original CVs and live data are retained.
The native pip download-cache purge reclaimed another 26,497,024 allocated bytes;
it did not uninstall packages or remove model/browser assets. The whole-filesystem
net differs slightly from these component totals because of metadata and live logs.

## Cold Archival

`deploy/vps/scripts/archive-cold-backups.py` defaults to a dry run and applies only
an explicitly reviewed digest. It retains the oldest baseline and two newest
matching sets, rejects recent writes and original CV formats, and checks process,
service, symlink and container-mount references before removal. Existing retention
locking prevents concurrent cleanup. Application data directories are not targets.

Older backup files are consolidated losslessly rather than discarded. Every file's
SHA-256, size, permissions, owner/group and timestamp is checked against the archive,
and one complete backup set is restored to an isolated directory before any source
copy is removed. Recovery pointers remain at each original backup directory. The
archive and manifests are root-only; credentials/customer data are never published.

Restore into an empty private directory, never over a live application:

Create a new, unused private destination before extracting the archive path
recorded in its `ARCHIVED.json` pointer:

```sh
install -d -m 700 /root/cold-backup-restores
restore_dir=$(mktemp -d /root/cold-backup-restores/restore.XXXXXXXX)
tar -xJf /path/from/ARCHIVED.json/archive.tar.xz -C "$restore_dir"
```

Review the selected backup there before using the application's normal recovery
procedure. Archives are cold recovery storage on the same VPS, not off-site backup.

## Verification

- 28 focused archival/source-cleanup tests passed locally; 16 focused archival
  tests passed on Linux in the existing isolated QA image, without network access.
- Both archives passed independent complete file/standard-metadata/hash and XZ
  checksum verification. One complete set from each archive was additionally
  restored into an isolated temporary directory and every restored file hashed.
- All 576 pre-existing SmartHR backup files are accounted for: 192 unchanged at
  their original paths and 384 byte-identical inside the verified archive.
- All 11 reviewed other-app database snapshots are accounted for: six unchanged
  at their original paths and five byte-identical inside the second archive.
  Its five accompanying files also passed the archive verification.
- All 7,862 genuine CV originals remain byte-identical: no missing files or
  outside-storage paths. All 23 HR tables and source/logo fingerprints match the
  fresh pre-cleanup snapshot, including index and email-context records.
- All 27 container identities, images, start times, status and reported health
  match the baseline. The 11 reviewed native service identities also match.
- Live HTTPS, security-header, protected-route and asset-hash checks passed.
  SmartHR and PostgreSQL remain healthy. No temporary QA containers remain.
- The AI ledger is unchanged at 312 calls / 980,393 tokens. No search, generation,
  embedding or paid AI calls were made; deep health explicitly skipped AI.

The first SSH completion acknowledgement was lost. Its operation was not repeated:
completion was independently verified from the durable archive, manifests,
per-directory recovery pointers and an additional isolated restore.

An unrelated live SQLite database was not byte-identical across the review.
Investigation verified its existing once-per-minute maintenance timer updates a
last-run setting; read-only SQLite `quick_check` returned `ok`, and the service and
timer remained healthy. Temporary WAL/shared-memory files appeared during its
normal activity. No live database was restored, checkpointed, edited or deleted.
No pre-cleanup logical snapshot of that other app was taken, so byte-identical
business data for that actively changing database is not claimed.

## Other Apps And Remaining Capacity

The host review covered app directories, active mounts, recovery copies, release
references, logs, caches, container content and native services. Largest retained
areas include approximately 35.08 GB of shared containerd storage, 6.73 GB of Docker
volumes, a separate app's 10.44 GB backup directory, and a 2.95 GB website-release
directory. These overlap with per-app accounting and must not be added together.
The shared WordPress upload volume alone is 2.03 GB of active data, not cache.

No global Docker, image, volume, snapshot or journal pruning was used. Potentially
unique stopped-app recovery copies remain protected. Per-app identities, detailed
paths and manifests are kept in private local receipts, not published in this repo.

Disk remains near 80.2% used, so the existing capacity warning remains appropriate.
Further large reductions need a separately reviewed recovery/ownership decision;
clearing that warning does not justify deleting genuine uploads or useful backups.

The installed operations script is the reviewed source from this release. Runtime
remains `2f762d8c34d20ccdcb653c046bf83062e38f500d`; no application image was rebuilt,
no application was restarted, and the logo, UI and core behavior are unchanged.
Other apps received operational preservation checks, not full business-flow tests.
Archives are same-host cold recovery storage, not off-site disaster recovery.
