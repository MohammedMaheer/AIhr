# Expanded Role And Desktop Acceptance

## Controlled Real Searches

Every request asks for ten candidates, within a source-reviewed folder/tag/
email-received-date cohort. Original documents and private evidence stay out of Git.

Initial runs before correcting the title metadata:

| Role And Explicit Requirement | Cohort | Returned | Shortfall | Worker Time | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| HR Recruiter: Recruitment | 10 | 10 | 0 | 29.01 s | 81,469 |
| Data Analyst: SQL and Power BI | 4 | 4 | 6 | 12.89 s | 36,297 |
| Sales Manager: Sales and CRM | 2 | 1 | 9 | 11.59 s | 8,802 |

Independently verify returned source-file membership, tenant/folder/tag/date
scope, explicit skill evidence, final strict parsed criteria, full-document
scorecard verification, unique results, finite descending scores and consistency
between database/nested/visible scores. HR scores range 92-78, analyst scores
86/73/69/66, and sales 88. No filler candidates or assessment failures occurred.

## Desktop Review And Focused Fixes

The documented CDP screenshot capture recovered a complete 1440 x 900 desktop
image, resolving the earlier incomplete compositor capture. The original logo,
navigation, candidate list and detail-column alignment were inspected directly.
No logo, CSS, scoring/ranking/filtering or backend/API implementation changed.

Three UI/metadata issues were reproduced:

1. A repeat search displayed the previous candidate count and Export All action
   while the old results were already replaced by progress indicators.
2. Opening the sales email composer used the entire query including Required
   skills as its job title, subject and template role.
3. The title helper captured only Data from Data Analyst and treated the ui
   substring inside required/recruitment as a UI/UX fallback. That incorrect
   title was sent as request metadata and appeared in saved report labels.

Fix only those presentation states. Pending searches now show Searching... and
cannot offer stale exports; completion/failure cleanup clears the busy state.
Outreach extracts the literal role before explicit requirement labels, preserving
abbreviations and the full query. Existing manual draft protection remains.
Capture the complete role phrase and use word-bounded fallback keywords; do not
change the original criteria, semantic query, scoring formula or filter logic.
Corrected role metadata is separately retested live rather than described as a
cache-equivalent request to the old, incorrectly labeled search.

## Verification

The new loading-state regression and expanded outreach regressions passed.
The desktop/mobile browser-to-API-to-worker-to-SQL scope workflow passed using
fictional documents and provider mocks; this is separate from real AI acceptance.
All 25 frontend suites passed, including complete-title and bounded-keyword
regressions. The workflow test completed ten fictional searches at desktop and
mobile widths and passed again after the title correction.

## Final Live Acceptance

| Corrected Role Metadata | Requested | Returned | Shortfall | Worker Time | Tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| HR Recruiter | 10 | 10 | 0 | 29.18 s | 80,247 |
| Data Analyst | 10 | 4 | 6 | 12.65 s | 36,349 |
| Sales Manager | 10 | 1 | 9 | 10.45 s | 8,990 |
| Identical corrected HR repeat | 10 | 10 | 0 | 2.60 s | 1,145 |
| HR with excluded folder | 10 | 0 | 10 | Empty scope | 0 |
| HR with excluded uploaded date | 10 | 0 | 10 | Empty scope | 0 |

The corrected HR scores were 91/91/90/88/88/87/84/81/76/68, analyst scores
87/73/72/66 and sales 89. Source membership and strict criteria passed for each
result. Changing incorrect metadata intentionally regenerated assessments; the
old scores are not treated as cache-equivalent. The identical corrected HR
repeat then reused all ten scorecards with the exact same files, order and
scores, using about 98.6% fewer measured tokens. No retries/provider failures
occurred in these nine real submissions. The two empty scopes made no AI calls.
Ten additional read-only stored-vector scope probes passed, including tags,
multiple folders/tags and received/uploaded-date boundaries; these exclude
query embedding and AI latency and made no paid calls.

The live pending header showed Searching..., aria-busy true and no stale export
button. Completed results restored their count/export; excluded scopes showed
0 results without exports or a leftover list spinner. Both email and interview
job titles were HR Recruiter; email subject was the clean role plus Efforts
Solutions. The branded preview visibly loaded the existing Efforts Solutions
logo. Preview only: no email was sent and no meeting created.

Desktop pixels were inspected at 1440 x 900 for dashboard, upload, Outlook import,
CV library/PDF preview, applications/create-page dialog/question controls,
reports, JD builder, administration companies/users, settings and recruiter
dialogs. The compact 1280 x 800 search also had no horizontal overflow. Only the
three reproduced issues were changed. Test scope was cleared, the query left
empty, count restored to ten and the viewport override reset afterward.

## Deployment And Budget

Final deployed source: `1d881e2143d9d7137c5ed29a569c66b8a68a12d2`;
tree: `03d0e5b5ee91a858bc1fbccc3ce3597440354ed1`;
image: `smarthr-app:review-1d881e2-20261114t064942z`.
The first UI-only step was deployed as `cabcc7f` before the additional metadata
finding; this final image includes both. Documentation attestation does not
modify that tested runtime code.

All 1,152 backend tests passed independently in each production-runtime provider
configuration. Backup/restore and restart preserved all 23 business-table
fingerprints; unrelated applications were unchanged. Sixteen reviewed source CV
hashes were identical before/after QA. HTTPS health/login returned 200 and
anonymous protected APIs 401. Runtime/static hashes matched, no QA containers
remained and health/deep-health checks added no AI calls.

This round recorded 74 successful provider calls, 190,768 input and 62,531 output
tokens (253,299 total). Conservative peak-uncached estimate: USD 0.13227, using
USD 0.30/1.20 per million input/output tokens, not an invoice. Read-only desktop
review, preview rendering, cohort planning, automated tests, scope probes and
health checks made no paid calls. Rates:
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/).

## Boundaries

This is source-grounded sample eligibility and score-consistency acceptance,
not objective population accuracy, globally optimal ranking across unassessed
CVs or validation of predicted employment outcomes. No mail was sent, calendar
event created, applicant selected, original CV changed or candidate deleted.
Screenshot pixels can be inspected through browser control; filesystem export
from that browser runtime is denied, so no missing screenshot file is claimed.
Hosted CI remains subject to the separately reported GitHub billing lock.
