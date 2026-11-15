# Reviewed QA Image Cleanup

## Scope

Operations-only release v2026.11.15.5 checks old SmartHR releases and Docker image
dependencies without rebuilding/restarting any application or calling AI providers.
The current app remains source `2f762d8`; logo, UI and core behavior are unchanged.

The 25 SmartHR release receipts were reviewed. The existing verified source-cleanup
dry run found **zero** eligible redundant source artifacts. The two remaining source
trees are current and rollback releases; both stay protected, along with every
database/configuration backup, recovery pointer and verified cold archive.

Docker's capacity summary reported a negative reclaimable size, so it is not used
to estimate actual savings. The detailed graph contains 827 image records, including
intermediate build images, not 827 independent full-size copies.

## Reviewed Policy

`deploy/vps/scripts/prune-qa-images.py` selects only explicitly reviewed old QA
leaves. Each eligible image must have a single recognized local QA tag, a retained
production base, exactly one added layer below 32 MiB, and the exact expected build
history adding pytest/httpx and switching users. Added COPY/RUN steps, missing
bases or ambiguous ownership are rejected. Local self-digests are distinguished
from external registry references without weakening ID/container protections.

The tool retains every production/foreign image, multi-tag image, externally
referenced image, container reference (including stopped containers), known
operations QA image, oldest eligible QA baseline and newest two QA images. Service,
cron, Compose and operations configuration pins are checked privately; configuration
contents are hashed for review binding and never serialized into receipts.

Only untagged ancestors exclusively used by selected QA leaves are additionally
eligible. Shared/tagged/pinned ancestry is kept. Children are removed before parents.
All removals use immutable SHA-256 IDs, never mutable tags, `--force`, a prune command
or volume/container deletion. Docker's `--no-prune` prevents implicit parent removal.

Apply requires the reviewed plan digest and an unchanged image graph, configuration
pin digest and container inventory. Before each removal, current container identity
and exact image metadata are rechecked. The existing retention lock coordinates
cleanup. A private, fsynced action log precedes deletion; retained image availability
and container identities are checked afterward.

## Applied Results

The reviewed plan was applied using the installed source from commit `dec9d5b`.
It removed exactly **39 obsolete QA images and 77 exclusive untagged intermediate
records**. Independent inspection confirmed the expected image-ID delta and
unchanged complete metadata for all **711 retained image records**, including all
74 production and 30 foreign/shared tagged image records. No production image was
removed; baseline, recent, operations-pinned and ambiguous multi-tag QA remain.

Whole-filesystem checkpoints include the new operations source, QA fixture files,
private receipts and continuing live logs. Sizes are decimal bytes/MB/GB:

| Measurement | Before this pass | Final preservation snapshot |
| --- | ---: | ---: |
| Free bytes | 20,369,895,424 | 20,564,975,616 |
| Used bytes | 82,528,817,152 | 82,333,736,960 |
| Used percentage | 80.19% | 80.00% |

**Actual net space reclaimed: 195,080,192 bytes, approximately 195 MB.** The removal
step itself measured 195,846,144 additional free bytes. Differences reflect new
evidence/operations files and live host writes. QA added-layer virtual sizes
totaled about 43 MB; Docker's virtual/negative reclaimable estimates were not used
as filesystem savings. Shared image layers are not counted once per image.

## Verification

Forty-eight focused QA-image/release-source/cold-archive tests passed locally and
on Linux. Linux tests used a retained QA image with no network, no Docker socket,
no live database/data mount, a read-only root/source, dropped capabilities and
bounded CPU/memory. Fixtures covered stopped/new containers, config references,
shared parents, changed tags, recent/pinned images, registry digests, unknown build
steps, review mismatch, protected-image disappearance and immutable-ID commands.

- All 7,862 original CVs remain byte-identical, with no missing or outside-storage
  references. All 23 HR table fingerprints match the fresh pre-cleanup snapshot,
  including embeddings, email context, searches, scorecards and usage history.
- All 237 physical HR backup/pointer files and all four cold archive/manifest files
  match their pre-cleanup hashes. Every needed recovery copy remains available.
  The prior archive content/restore proofs remain applicable because hashes match.
- All 51 volume names are unchanged. No volume, database, upload or model cache was
  deleted. All 27 container identities, images, starts, mounts and reported health
  match; all 11 reviewed native service identities match as well.
- Exact independent image inspection found only the 116 planned removals; every
  other image retained its tags, digests, parent, timestamp, layer list and size.
- The source-release dry run still selects zero artifacts. Current and rollback
  source trees and all release receipts/backups remain in place.
- Live HTTPS, authentication guards, security headers and deployed asset hashes
  passed. SmartHR/PostgreSQL remain healthy, and the temporary test container was
  removed. No app image was rebuilt and no app was restarted.
- The AI ledger remains 312 calls / 980,393 tokens: **zero new paid AI calls or
  tokens**. Deep health explicitly skipped AI. No live search or scorecard calls
  were needed for this operations-only change.

Another app's existing minute-based maintenance continues writing its live SQLite
database. Its timer/service are healthy and read-only `quick_check` returned `ok`.
That expected raw-file hash drift is explicitly reviewed, not described as
byte-identical unrelated business data. No restore, checkpoint or database edit
was performed. Other apps received preservation/liveness checks, not full product
workflow tests.

## Remaining Limits

Free space is approximately 20.56 GB; utilization remains near 80%, so the existing
capacity warning stays appropriate. No further source deletion or broad image
pruning is justified by this review. Larger reductions would require a separate
decision about historical production-image retention, not silently treating useful
rollback versions or other apps' storage as disposable.

No production image, genuine CV, needed backup, other-app data or volume is an
authorized target. This is not a production-image retention policy and does not
establish off-site disaster recovery. Runtime remains `2f762d8` and the installed
operations source matches the versioned tool; the logo, UI and core are unchanged.
Private configuration, customer data, detailed per-app inventory and action logs
are excluded from GitHub.
