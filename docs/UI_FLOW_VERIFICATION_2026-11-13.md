# UI And Flow Verification: v2026.11.13.4

## Fixes

- Overlapping dialogs share the original background state. Closing several dialogs together no longer leaves the workspace inactive, and closing an older dialog keeps focus in the remaining one.
- Candidate analysis is a labeled keyboard-accessible dialog, rejects duplicate openings, restores focus and no longer overrides the body's original scrolling style.
- Candidate-status lists ignore obsolete responses after navigation, another status request or an account-context change. Mobile layouts retain field labels and candidate actions.
- Loading saved email templates does not overwrite a draft typed while the list was loading. Stale refreshes cannot replace newer records.
- Template save, delete and apply operations prevent dismissal and duplicate requests while pending, retain edited text after failures and focus error feedback. Their action bar stays visible on small screens.
- Failed administration saves focus their error message while retaining the entered form values.

No logo, image asset, search criterion, matching/ranking rule, scorecard, backend API or production database schema was changed.

## Verification Evidence

- All 23 frontend DOM suites passed. New regressions cover overlapping-dialog removal, focus recovery, analysis accessibility, stale candidate lists, template loading races and pending template operations.
- The recent-feature Playwright suite passed at 1440x900, 1280x720, 900x768, 600x800, 390x844 and 320x568.
- The remaining-pages suite passed at 1440x900, 900x768, 390x844 and 320x568. It covers dashboard actions, status lists, report deletion confirmation, saved results, JD skills, settings, company/user create/edit/delete dialogs, email composition/templates, interview creation/edit/cancellation/history and candidate analysis. Destructive buttons were not confirmed against production.
- PDF, formatted DOCX, legacy Word, scanned PDF and text previews were checked at all four sizes. Canvas-pixel assertions reject blank PDF renders; text mode and dialog closure are also checked. Rendered Word previews here use previously generated fictional conversion fixtures, not production CVs.
- An additional real browser-to-HTTP-to-PostgreSQL test passed at desktop and mobile widths: create/publish a job page, submit an actual fictional Word CV, parse/store/index it, review and shortlist the applicant, and schedule an application-linked interview without sending email. SQL assertions verify two separate application, embedding and interview records, retained extracted text and local search tags.

## Honest Boundaries

The visual fixture server contains fictional records and makes no live provider mutations. The browser/backend test uses a disposable loopback PostgreSQL database, fixture authentication, disabled startup workers and deterministic embedding vectors. Parsing, storage, application endpoints, SQL writes and frontend rendering are real; this does not measure semantic embedding quality, real login/OAuth consent, email delivery, calendar synchronization or model accuracy. Existing API/SQL regressions cover folder/tag/date cohort isolation and email-ingestion adapters using mocked provider responses, without paid AI.

Source syntax, frontend regressions and a secret scan gate publication. The production-runtime backend suite and a verified database backup/restore gate the code-only SSH deployment. Actual test counts, source mapping, live asset verification and deployment outcome are recorded in GitHub PR #1. Existing dependency deprecation warnings are not hidden or treated as provider acceptance.

## Repeat The Checks

Use the generated Tailwind asset and an isolated Playwright installation. Run `node tests/ui_preview.cjs`, then pass its loopback URL to `node tests/visual_remaining_pages.cjs <fixture-url>`. The other visual suite starts and stops its own fixture server. Set `UI_BROWSER_CHANNEL=chrome` to use installed Chrome in a fresh test context.

The full browser/backend case is deliberately opt-in rather than silently skipped by ordinary CI. Run `pytest tests/browser_application_flow.py -q` only with `SMARTHR_TEST_DATABASE_URL` pointing to a dedicated loopback database named `qa` or `smarthr_qa`, with pgvector enabled, local-mode test environment variables, Playwright/Node dependencies and the generated CSS available. Do not point test fixtures at production.
