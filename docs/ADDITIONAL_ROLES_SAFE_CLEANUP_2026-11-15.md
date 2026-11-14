# Additional Role Acceptance And Safe Cleanup

## Scope

Release v2026.11.15.2 changes only the reviewed release-source cleanup tool and
its tests/documentation. Application code, logo, UI, provider settings, strict
CV eligibility and HR scoring remain unchanged. Real CVs and backups are retained.

## Cleanup Safeguard

The prior cleanup wrapper compared its dry-run and applied target sets only
after deletion. Although targets were independently verified and constrained to
redundant SmartHR source artifacts, this did not bind deletion to the operator's
reviewed plan. Applying now requires the dry-run `plan_sha256`. The digest binds
target paths, receipt evidence and canonical container identities/mounts. A changed
plan is rejected before removal, and source hashes are rechecked during apply.

Active/mounted releases, the two newest deployed snapshots and the current
predecessor remain protected. No CV, backup, private configuration, Docker image,
container, volume or unrelated application file is a cleanup target.

## Verification Checkpoint

Twelve focused cleanup regressions passed. Planned live checks cover ten-result
HR recruiting, networking/CCNA, graphic design/Photoshop and sales/CRM, with small
source-reviewed scopes to limit inference costs. Production-matched suites,
restore/recreation gates, real-provider results, immutable CV/index checks and
measured cleanup savings will be recorded after completion.

## Limits

No population-wide hiring-accuracy percentage or 10/10 reliability is claimed.
Stored genuine scorecard reuse is distinguished from new paid inference. Safe
cleanup may reclaim only modest space; shared Docker resources and genuine
candidate records will not be deleted to chase a disk threshold.
