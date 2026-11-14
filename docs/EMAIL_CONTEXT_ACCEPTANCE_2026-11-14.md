# Email Context Retrieval And Conservative Disk Cleanup

## Scope

Release v2026.11.14.8 preserves the original logo, UI layouts, CV originals,
strict CV eligibility checks, HR score weights and provider configuration.
No paid model call is needed to index or search email context. GitHub billing,
credential changes and off-site backup provisioning remain outside this work.

## Email Matching

- `services/email_context.py` normalizes bounded plain/HTML message content,
  removes common quotes, signatures, scripts and hidden content, and records
  hashed message identity, sender, received date, content digest and association.
- `main.py` passes context through the existing attachment ingestion path.
  The local index stores it atomically in separate `source_email_context` and
  `source_email_metadata` fields; original CV extraction, embeddings, profile
  fields and tags are not populated from email claims.
- `vps_local/discovery_shim.py` adds a partial full-text index and bounded
  supplemental retrieval with the same company/folder/tag/date scope. Original
  retrieval weights are retained; lexical evidence can include eligible message
  context. Queries without email matches retain their previous behavior.
- Only messages with one collected CV can contribute contextual matching.
  Multi-CV messages remain recorded but non-searchable to avoid cross-candidate
  attribution. Email context cannot satisfy a missing required skill, city,
  experience or language, and cannot turn an unreadable file into a verified CV.
- Results expose only an additive context-match flag, not body/sender content.
  CV snippets and full-document scorecard prompts stay CV-only, so prompt size,
  cached HR scores and scoring rules are unchanged.

## Cleanup Boundaries

The dry-run-first cleanup tool accepts only redundant source trees/archives whose
contents match their recorded source manifest. Active/mounted releases, newest
rollback sources, all backups, receipts, genuine CVs, private configuration,
Docker images/containers/volumes and unrelated applications are retained.
Unknown/modified files are a reason to skip a directory, not delete it.

## Verification Checkpoint

Focused regression fixtures cover quoted/shared contexts, source integrity,
three roles with ten exact candidates, wrong city/years/skills, truthful result
shortfalls, original folder/tag/date boundaries and full-CV-only scorecard input.
All external AI is mocked in these fixtures. Cleanup fixtures check tampering,
mount protection and preservation of genuine files/backups.

Full production-runtime suites, immutable deployment, live scoped acceptance,
historical-context recovery and actual cleanup measurements are gated separately.
Completed results will replace this checkpoint after those gates pass. No broad
population hiring-accuracy or sustained capacity certification is implied.
