# Outlook CV Catch-Up

The last verified mailbox scan ended on **November 11 at 11:39 a.m. IST**.
This catch-up covered November 10 at 11:39 a.m. through **November 20 at
9:31 a.m. IST**. The one-day overlap protects against missing late-visible
messages. The exact next checkpoint is `2026-11-20T04:01:03.528426Z` (exclusive
end of the completed scan, not the latest retained candidate's received date).

| Outcome | Count |
| --- | ---: |
| Received messages with attachments reviewed | 302 |
| Supported PDF/Word attachments | 305 |
| Exact file duplicates skipped | 88 |
| New CVs indexed in `Mailbox 2026` | 211 |
| Held privately for review | 6 |
| Failed attachment downloads | 0 |

The held files comprise five uncertain document types and one low-confidence
OCR result. No files were deleted. The scan followed all result pages and
excluded sent, draft, outbox, junk and deleted folders using the
[Microsoft Graph folder model](https://learn.microsoft.com/en-us/graph/api/resources/mailfolder?view=graph-rest-1.0).
Originals and bounded, cleaned email context stayed on the VPS. Processing used
the existing local embedding model and a network-disabled extraction worker.
Email context is retrieval-only; context from eight shared-message attachments
is retained for provenance but cannot influence ranking.

The batch was rehearsed on an isolated database restore before live publication.
The published transaction added the reviewed records without rewriting prior
records. Every new CV passed source hash, extracted text, vector, company scope,
email context and received-date verification. Tags were derived from source text;
171 new records have at least one recognized tag. Twenty deployed retrieval
checks covered the ten received dates and cross-company exclusion.

All **7,862** pre-existing original files matched their pre-import hashes. There
are now **8,073** indexed document records and **8,063** searchable vectors. The
`Mailbox 2026` folder contains **4,073** searchable CVs. These are document counts,
not distinct people. Health checks passed, the provider ledger did not change,
and the original logo, runtime image and matching rules were not changed.
This was a one-time catch-up, not a recurring mailbox import.
