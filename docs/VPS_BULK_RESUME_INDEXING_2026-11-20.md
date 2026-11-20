# VPS Bulk Resume Indexing

SmartHR now batches embedding inference for manual recruiter uploads on the
VPS. It saves and tracks each original as before, uses the same local text
extractor and MiniLM weights, then embeds up to eight saved CVs in one call.
The upload still returns individual storage and searchability outcomes, in
input order, after indexing and metadata work completes. Embedding failures
fall back to the one-file path. A bad file does not block other files in its
group, and a valid file with no readable text is saved but not marked indexed.

The setting is `SMARTHR_BULK_EMBED_BATCH_SIZE`, capped at eight. Default or
`1` uses the individual path. The new grouping applies only to authenticated
manual bulk uploads in local mode; it retains the existing file size, request,
quota and worker limits and caps queued file content at 16 MiB per group.
Single uploads, email imports, public job applications, ranking rules and
the UI are unchanged. Desktop offload remains disabled.

## Verification

The candidate image ran in a disposable VPS environment with real pgvector,
local storage, MiniLM and synthetic users only. The test exercised login and
authenticated multipart upload, checked original bytes and metadata, and ran
the production SQL retrieval and ranking code. No production CVs or AI
credentials were used.

| Check | Result |
| --- | --- |
| Upload through search-ready, 34 PDF and DOCX fixtures | **4.527 s** one by one vs. **3.853 s** batched, about **15% less time** (medians of three runs per mode) |
| Model calls per 34-file batch | 34 individual calls became five calls: `8, 8, 8, 8, 2` |
| Indexed uploads | **207** across six timed uploads and the forced-fallback check |
| Ranking | **12/12** comparisons retained candidate order and criteria status; score differences were at most `0.00001` and minimum paired cosine similarity was `0.99999994` |
| Scope | Strict 10-candidate search and scoped folder, tag and uploaded-date search passed |
| Failure handling | Injected group inference error recovered individually; a blank PDF remained saved but unindexed, and an invalid PDF was rejected |
| Regression checks | **1,316 passed**, five subtests passed, and the frontend folder/upload payload suite passed |

These are staged synthetic timings on the VPS, not a guarantee about real
upload bandwidth, concurrent load, or near-ties in arbitrary candidate data.

## Deployment

The tested backend patch (`60506566e278f763a742f077db2486f499c6bd52`)
is running on the VPS as `smarthr-app:bulk-embeddings-60506566e2` with batch
size eight. No migration or reindex was needed. Public health passed with
the LLM probe skipped. The logo, production CV and upload records, AI call
ledger, and 26 unrelated containers were unchanged across the switch. The
previous image and Compose definition were kept for rollback. To disable
batching without reverting code, set the app container's batch size to `1`
and recreate only SmartHR's app service.
