# Controlled AI Search Acceptance: v2026.11.14.2

## Observed Defect And Fix

A real signed-in search, restricted to a folder, a role tag and a single email
received day, returned zero results despite source-CV evidence for two eligible
React/Node.js candidates. The provider successfully prepared the query and
keywords; no scorecard calls were made because local preselection rejected the
canonical indexed skill `node` against the explicit requirement `Node.js`.

The fix recognizes equivalent spellings for Node.js and React in the same bounded
token pattern used by Python eligibility checks and PostgreSQL supplemental
retrieval. Local extraction of these two names uses that pattern too. Generic
multi-node networking, reactive programming, node_modules and longer similarly
named tokens remain negative examples. This is a normalization correction, not
a relaxation of required qualifications or a scoring/ranking redesign.

Fictional regressions cover aliases, versions, sentence punctuation, similarly
named nonmatches, text indexing, strict ranked retrieval and SQL/Python parity.
Existing location, experience, Boolean requirements and hard-filter tests remain
part of the complete production-dependency regression gate.

## Live Acceptance Method

The controlled test set contains only three existing CVs in one selected
folder/tag/received-day intersection. Source text is reviewed privately first.
Two CVs explicitly list React and Node.js; one also has PostgreSQL evidence, and
the other explicitly gives Abu Dhabi as its contact location. Candidate names, contact details, raw CVs and
scorecards are not published to GitHub. No candidate status, email or calendar
operation is part of this test.

The bounded test plan is:

1. Run the explicit React/Node.js and 2-4 years query for three results. Expect the
   two supported candidates, a truthful one-result shortfall and descending
   score order. Review qualifications and scorecard claims against source CVs.
2. Separately require PostgreSQL or Abu Dhabi with the original mandatory stack
   and experience range. Confirm each remaining result has document-backed
   evidence rather than padding with weaker matches.
3. Repeat the original scope to check that verified cached scorecards preserve
   the result set and ranking without fresh model calls.
4. Exercise empty folder/date/tag intersections after confirming they contain
   no indexed CVs. Confirm zero results and no unnecessary model calls.

Record actual outcomes, task timing, calls and token counts in PR #1, including
any discrepancy instead of treating this plan as a passed result. A few reviewed
CVs test important failure modes; they do not establish population-wide accuracy
or turn model-generated scores into objective hiring decisions.

## Cost And Boundaries

Use the deployed provider/model without changing prompts, full-CV inputs or
output budgets. Keep each paid search within the small verified scope, examine
usage before another run, and avoid broad exploratory paid searches. Repeat and
empty-scope checks should use the existing cache and early exit.

Observed token counts come from the application's provider usage log and each
task's tracker. A conservative estimate can use the published peak, uncached
DeepSeek Flash rates, even when actual cache/off-peak billing is cheaper. It is
not an invoice or a claim about total monthly cost. Pricing source:
[DeepSeek Models And Pricing](https://api-docs.deepseek.com/quick_start/pricing/).

The code-only deployment is gated by full runtime regressions, a source secret
scan, verified backup restore and active-task checks. Original CV bytes and
unrelated VPS apps must be preserved. Normal searches retain their ordinary
history, cache, metadata and usage records for traceability. The logo and UI,
criteria meaning, ranking weights, scoring prompts and schema are unchanged.
