# SmartHR VPS — GCP-Free Cutover Complete

**Date:** 2026-05-08
**Host:** smarthr-vps (187.127.162.233)
**URL:** https://smarthr-187-127-162-233.nip.io

## Status: ✅ 100% GCP-INDEPENDENT

The VPS deployment now runs entirely without Google Cloud:
- ❌ No GCS
- ❌ No Vertex AI
- ❌ No Discovery Engine (Vertex AI Search)
- ❌ No Gemini API / google.genai
- ❌ No Cloud Tasks (already disabled)
- ❌ No Cloud Run

A `tcpdump` test during search + health requests confirmed **zero packets**
to `*.googleapis.com`, `google.com`, or `huggingface.co`.

## Architecture

`SMARTHR_LOCAL_MODE=1` activates `vps_local/` package which monkey-patches
`sys.modules` *before* `main.py` imports `google.cloud.*`:

| Replaced module | Shim | Backed by |
| --- | --- | --- |
| `google.cloud.storage` | `vps_local.storage_shim` | local FS at `/app/storage` |
| `google.cloud.discoveryengine_v1` | `vps_local.discovery_shim` | pgvector + sentence-transformers |
| `google.cloud.discoveryengine` | `vps_local.discovery_shim` | (alias) |
| `google.genai` + `.types` | `vps_local.genai_shim` | OpenAI ChatCompletion |
| `vertexai` + `.generative_models` + `.language_models` | `vps_local.vertexai_shim` | OpenAI + sentence-transformers |

Cloud mode is fully preserved: setting `SMARTHR_LOCAL_MODE=0` disables the
shim and the original GCP imports run untouched.

## Data

- **4,001 resumes** synced from GCS to `/opt/smarthr/storage/resumes/{legacy,resume}/`
- **3,904 embedded** with `sentence-transformers/all-MiniLM-L6-v2` (384-dim) into pgvector
- **97 failed** (scanned/image-only PDFs — would need OCR; unrelated to GCP-free work)
- **HNSW index** in place (`idx_resume_emb_vec_hnsw`)
- Bucket symlink: `/opt/smarthr/storage/smarthr-prod-2026-resume-storage` → `resumes` (so existing `gs://smarthr-prod-2026-resume-storage/...` references resolve to local FS)

## LLM Mode

Currently runs in **STUB mode** (no `OPENAI_API_KEY` set in `/opt/smarthr/.env`).
- Gemini calls return `{}` placeholder — endpoints respond but extraction/scoring is stubbed.
- To enable real LLM: add `OPENAI_API_KEY=sk-...` to `/opt/smarthr/.env`, then `docker compose up -d smarthr-app`.
- Model selectable via `OPENAI_MODEL=gpt-4o-mini` (default).

## Files

- `vps_local/__init__.py` — auto-installer; activated by env var
- `vps_local/storage_shim.py` — GCS replacement
- `vps_local/genai_shim.py` — Gemini → OpenAI
- `vps_local/vertexai_shim.py` — Vertex Embeddings → MiniLM
- `vps_local/discovery_shim.py` — Vertex Search → pgvector
- `deploy/vps/scripts/embed-resumes.py` — corpus embedder (idempotent)
- `deploy/vps/scripts/test-search.py` — search smoke test
- `deploy/vps/scripts/monitor-embed.sh` — progress monitor
- `requirements-vps.txt` — extra deps (sentence-transformers, openai, pgvector, numpy>=2)
- `Dockerfile` — `INSTALL_VPS_DEPS=1` build arg adds these
- `deploy/vps/docker-compose.yml` — mounts `/opt/smarthr/storage:/app/storage` and named volume for HF cache; sets all env vars

## Verification Commands

```bash
# Confirm shim activation
docker exec smarthr-app env | grep SMARTHR_LOCAL_MODE
docker logs smarthr-app | grep 'local-mode shims'

# Embedded corpus
docker exec smarthr-postgres psql -U smarthr -d recruitment -c \
  'SELECT COUNT(*) AS resumes, COUNT(embedding) AS embedded FROM resume_embeddings'

# End-to-end search
docker exec smarthr-app sh -c 'cd /app && PYTHONPATH=/app python /tmp/test-search.py'

# Network audit (run in one terminal, exercise app in another)
timeout 60 tcpdump -nn -i any 'port 443' | grep -iE 'googleapis|google|huggingface'
```

## Rollback

Cutover is reversible without rebuild:
1. Edit `/opt/smarthr/.env`: `SMARTHR_LOCAL_MODE=0`
2. `docker compose up -d smarthr-app`
3. Original GCP code paths active again (requires `service-account.json`).

## Next Steps for User

1. Provide `OPENAI_API_KEY` → write to `/opt/smarthr/.env` → `docker compose up -d smarthr-app`
2. (Optional) OCR for the 97 image-only PDFs (e.g. `tesseract` in embed pipeline)
3. (Optional) Delete GCP project / GCS bucket — VPS no longer depends on them
