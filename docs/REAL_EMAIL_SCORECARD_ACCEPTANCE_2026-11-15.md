# Real Email-Context Search And Scorecard Acceptance

## Scope

Release v2026.11.15.1 preserves the original logo, UI, strict CV eligibility,
HR score weights, provider configuration and original candidate documents.
Real-provider tests are bounded and source-reviewed; simulated tests are labeled
separately. No mailbox send, calendar invitation or CV mutation is authorized by
these search checks.

## Correction

A real-data preflight reproduced an overly restrictive email query: a message
contained the requested job title but not the full combination of city, years
and skills in the JD. Full-text matching the entire JD missed that context.

The durable HR path now passes its explicit job title to local email retrieval,
including raw-query fallback. The optimized CV query and original hard criteria
remain separate and unchanged. The message cannot establish missing skills,
location, years or languages; CV-only final verification still controls results.
Generic titles retain the original query rather than broadening retrieval.
Role context supplements the original email query; existing original-query
matches are retained even when the role words are absent from the message.

Task completion records bounded context-match/cache-hit counts for acceptance.
No raw email body is exposed or added to an AI prompt, and no UI text changes.

Real source review also found a stale indexed workplace city overriding a CV's
contact-header city. Local preselection now recognizes conservative geographic
header segments from the existing supported city map, ignores employer/project/
relocation sections, and prefers that source over contradictory indexed values.
Supplemental retrieval considers the same bounded CV header to avoid hiding
correct-city candidates. This read-time correction does not rewrite stored metadata
or original files. The existing successful-scorecard path still refreshes derived
search profiles; the full-document scorecard and strict rules remain authoritative.

## Completed Verification

- Deployed runtime source: `8a00d3adf58cd9c39437cb0a9dd9dabc2e799bce`.
- Production-matched isolated suites: **1,256 passed per provider configuration**
  (`auto` and `deepseek`), using synthetic credentials and mocked inference.
- **27 frontend suites** and **three isolated browser/API/worker workflows** passed.
  These are not authenticated live-browser or visual acceptance claims.
- A 23-table backup restore and persistent-volume recreation rehearsal passed.
  Deployment preserved business records, email context and PostgreSQL identity.
- Thirteen live durable-queue jobs completed on their first attempt. Six initial
  jobs exercised the email-role fix; seven post-deployment jobs exercised the
  final runtime. The table distinguishes fresh inference from cached assessments.

| Real Search / Control | Requested / Returned | Observed Result |
| --- | --- | --- |
| Accountant; Accounts Payable and Excel; selected folder/tag/received dates | 10 / 10 | All ten skills verified against CV text; scores 92, 92, 91, 90, 89, 89, 88, 88, 88, 86. Same membership/order on two repeats, including final runtime. |
| Monitoring engineer; Linux; 10-14 years | 10 / 1 | Role-only email context recovered. Fresh full-CV scorecard 74; repeats retained the score and truthful shortfall of nine. |
| Same monitoring criteria plus Abu Dhabi | 10 / 0 | Correctly rejected: the city occurs in project/client history, not the candidate address. Email cannot override CV eligibility. |
| Data analyst; SQL; 1-4 years; Hyderabad | 10 / 0 | Correctly rejected: Hyderabad is a workplace, while the contact header identifies Vijayawada. |
| Same data criteria with Vijayawada, final runtime | 10 / 1 | Correct-city candidate recovered; fresh full-CV scorecard 91; shortfall nine. |
| Different existing tag with no records in the selected received-day scope | 10 / 0 | No result leakage; no provider calls or tokens added. |
| Same day interpreted as upload date instead of received date | 10 / 0 | Correctly empty; no provider calls or tokens added. |
| Future received dates | 10 / 0 | Correctly empty; no provider calls or tokens added. |
| Nonexistent selected folder | 10 / 0 | Correctly empty; no provider calls or tokens added. |

Every returned item was checked for tenant, folder, tag, date basis/range, unique
CV identity, required skills, strict scorecard criteria and full-document input.
Scores were finite, descending and consistent across the result, scorecard and
candidate overview. These checks establish observed membership and consistency,
not a calibrated population-wide hiring-accuracy percentage.

## Speed And API Usage

The whole bounded real-provider session added **23 successful calls: 30,254 input
and 8,617 output tokens**, or **38,871 total**. No failed provider call was recorded.
This is measured usage, not an invoice or a general monthly-cost projection.

The ten accounting scorecards reused previously saved genuine provider assessments;
they were not ten fresh paid analyses. Their final-runtime worker duration was
2.81 seconds. A warm monitoring repeat reused its scorecard and preparation cache,
used zero new tokens, and took 0.02 seconds versus 8.86 seconds initially. After
restart, its final repeat took 2.26 seconds and 1,152 preparation tokens. Preparation
caches are process-local and expiring: do not assume every repeat is entirely free.
All durations here are worker processing time, excluding browser and queue delay.

Additional read-only, stored-vector probes passed ten folder/tag/date combinations,
including multiple-folder/tag selection and upload-versus-received dates, with no
out-of-scope rows. Thirty-two retrievals at concurrency four had zero errors and
191.08 ms p95. Five real email-only role probes recovered context, and shared-message
text was excluded from attribution. These are retrieval measurements with stored
vectors, not full AI request latency, embedding benchmarks or large-scale load tests.

## Preservation And Operations

All **7,862 referenced original files** were hash-identical before/after acceptance,
with none missing. An isolated restore of the pre-acceptance backup verified every
indexed row's immutable fields, including CV text, embedding, folder, bucket, tenant,
tags, dates and email provenance. Only two tested candidates had normal derived
profile refreshes through the pre-existing scorecard-save path. No bulk reindex,
manual candidate rewrite, mailbox send or calendar notification was performed.

After acceptance, 17 business tables were unchanged; the six expected changed
tables were scorecard tasks, search history/results, AI usage, cached analyses and
derived resume profiles. The PostgreSQL container and 22 unrelated running
containers retained their identities/start times. Temporary QA resources were removed.

Public HTTPS login, health, deep health, protected-route authentication, CSRF-aware
unauthenticated rejection and served asset/source hashes passed. Even an explicit
`llm=true` deep-health probe skipped AI; health/monitor checks added zero provider
calls. Monitoring and resource/log limits remain active. Disk usage was **80.57%**,
an existing capacity warning requiring monitoring, not a reason to delete real CVs.

## Limits

A ten-candidate request must return ten only when ten verified CVs qualify.
Otherwise a truthful shortfall is required, never a weaker scope or invented
scorecard. Bounded real examples do not establish population hiring accuracy,
sustained capacity or authenticated live browser acceptance. Shared-message
context and unknown historical associations are still deliberately excluded from
email attribution. Historical indexed facts without unambiguous CV evidence are
not certified by this bounded test. Keys, GitHub billing and off-site backup
provisioning remain outside this change. The logo, UI, HR weights and core workflow
contracts are unchanged; this is a targeted retrieval-quality correction.
