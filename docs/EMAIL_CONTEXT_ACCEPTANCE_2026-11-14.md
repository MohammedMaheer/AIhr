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
  context. Queries without email matches retain their previous behavior. The
  email query keeps the index eligible without the semantic ANN scope barrier;
  actual index preference remains dependent on selectivity and planner costs.
- Only messages with one collected CV can contribute contextual matching.
  Multi-CV messages remain recorded but non-searchable to avoid cross-candidate
  attribution. Email context cannot satisfy a missing required skill, city,
  experience or language, and cannot turn an unreadable file into a verified CV.
  Those CVs remain searchable by their own content.
- Results expose only an additive context-match flag, not body/sender content.
  CV snippets and full-document scorecard prompts stay CV-only, so prompt size,
  cached HR scores and scoring rules are unchanged.

## Cleanup Boundaries

The dry-run-first cleanup tool accepts only redundant source trees/archives whose
contents match their recorded source manifest. Active/mounted releases, newest
rollback sources, all backups, receipts, genuine CVs, private configuration,
Docker images/containers/volumes and unrelated applications are retained.
Unknown/modified files are a reason to skip a directory, not delete it.

## Completed Verification

- **1,243 backend tests passed independently per production-matched provider
  configuration** (`auto` and `deepseek`); five existing deprecation warnings
  remain. These suites use mocked paid providers on an isolated QA network.
- All **27 frontend DOM suites** passed. All **three isolated real-browser/API/
  worker/SQL workflows** passed again on the final source, covering scoped search,
  similar profiles and application upload/review/interview flow. No live email
  or calendar notification was sent.
- **179 focused tests** passed for context attribution, tenant/scope enforcement,
  startup and cleanup. Accuracy fixtures request ten candidates for Developer,
  Accountant and Network Engineer roles, reject wrong city/experience/skills and
  email-only claims, and retain truthful shortfalls when fewer CVs qualify.
- A real PostgreSQL EXPLAIN regression verifies that the scoped email query can
  use its partial GIN index. Cleanup's eight safety tests include a live-observed
  Docker mount-list permutation: order alone must not hide or invent a change.
- The reviewed source trees passed redacted secret scans. UI/static templates,
  original logo, strict criterion parser, HR weights and scorecard prompt/cache
  modules have no changes in this release.

### Historical Recovery

The one-time Microsoft Graph read scanned 4,916 messages and matched **all 3,862
target CVs** using recorded immutable message/attachment identities, not names or
subjects. No attachment bytes were downloaded again and no paid AI was used.

Before committing context, every targeted original matched its recorded SHA-256.
The atomic backfill changed only the two new context fields; all pre-existing
business/CV fields matched their before/after fingerprints. Normal mailbox token
refresh used the existing OAuth connection without changing provider keys.

| Association | CV Records | Use |
| --- | ---: | --- |
| Single-resume email | 3,538 | Local contextual retrieval plus existing CV search |
| Shared multi-CV email | 324 | Provenance only; ordinary CV search remains available |
| Unmatched historical target | 0 | No guessed associations |

All 3,862 persisted context digests passed independent readback validation.
Five live-record probes recovered email-only terms for application monitoring,
network security, business development, project management and data analysis
inside selected company/folder/tag/received-date scope. Shared-message retrieval
was rejected and result metadata exposed no raw body or sender.

These probes used stored vectors to isolate retrieval without loading another
model into the live container. Their final SQL/vector times were 4.83-22.04 ms;
they are not full AI scorecard searches or representative hiring-accuracy tests.

### Scope And Performance

Ten live folder/tag/date cases, repeated three times and compared with an
independent eligible-ID query, had no scope leakage or missing result within the
requested limit. The final per-case median retrieval range was **2.72-78.56 ms**.
A 32-request/four-worker probe had zero errors: **116.31 ms p50, 166.90 ms p95**,
170.94 ms maximum. These are retrieval-only measurements after context recovery,
not an end-user response-time or sustained-capacity guarantee. Query statistics
were refreshed with `ANALYZE`, without rewriting CV data.

## Deployment And Preservation

Runtime source `72259542443d7abde2df73b051b3473c108b0def` is live in immutable
image `smarthr-app:review-7225954-20261114t162800z`. Operations helper source
`a332e42` is installed with its verified digest. The final documentation-only
attestation does not alter either runtime behavior or application branding.

- Database restore and named-volume container recreation were rehearsed before
  rollout. All **23 original business-table fingerprints** and the complete
  recovered email-context fingerprint match the final staging snapshot.
- Production PostgreSQL was **not restarted**. Its container, image and data
  volume remain intact; all **22 unrelated running containers** retained IDs and
  start times. Cleanup also checked stopped-container identities and mounts.
- All **7,862 referenced original files** are present with identical complete
  before/after SHA-256 sets: **1,635,188,633 bytes** checked, none missing.
- Cleanup removed **36 verified redundant source artifacts**, reclaiming
  **776,065,024 bytes (740.11 MiB)**. All **98 retained backup files** passed hash
  preservation checks. No image, volume, receipt, private configuration, genuine
  CV or unrelated application file was removed.
- HTTPS health, protected-route rejection, security headers and deployed source/
  asset hashes passed. Deep health with `llm=true` still skipped the provider.
  Release-labeled QA containers, networks and volumes were removed.
- **Zero paid AI calls were added**; the usage-log count remains 247. Both owned
  services and the five-minute monitor are healthy. Disk use is **80.20%** and
  remains honestly flagged; backup retention and thresholds were not weakened.

## Remaining Limits

Email matching itself adds no model call or body tokens. Full HR scorecard
searches still use the configured provider under the existing cache and limits;
their total cost depends on how many CVs need analysis. No population accuracy,
full-provider acceptance, sustained load or authenticated live desktop/mobile
visual certification is claimed by the isolated fixtures above.

Context recovery covers verified 2026 mailbox imports, not arbitrary legacy
uploads whose message provenance was never retained. Shared-message bodies are
deliberately not assigned to one candidate. Broader historical association needs
source proof, not filename guessing. External paging, off-site backups, key work
and GitHub billing remediation remain outside this release's scope.
