# UI Refinements: v2026.11.13.2

## Changes

- Job-page headers adapt to the available workspace width, including the administration sidebar.
- All job-page actions remain visible on narrow screens. Applicant tables reserve room for names, contact details and actions, and become labeled layouts when space is limited.
- Job-page dropdowns match the surrounding fields. Banner color and checkbox controls keep their intended dimensions.
- Screening questions use wrapping editors with the existing character limits, duplicate validation, human review and question-count rules.
- Upload-tab icons inherit their text color for consistent contrast.
- Correcting either pay-range boundary or supplying compensation clears obsolete validation messages.
- Providing a resume link clears the previous missing-CV error before browser validation. Unsupported files and files larger than the existing 10 MB limit are rejected before upload.
- Pending job saves and candidate submissions reject duplicate submit events. Job dialogs cannot be dismissed during a save; failed requests retain entered details and focus the error.
- The applicant-load error screen has a functioning return button. Closing applications now reports the correct status.

## Verification

- 22 frontend DOM regression suites passed, including new pending-save and failed-submission recovery tests.
- Playwright checks passed at 1440x900, 1280x720, 900x768, 600x800, 390x844 and 320x568.
- Browser checks cover job lists, applicant lists, scrollable job dialogs, question review, bulk-upload controls, connected-mailbox import controls, the CV library, folder/tag/date selection, and candidate submission failure/retry/success.
- Browser-native checks verify that correcting a pay range or adding a resume link unblocks validation. Screenshots are local, ignored artifacts rather than published candidate data.
- All browser actions use fictional local fixtures. AI question suggestions and application submissions are intercepted locally. No real email, calendar, mailbox-import or paid-AI action is performed.

## Deployment And Boundaries

This source version is intended for a code-only SSH deployment to the existing SmartHR VPS, after isolated production-runtime regression and database backup/restore gates pass. The GitHub PR records the actual deployment result and source revision.

The existing top-left logo, brand assets, search scope, ranking, scorecards, backend APIs and database schema are unchanged. These checks do not certify every authenticated live flow or external provider. GitHub-hosted CI was previously blocked by the account billing lock; direct test evidence must not be described as a successful GitHub Actions run.

To repeat the visual check, generate the normal Tailwind CSS asset, install Playwright in the test environment, and run `node tests/visual_recent_changes.cjs`. Set `UI_BROWSER_CHANNEL=chrome` to use an installed Chrome in a fresh isolated context. The fixture server is stopped automatically.

## Follow-Up: v2026.11.13.3

Final screenshot review identified a clipped status label at a mid-sized desktop width. The applicant status column now reserves enough space for the longest option, while retaining the existing compact layout on smaller screens. A canvas text-measurement assertion checks every status option at all six viewport sizes, including space for padding and the dropdown arrow.
