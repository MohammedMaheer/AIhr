# SmartHR — VPS deployment (parallel to GCP)

This folder contains everything needed to run SmartHR on the Hostinger VPS
**alongside** the existing `/opt/leadflow/` stack. GCP Cloud Run revision 63
keeps serving production traffic; the VPS is a parallel, independent deployment.

## Public URL

**https://smarthr-187-127-162-233.nip.io** (Let's Encrypt cert, auto-renewed by certbot.timer)

`nip.io` is a free wildcard DNS service — `<anything>-<ip-with-dashes>.nip.io`
resolves to the embedded IP, no domain registration needed. If/when you buy a
real domain, point it at `187.127.162.233` and run:

```bash
certbot --nginx -d hr.your-domain.com
# certbot adds a new server block; old nip.io block can stay or be removed.
```

## Topology

| Resource | Existing (Leadflow) | New (SmartHR) |
|---|---|---|
| Folder | `/opt/leadflow/` | `/opt/smarthr/` |
| App container | `leadflow-api` (127.0.0.1:8080) | `smarthr-app` (127.0.0.1:8081) |
| Postgres container | `leadflow-postgres` (pgvector pg16) | `smarthr-postgres` (pg16) |
| Docker network | `leadflow_leadflow-net` | `smarthr_smarthr-net` |
| Compose project | `leadflow` | `smarthr` |
| Public access | host nginx → :80/:443 | host nginx vhost on **:8443** |
| Backups (cron) | 03:00 daily | 04:00 daily |

The two stacks share **only** the host nginx and host docker daemon — completely
isolated networks, volumes, and databases.

## Layout

```
/opt/smarthr/
├── app/                    # Synced from local AIhr/ via scripts/sync-code.sh
├── docker-compose.yml      # smarthr stack (postgres + app)
├── .env                    # Secrets — chmod 600
├── .env.example
├── secrets/
│   └── service-account.json   # GCP SA key (Vertex/Discovery/GCS)
├── nginx/
│   └── smarthr.conf        # Vhost dropped into /etc/nginx/sites-available/
├── scripts/
│   ├── bootstrap.sh        # One-time host prep (UFW, nginx, cron)
│   ├── up.sh / down.sh
│   ├── sync-code.sh        # rsync from workstation
│   ├── restore-db.sh       # Postgres dump restore
│   ├── backup.sh           # Nightly dump (called by cron)
│   └── inventory.sh        # Read-only host inventory
├── backups/                # Nightly dumps land here
├── db-init/                # One-shot SQL on first postgres start
└── migration/              # Place latest.sql.gz here for restore
```

## First-time bring-up

From the workstation (Windows PowerShell, with `ssh smarthr-vps` alias configured):

```powershell
# 1. Sync the deploy folder + app code
ssh smarthr-vps 'mkdir -p /opt/smarthr/{secrets,backups,migration,db-init}'
scp -r deploy/vps/* smarthr-vps:/opt/smarthr/
scp service-account.json smarthr-vps:/opt/smarthr/secrets/
scp ../migration_full_export_efforts-recruit-2026_20260430_222335/db/latest.sql.gz `
    smarthr-vps:/opt/smarthr/migration/
bash deploy/vps/scripts/sync-code.sh

# 2. On the VPS, fill in .env and run bootstrap
ssh smarthr-vps
cd /opt/smarthr
cp .env.example .env && nano .env       # fill in passwords
chmod 600 .env secrets/service-account.json
chmod +x scripts/*.sh
sudo scripts/bootstrap.sh

# 3. Restore migration data
scripts/restore-db.sh /opt/smarthr/migration/latest.sql.gz

# 4. Start the stack
scripts/up.sh

# 5. Verify
curl -i http://127.0.0.1:8081/health
curl -i http://<vps-ip>:8443/health
```

## Differences vs GCP Cloud Run

- **Postgres**: local container (data restored from migration export). GCP uses
  Cloud SQL — independent now.
- **Cloud Tasks**: disabled (`USE_CLOUD_TASKS=false`). HR-scorecard tasks are
  dispatched in-process via a localhost POST. To re-enable Cloud Tasks: point a
  domain at the VPS, terminate TLS, and set the env var back to `true`.
- **GCS / Vertex / Discovery Engine**: still used (call out to GCP via the
  service-account.json). These are managed services; not self-hosted.

## Adding a domain + TLS later

```bash
# After DNS A record points <subdomain> -> 187.127.162.233
certbot --nginx -d hr.your-domain.com
# Optionally remove the nip.io listener afterwards.
```

## Coexistence guarantee

Nothing in this folder reads or writes anything under `/opt/leadflow/`,
`/etc/nginx/sites-enabled/leadflow`, or any leadflow container/volume/network.
Bootstrap is idempotent and skips conflicting resources.
