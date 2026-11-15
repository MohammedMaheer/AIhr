# Verified Inactive Swapfile Removal

## Authorized Scope

Operations release v2026.11.15.6 removes only `/swapfile`, the explicitly authorized
inactive 4 GiB Linux swap file. It does not alter any application source, logo,
matching/scoring behavior, live database, CV, backup, volume or active swap.
Runtime remains `2f762d8c34d20ccdcb653c046bf83062e38f500d`. No app rebuild/restart,
swap activation/deactivation, boot change or reboot was performed.

## Dependency Review

- Verified a root-owned, mode-0600 regular file, one hard link, the exact expected
  inode/device/size/timestamps, and a normal Linux `swap` signature. A symlink,
  device, different size/owner/permissions or saved hibernation image was refused.
- Verified `/swapfile` was absent from active swaps, including inode/alias checks.
  The separate active swap remained enabled at its original inode, size and
  priority. Available RAM was approximately 4.77 GB before the operation.
- Found no open process descriptors, mapped-file references or loop-device
  backing references to the target.
- Scanned 2,973 configuration/helper files across standard system/boot, cron,
  local administration and app deployment/operations locations for the target
  path and UUID. No references were found. Contents were not logged or published.
- Extracted both installed initramfs images into isolated private temporary
  directories and checked embedded configuration. Neither referenced the target.
  Both the running-kernel image and installed next-kernel image were covered.
  Temporary extraction directories were removed after inspection.
- Kernel resume target/offset were unset; the running command line contained no
  resume option. No boot or configuration regeneration was necessary.

## Guarded Action

A private, one-target guard recorded a reviewed plan digest. Nineteen focused
refusal/reference tests passed on Windows and native Linux without invoking the
real removal path. These covered active aliases, absent/changed active swap,
symlinks, devices, hard links, unexpected ownership/permissions/size, hibernation
signatures, configuration references spanning read buffers and missing approval.

Immediately before unlinking, the guard rechecked the target identity, configuration
fingerprints, boot hashes, process/loop references, kernel resume state and active
swap. The only pre-existing file removed was the literal `swapfile` entry, using
an open root-directory descriptor; newly created private extraction scratch was
cleaned separately. No application-directory deletion, volume/image pruning,
swapoff, swapon or service operation was issued. Existing retention locking and
bounded CPU/memory/idle I/O coordinated the operation.

The one-off helper and raw receipts stay private; no recurring cleanup task or
general-purpose production deletion feature was installed.

## Measured Capacity

Measurements use decimal GB and include the new private evidence files and normal
live host writes; free space continues to fluctuate after these checkpoints.

| Measurement | Fresh pre-operation snapshot | Final preservation snapshot |
| --- | ---: | ---: |
| Free bytes | 20,521,914,368 | 24,816,635,904 |
| Used bytes | 82,376,798,208 | 78,082,076,672 |
| Used percentage | 80.04% | 75.87% |

The unlink reclaimed **4,294,971,392 allocated bytes**. Net whole-operation free
space increased by **4,294,721,536 bytes**, approximately **4.29 GB**, after the
small evidence/logging overhead. Free space is approximately **24.82 GB**.

The existing monitor reported 75.89% used, healthy app/database/deep health and
no remaining issues. Its capacity warning cleared without modifying thresholds.
The slight percentage difference reflects monitor/filesystem accounting and timing.

## Preservation Checks

- An independent post-check confirmed `/swapfile` absent; active swap identity,
  capacity, priority and systemd state preserved. Active swap usage counters may
  change with normal memory activity; they are not immutable data fingerprints.
- Both boot images, the running kernel command line, fstab and all reviewed
  configuration fingerprints remain unchanged. No temporary boot extractions remain.
- All 7,862 original CVs remain byte-identical, with zero missing/outside-storage
  references. All 23 HR table fingerprints match the fresh pre-operation snapshot,
  including index/email context, searches, scorecards and AI usage records.
- All 237 physical HR backup/pointer files and four cold archive/manifest files
  match their original hashes. All 51 Docker volume names are unchanged.
- All 27 container identities, image references, starts, mounts and reported health
  match the baseline; all 11 reviewed native service identities also match.
- Live HTTPS, security headers, authentication guards and deployed asset/source/logo
  hash checks passed. No application image or other app was restarted by this work.
- The SmartHR AI ledger is unchanged at 312 calls / 980,393 tokens. No paid AI,
  search, generation or embedding call was made; deep health explicitly skipped AI.

An unrelated live SQLite database continued its existing minute-based maintenance
writes. That expected raw-file hash drift was separately reviewed, and read-only
`quick_check` returned `ok`. No database was restored, checkpointed or edited.
Byte-identical unrelated live business data and full unrelated-app workflow tests
are not claimed.

## Limits

Boot verification was static; no real reboot/failover test was performed. Removal
was ordinary filesystem unlink, not secure erasure. This operation does not change
production-image/backup retention policies or provide off-site disaster recovery.
Active swap, genuine CVs, needed backups and other-app data remain protected.
Host UUIDs, configuration contents, guard source/tests and detailed audit receipts
are kept private rather than published with this report.
