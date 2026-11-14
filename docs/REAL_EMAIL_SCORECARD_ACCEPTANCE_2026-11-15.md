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

## Verification Checkpoint

New regressions cover long JDs with role-only email text, unchanged CV lexical
queries, original hard requirements, request propagation, input bounds and the
actual durable worker's context counter. Production-matched regressions, restore
checks, live provider searches, cache reuse and source validation gate the final
acceptance. Actual completed evidence will be recorded after those steps.

## Limits

A ten-candidate request must return ten only when ten verified CVs qualify.
Otherwise a truthful shortfall is required, never a weaker scope or invented
scorecard. Bounded real examples do not establish population hiring accuracy,
sustained capacity or authenticated live browser acceptance. Shared-message
context, unknown historical associations, keys, GitHub billing and off-site
backup provisioning remain outside this change.
