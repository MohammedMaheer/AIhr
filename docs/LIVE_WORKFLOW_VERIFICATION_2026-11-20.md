# Live Workflow Verification

This is an evidence-only follow-up to the deployed workflow release v2026.11.20.1.
The app, logo, ranking rules, provider settings and existing business records were
not changed in this pass. Private CV, provider and backup contents are not in Git.

| Area | Verified | Limit |
| --- | --- | --- |
| Microsoft | Live delegated token refresh succeeded in memory. Identity, inbox, default calendar and Sent Items queries returned HTTP 200. Teams was supported. The previously approved branded test message was found in Sent Items. | A granted send scope and a prior sent message are not proof of new recipient delivery. No new email or calendar event was created. Google had no connected account and SMTP was not configured. |
| Integration regressions | 319 tests passed against isolated PostgreSQL and simulated providers, including import, branding, OAuth, calendar changes and delivery failures. | These tests cannot prove external email delivery or attendee notification. |
| Fresh AI scorecards | Two fictional candidates met the exact city, experience and skill requirements. The stronger evidence ranked first, 91 to 82. Three separate offline negatives failed for incorrect city, missing skill and insufficient experience. | This is a small scorecard check, not a production-wide accuracy estimate or a paid full-queue load test. No genuine CVs were included in the provider requests. |
| Live scoped retrieval | Ten folder/tag/date combinations had zero out-of-scope returns. The empty scope stayed empty. A further 32 runs at concurrency four had zero errors and 263 ms p95. | These used a stored vector and the deployed retrieval code, not live embedding or AI processing. |
| Live HTTPS | 180 read-only requests over 89.6 seconds, at about two per second, returned zero errors. Overall p95 was 101 ms; health skipped AI. | Light public traffic only. No throughput or high-concurrency SLA is established. |
| Database recovery | The newest completed nightly backup, from November 19, restored into a disposable, network-disabled PostgreSQL container. The original backup hash matched. A vector query and replay of the additive migration passed. | Approximately 29 seconds measured for this database drill, including setup and cleanup. It is not an end-to-end disaster recovery time or an off-site restore. |

The live model probe made exactly **two paid calls**, totaling 6,810 input and
3,014 output tokens (9,824 total). Provider response times were 8.48 and 5.97
seconds. These one-off probes ran outside the production queue; their token
receipt is separate from the normal application ledger, which remained unchanged.

The live index and the restored database each contain **7,862 resume records**,
of which **7,852 have searchable vectors**. The ten unindexed PDFs are present
and match the hashes from the prior manual review: seven supporting documents,
two damaged PDFs and one low-confidence scan. They were not deleted or force
indexed. The operational actions for the last three are replacement or manual
confirmation, not more paid search calls.

## Remaining Acceptance

- Confirm a fresh branded email through recipient receipt and a controlled
  calendar create/reschedule/cancel through attendee delivery to an approved
  test mailbox. The earlier one-time permission was not reused.
- Approve an independent backup destination and restore both database and CV
  files there. Do not restore or remove any shared VPS snapshot as part of this
  application-only drill.
- Run sustained load against a production-like isolated copy with agreed
  concurrency, p95 and error-rate targets before promising high-traffic capacity.
