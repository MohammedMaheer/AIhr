# SmartHR VPS — GCP-Free Local Mode

This guide explains the GCP-free local mode that lets the VPS deployment
run **without any Google Cloud APIs** (no Vertex AI, no Discovery Engine,
no GCS, no Cloud Tasks).

## What replaces what

| GCP service | Local replacement |
|-------------|-------------------|
| Vertex AI Gemini 2.5 Flash (`google.genai`, `vertexai.generative_models.GenerativeModel`) | OpenAI `gpt-4o-mini` (configurable via `OPENAI_MODEL`) |
| Vertex AI text embeddings (`vertexai.language_models.TextEmbeddingModel`) | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs locally on CPU) |
| Discovery Engine vector + keyword search (`google.cloud.discoveryengine_v1`) | `pgvector` cosine similarity over the `resume_embeddings` table |
| Google Cloud Storage (`google.cloud.storage`) | Local filesystem rooted at `/app/storage` (host: `/opt/smarthr/storage`) |
| Cloud Tasks | Already disabled in VPS deploy (`USE_CLOUD_TASKS=false`) — uses in-process dispatch |

## How it works

`AIhr/main.py` imports `vps_local` at the very top of the file, **before any
google.cloud / vertexai imports**. When `SMARTHR_LOCAL_MODE=1`, the package
installs shim modules into `sys.modules` so every subsequent `from google.cloud
import storage` (and friends) resolves to a drop-in local implementation.

Files:
- [AIhr/vps_local/__init__.py](AIhr/vps_local/__init__.py) — auto-installer; reads `SMARTHR_LOCAL_MODE`
- [AIhr/vps_local/storage_shim.py](AIhr/vps_local/storage_shim.py) — `google.cloud.storage`
- [AIhr/vps_local/genai_shim.py](AIhr/vps_local/genai_shim.py) — `google.genai`
- [AIhr/vps_local/vertexai_shim.py](AIhr/vps_local/vertexai_shim.py) — `vertexai`, `vertexai.generative_models`, `vertexai.language_models`
- [AIhr/vps_local/discovery_shim.py](AIhr/vps_local/discovery_shim.py) — `google.cloud.discoveryengine_v1`

When `SMARTHR_LOCAL_MODE` is unset (or `0`), the import is a no-op and the
real GCP libraries are used. So the same code path runs both on Cloud Run and
on the VPS.

## Cutover steps

1. **Add your OpenAI API key** to `/opt/smarthr/.env` on the VPS:
   ```bash
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini   # optional override
   SMARTHR_LOCAL_MODE=1
   ```

2. **Rebuild the image with VPS deps baked in**:
   ```bash
   cd /opt/smarthr
   docker build --build-arg INSTALL_VPS_DEPS=1 \
       -t smarthr-app:vps -f app/Dockerfile app/
   # Tag as latest so docker-compose picks it up:
   docker tag smarthr-app:vps smarthr-app:latest
   ```

3. **Apply the local-mode schema** (only first time):
   ```bash
   docker compose exec -T smarthr-postgres \
       psql -U smarthr -d recruitment < deploy/vps/schema-local-mode.sql
   ```

4. **Build embeddings** for every resume on disk (~15-30 min on CPU):
   ```bash
   docker compose exec smarthr-app \
       python /app/deploy/vps/scripts/embed-resumes.py
   ```

5. **Restart the app**:
   ```bash
   docker compose up -d smarthr-app
   docker compose logs -f smarthr-app
   ```

6. **Verify no GCP traffic leaves the box** (optional):
   ```bash
   sudo tcpdump -nn 'host 142.250.0.0/15 or host 172.217.0.0/16' &
   # exercise the app, then kill tcpdump — expect zero packets
   ```

## What works without `OPENAI_API_KEY`

If you don't set the key, the genai shim falls back to a stub that returns
empty JSON `{}` for every LLM call. The app still starts, login works,
search works (pgvector), but every feature that uses Gemini will return
empty or default values:

- HR scorecard generation → empty scorecard
- Resume analysis → empty analysis
- JD generation / refinement → empty JD
- Web search summarization → no summary

Set the key as soon as possible.

## Rollback to GCP mode

Just unset the flag and restart:
```bash
sed -i 's/^SMARTHR_LOCAL_MODE=1/SMARTHR_LOCAL_MODE=0/' /opt/smarthr/.env
docker compose up -d smarthr-app
```
The original `service-account.json` is still mounted, the original google
packages are still in the image, and main.py's behavior reverts immediately.

## Cost notes

- `gpt-4o-mini`: ~$0.15 / 1M input tokens, ~$0.60 / 1M output tokens.
  Each scorecard ≈ 5k input + 1k output ≈ $0.0014 ≈ ~700 scorecards / $1.
- `all-MiniLM-L6-v2`: free, runs on CPU. ~5-10 ms per resume after warmup.
- Embedding 4002 resumes once: ~15-30 min CPU time, $0.

## Known caveats

- **Embedding dimension mismatch**: legacy GCP code paths assume 768-dim
  Vertex AI embeddings; the local shim returns 384-dim from MiniLM, and
  the `resume_embeddings.embedding` column is `vector(384)`. If main.py
  ever dot-products a stored 768-dim vector with a fresh 384-dim query,
  it will fail — but no such code path exists today (search runs entirely
  inside the discovery_shim).
- **Cloud Tasks payload encoding**: the shim does not implement
  `google.cloud.tasks_v2`. The VPS already runs with `USE_CLOUD_TASKS=false`
  and an in-process executor, so this is fine. Don't flip that flag.
- **Signed URL TTLs**: the storage shim returns the resume's static
  `/api/download-resume` URL; there's no HMAC expiration. The app's
  auth layer still gates downloads.
