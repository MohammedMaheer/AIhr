# SmartHR VPS — Intensive Test Report

**Date:** 2026-05-08
**Target:** https://smarthr-187-127-162-233.nip.io  (Hostinger VPS 187.127.162.233)
**Parallel to:** GCP Cloud Run rev 63 — `https://smarthr-2ijwxm4iza-el.a.run.app` (untouched, still 100% traffic)

## Summary

| # | Test | Result |
|---|------|--------|
| T1 | Container & resource health | PASS |
| T2 | Database integrity | PASS |
| T3 | TLS + security headers | PASS |
| T4 | Internal endpoint ACL | PASS |
| T5 | Authentication (login + session + /api/me) | PASS |
| T6 | Static assets | PASS |
| T7 | GCP integrations (GCS, Vertex AI, Discovery Engine) | PASS |
| T8 | Authed API surface (12 endpoints) | PASS |
| T9 | HR scorecard end-to-end async pipeline | PASS |
| T10 | Backup script (manual + cron) | PASS |
| T11 | Restart resilience (app + postgres) | PASS |
| T12 | Coexistence with Leadflow tenant | PASS |
| T13 | Concurrency smoke | PASS |

## Critical fixes applied during testing

1. **DB schema mismatch** — the `migration_full_export_efforts-recruit-2026` dump turned out to be from a *different* predecessor app (Efforts Recruit), with incompatible schema (`name`/`role`/`org_id` vs the SmartHR app's `full_name`/`user_type`). Fix: exported the live GCP `smarthr-prod-2026:asia-south1:smarthr-db` via `gcloud sql export sql` → GCS → downloaded → restored on VPS. VPS now mirrors production exactly: 9 users, 4181 resumes, 63 hr_scorecard_tasks, 98 search_history.
2. **Service-account.json permission denied** — file was `0600 root:root` but container runs as `appuser` (uid 999). Fix: `chmod 644` on the SA file. Also patched `bootstrap.sh` to enforce 644 going forward.
3. **Static asset paths** — actual paths are `/static/css/style.css` (not `/static/style.css`). Documented for future health checks.

## Detailed results

### T7 — GCP integrations (proven from inside container)
```
SA env: /run/secrets/sa.json   ✅ readable
GCS bucket smarthr-prod-2026-resume-storage  ✅ exists, can list
Vertex AI text-embedding-004                 ✅ 768-dim embeddings returned
Discovery Engine (global)                    ✅ 3 datastores visible
                                                including smarthr-resume-datastore
```

### T9 — HR scorecard async (the most complex flow)

```
POST /api/hr-scorecard-search → task_id queued in local-inproc queue
Progress timeline:
  t+0s   pending → searching_candidates
  t+5s   generating_scorecards 0%
  t+20s  generating_scorecards 33%
  t+25s  generating_scorecards 66%
  t+30s  COMPLETED   (32.71s wall, 8 Gemini calls, 26 309 tokens, 0 failures)
search_id=111 persisted to DB
```

This validates: VPS-mode threading dispatch (`USE_CLOUD_TASKS=false` → daemon thread → loopback POST → ACL allow 127.0.0.1), Vertex Gemini calls, Discovery Engine retrieval, DB writes, scorecard ranking pipeline.

### T11 — Restart resilience

| Action | /health | Authed /api/me |
|--------|---------|----------------|
| restart smarthr-app | 200 | 200 (session cookie survives, sessions stored in `user_sessions`) |
| restart smarthr-postgres | 200 | transient 500 → 200 within 30s (psycopg2 pool reconnects) |

### T12 — Leadflow coexistence (no disruption verified throughout)

```
leadflow-api        Up 17 hours
leadflow-postgres   Up 42 hours (healthy)
https://leadsignai.duckdns.org/  HTTP 200
```

Separation: distinct compose project (`smarthr` vs `leadflow`), distinct docker network, distinct volumes (`smarthr_pgdata`, `smarthr_uploads`), bind on `127.0.0.1:8081` vs leadflow's `127.0.0.1:8080`, separate nginx vhost on smarthr-187-127-162-233.nip.io with own LE cert, backup cron at 04:00 vs leadflow's 03:00.

### T13 — Resource snapshot under test load

```
Disk:  11G / 96G   (12%)
RAM:   1.2G / 7.7G used,  6.5G available
10 concurrent /health: all 200, 100-150ms each
```

## Test credentials seeded (please rotate or delete)

A super_admin row was seeded for testing: `vpstest@smarthr.local` / `VpsTest!2026`.
To remove:
```bash
ssh smarthr-vps "docker exec smarthr-postgres psql -U smarthr -d recruitment -c \"DELETE FROM users WHERE email='vpstest@smarthr.local';\""
```

## Production users available on VPS (post-restore)

Existing GCP-prod users now active on VPS (use the **same passwords** as on GCP):
- `admin@yourcompany.com` (super_admin)
- `admin@maheer.tech` (tenant_admin)
- `maheer@effortz.com` (tenant_admin)
- `test-admin@test.local` (tenant_admin)
- 4 others (tenant_user / test accounts)

## Open / minor follow-ups (non-blocking)

- `/api/gcs-status` reports `credentials_found: false` because it checks the legacy `CREDENTIALS_PATH` constant rather than `GOOGLE_APPLICATION_CREDENTIALS` env var. Functionally GCS works (proven); display only.
- `/api/company-stats` and `/api/company-resource-usage` return 400 without `company_id` query param — expected for a super_admin without a default company.
- Postgres restart causes ~10s window of transient 500s on authed endpoints. Acceptable (auto-recovers); could be hardened with psycopg2 `pool_pre_ping`.

## How to re-run the suite

```powershell
powershell -ExecutionPolicy Bypass -File AIhr/deploy/vps/scripts/test-vps.ps1
powershell -ExecutionPolicy Bypass -File AIhr/deploy/vps/scripts/test-vps-2.ps1
powershell -ExecutionPolicy Bypass -File AIhr/deploy/vps/scripts/test-vps-3.ps1
```

GCS / Vertex container-side checks:
```powershell
ssh smarthr-vps "docker exec smarthr-app python /tmp/test-gcs.py"
ssh smarthr-vps "docker exec smarthr-app python /tmp/test-vertex.py"
```
