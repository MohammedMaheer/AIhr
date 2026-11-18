# Retired Preview Removal

## Outcome

**v2026.11.18.1** records the user-authorized permanent removal of three retired
preview deployments from the VPS on 18 November 2026. This is an operations and
evidence release, not an application-code deployment. Customer names, private
resource inventories, configuration contents and credentials are not published.

Removed identified deployment directories, their uploads/databases and saved
backup copies, including an older archived preview deployment. Six unattached
project-owned Docker volumes, four empty project-owned networks, two exclusive
certificate lineages (live/archive/renewal material), app-only credentials and
obsolete app-specific logs were removed. No app data backup was deliberately kept
on the VPS for these three deployments.

## Removal Controls

- Verify project labels, compose ownership and all running/stopped container
  references. Reject native-process references, overlapping mounts, nested
  filesystems, changed target identities and shared certificate ownership.
- Acquire the existing host retention lock. The first attempt stopped before any
  deletion because the scheduled retention job held it; wait for successful job
  completion and take a fresh plan and preservation baseline.
- Use exact paths and force-free Docker volume/network commands. Do not prune
  shared images, containers, networks or volumes. No image was removed by this
  operation; all 35 images in the post-retention baseline remain unchanged.
- Replace only retired routes with an HTTP 410 / TLS handshake rejection rule.
  Keep the existing default-site ordering and gracefully reload nginx after a
  successful configuration check. Other sites' configuration and certificate
  hashes remain unchanged. No unrelated app was rebuilt or restarted.

## Shared Certificate Recovery History

Certbot history held **68 retired nginx configuration blobs in 46 checkpoints**.
Deleting whole checkpoints would have discarded other sites' recovery copies.

Under the shared retention lock and Certbot's native work-directory lock, filter
only exact retired original paths, reindex retained blobs and preserve their
bytes, permissions, ownership and modification times. Preserve unrelated metadata
and audit notes. Each replacement is staged, fsynced, checked and atomically
exchanged before the superseded copy is removed.

All **1,100 retained configuration blobs** passed sandbox recovery using the
installed Certbot recovery implementation. No live configuration was overwritten
by restore testing. A separate final comparison verified every retained mapping
and hash, and zero retired blobs remained. Eight isolated fixtures passed,
covering first/middle/last removals, an all-retired checkpoint, no removals,
lookalike names, missing blobs and symlink rejection.

## Preservation And Live Checks

| Check | Verified Result |
| --- | --- |
| Genuine CV originals | All 7,862 present and byte-identical; zero missing files |
| HR database | All 23 table fingerprints unchanged |
| Retained HR backups | All 55 files unchanged against the fresh baseline |
| Existing cold archives/manifests | All four files unchanged |
| Containers / reviewed native services | All 27 / 11 identities unchanged |
| Other Docker resources | Only the six approved volumes/four networks removed; 45 volumes remain |
| Other sites | All 26 route status checks unchanged; configuration/certificate hashes unchanged |
| Retired addresses | Five former hostnames return HTTP 410 and reject TLS |
| SmartHR | Expected unauthenticated login redirect; basic/deep health HTTP 200 |
| Active swap | Same file, type, capacity and priority; no activation/deactivation |
| Core, logo and UI | Runtime hashes unchanged |
| AI usage | Ledger unchanged at 312 calls / 980,393 tokens; no new provider calls |
| Additional backup review | 28 generic archive indexes readable; no target-named members |

An unrelated live SQLite database changed through its normal minute-based worker.
Its read-only quick check passed and the writer/timer were verified. This work did
not write, restore or checkpoint that database, and does not claim byte-identical
preservation of an actively written database.

## Disk Accounting And Limits

Immediate removal reclaimed **1,655,058,432 bytes**, approximately **1.66 GB**.
At final route verification free space was **38,659,391,488 bytes** (38.66 GB).
Small differences during final checks reflect configuration-history filtering and
normal live writes. Savings from the separate scheduled retention job are not
attributed to this removal.

Remaining hostname rejection rules and shared operational audit notes contain no
application database, upload, deployment source or app credential backup. Shared
stock images and unrelated backups remain protected.

The scope is the identified VPS resources and reviewed on-host backup locations.
This is not a forensic overwrite guarantee for SSD/storage media, nor deletion
of provider snapshots, off-site copies, local development repositories or DNS
registrations. Route comparisons and health checks are preservation checks, not
an exhaustive functional audit of unrelated applications.
