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

## Verification Checkpoint

Forty-eight focused QA-image/release-source/cold-archive tests passed locally and
on Linux. Linux tests used a retained QA image with no network, no Docker socket,
no live database/data mount, a read-only root/source, dropped capabilities and
bounded CPU/memory. Fixtures covered stopped/new containers, config references,
shared parents, changed tags, recent/pinned images, registry digests, unknown build
steps, review mismatch, protected-image disappearance and immutable-ID commands.

The reviewed plan selects 39 test-only leaves and 77 exclusive intermediate image
records, retaining 711 image records. QA added-layer virtual sizes total about
43 MB, not the sum of full image sizes; actual filesystem savings and complete
preservation checks must be verified after supervised application.

No production image, genuine CV, needed backup, other-app data or volume is an
authorized target. This is not a production-image retention policy and does not
establish off-site disaster recovery.
