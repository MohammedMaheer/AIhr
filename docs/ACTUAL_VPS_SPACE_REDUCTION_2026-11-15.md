# Verified Whole-VPS Space Reduction

## Scope

Operations-only release v2026.11.15.4 reviews storage across the VPS without
rebuilding or restarting applications. Current CV originals, live databases,
uploads, credentials, active/rollback code and shared container storage remain
protected. There are no AI generation or search calls in this work.

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

```sh
mkdir -m 700 /private/empty-restore-directory
tar -xJf /path/from/ARCHIVED.json/archive.tar.xz -C /private/empty-restore-directory
```

Review the selected backup there before using the application's normal recovery
procedure. Archives are cold recovery storage on the same VPS, not off-site backup.

## Verification Checkpoint

Sixteen focused archival tests passed on Linux, and 28 archival/source-cleanup
tests passed locally. Actual consolidation, restore proofs, before/after filesystem
space, protected CV/database checks and other-app service identities gate completion.
No global Docker or volume pruning is authorized by this procedure.
