# Zero-Result Usage Reporting And Safe Cleanup

## Correction

`run_hr_scorecard_task` previously completed two early-return paths without the
token summary: no CVs in an explicit scope, and no eligible retrieved candidates
after JD preparation. The latter could have billed preparation calls even though
its missing progress field looked free to a reporting client.

Both paths now persist `token_tracker.get_summary()` and elapsed worker time using
the same fields as normal completion. The provider ledger is unchanged. No extra
inference is introduced; retrieval, strict eligibility, prompts, cache identities,
HR score weights, original logo and UI are unchanged. Historical completed records
are not rewritten or guessed from global provider totals.

## Verification Checkpoint

147 targeted regressions passed, including durable persistence, both public
status/results handlers, empty scope, empty retrieval, raw-query fallback,
out-of-folder rejection and cached preparation. Production-matched suites,
restore/recreation rehearsal, bounded live ledger checks and actual disk savings
will be recorded after completion.

## Conservative Disk Review

The image dependency audit found no safe install-only QA-image targets under the
retention guards: their layers remain referenced by retained images. No Docker
image, container or volume is selected for removal, and an unused cleanup tool
will not be added to the application.

Cleanup is restricted to hash-verified redundant release sources and the exact
transfer archive created for this rollout. The archive can be removed only after
successful deployment, a complete matching extracted source snapshot, verified
archive bytes and an unmounted path. Extracted active/rollback snapshots, images,
CV originals, database/configuration backups and other applications remain intact.

## Limits

Safe savings may be modest because retained backups, image layers and unrelated
applications are deliberately untouched. Report actual reclaimed bytes rather
than summed virtual image sizes. New reporting fields apply to newly completed
tasks only. No population-wide accuracy or fresh live visual acceptance is claimed.
