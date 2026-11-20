# Recruiter CV Processing Pilot

**Decision: keep production on the VPS pipeline.** This is a developer-run,
loopback-only test for manually selected recruiter CV files. It cannot upload,
save, or index a document. There are no changes to the recruiter interface,
ranking, logo, application uploads, mailbox imports, or deployment. The regular
VPS upload remains available for every document and is still authoritative.

## Results

| Check | Result |
| --- | --- |
| Cold processing | Browser **769 ms** including runtime/model loading over loopback; isolated VPS **6.41 s** including Python model startup |
| Warm processing (median, 17 PDFs) | Browser **33.4 ms** vs isolated VPS **29.7 ms**; browser not faster |
| Browser worker reuse | Warm end-to-end median improved from **106.8 ms** to **33.4 ms**; median extraction went from **81.1 ms** to **6.8 ms** |
| Embeddings on identical text | **20/20** probes passed; minimum cosine similarity > **0.999999**. Includes Unicode and the 256-token truncation boundary |
| PDF extraction parity | **17/18** exact text matches. The two-column fixture was read in a different order; its end-to-end vector similarity was **0.98314** |
| Ranking on synthetic pool | **6/6** queries had identical ordered candidate IDs and criteria statuses, including **10/10 exact matches** on the strict full-stack query |
| Fallbacks | **7/7** input cases routed back to regular upload; the file picker also recovered after a simulated model-load failure at a **412 px** mobile viewport |
| Data and cost | Synthetic files only in automated checks. Browser made same-origin GETs only. **Zero paid AI calls** |

The browser test used desktop Chrome on Windows with one WASM thread. The
VPS reference used the deployed SmartHR image in a one-CPU, network-disabled,
disposable container with only the model cache mounted read-only. The benchmark
uses the production CV extractor, query embedder and `_rank_rows` on a fixed,
exhaustive candidate pool with cosine scores. It does **not** cover database
retrieval, lexical scoring, scorecards, tenant filters or production latency.
The VPS normally keeps the model warm: the cold figures are startup costs, not
an expected time saving. The first browser run needs a **90.4 MB** model plus
the WASM runtime; loopback does not represent that download over the internet.
Mobile viewport checks are not device benchmarks.

## Run Locally

From `tests/local-upload-pilot` with Node.js 22+ and Chrome installed:

```sh
npm ci --ignore-scripts
npm run prepare-assets
npm test
npm start
```

Open `http://127.0.0.1:8765`. Use synthetic or approved test PDFs. The pilot
supports text-bearing PDF files up to 10 MiB and 20 pages. Unsupported formats,
unreadable PDFs, model failures and timeouts tell the recruiter to use the
regular upload. Model download is a separate setup command; it uses the
[pinned MiniLM revision](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/tree/1110a243fdf4706b3f48f1d95db1a4f5529b4d41/onnx)
and verifies SHA-256 hashes. The browser serves the model, tokenizer, PDF.js
and [single-threaded WASM runtime](https://onnxruntime.ai/docs/tutorials/web/deploy.html)
from the same loopback origin. It does not contact providers to process files.

For a VPS comparison, set `PILOT_BASELINE_SSH` to an approved SSH login and
`PILOT_BASELINE_IMAGE` to the verified running image tag already on the VPS.
Requires a preverified SSH host key and the `smarthr_stcache` volume. Run
`node verify.mjs --require-parity` to exit with code 2 if same-text vector,
PDF extraction, ranking, or a 20% warm speed improvement gate fails. The
runner sends only its built-in fixtures to the disposable container. It
never opens the production database, media store, or mailbox. Production
regression checks: upload folder/payload frontend suite and 122 profile and
search precision tests passed.

## Before Any Rollout

Keep canonical text extraction on the VPS. If the goal is reducing VPS CPU,
test embedding-only offload against server-extracted text and measure actual
end-to-end browser latency and VPS CPU under bulk load. Add low-end devices,
cold transfer conditions and a larger synthetic set covering multi-column,
multilingual, scanned and table-heavy documents. Test real database retrieval
and filtered result ordering in a disposable database. Browser output must
not write the canonical index unless the server can enforce tenant boundaries,
validate provenance and correctness, and safely fall back on failure. A file
hash, a model version claim and vector shape are not proof of correctness.
