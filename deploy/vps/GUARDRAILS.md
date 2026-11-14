# SmartHR Production Guardrails

These defaults target the inspected shared 2-core, 8GB VPS. They do not establish
capacity for arbitrary traffic, and must be measured before applying elsewhere.

| Service | CPU Ceiling | RAM Ceiling | PID Ceiling | Docker Logs |
| --- | ---: | ---: | ---: | --- |
| Application | 1.75 cores | 3GB | 384 | 5 x 10MB |
| PostgreSQL | 1 core | 2GB | 256 | 5 x 10MB |

Memory reservations are scheduling hints, not guaranteed allocations. The app
may use up to 1GB swap above its RAM limit; PostgreSQL swap is disabled at its
2GB RAM ceiling. Recheck memory peaks and cgroup pressure during normal usage.
Do not lower limits merely to make an idle dashboard look efficient.

## Applying Safely

`production-guardrails.yml` changes only the two named SmartHR services. Merge
only its resource/logging fields into the inspected production Compose document.
Preserve image identities, environment, networks, named volumes, bind mounts and
provider configuration. Never replace live Compose with an old repository sample.

1. Verify no queued or running search jobs and record the current Compose hash,
   image IDs, data-volume identities and unrelated container IDs/start times.
2. Stage the exact reviewed image and run production-matched regressions. Take a
   private database backup and verify its restore in an isolated database.
3. Quiesce only SmartHR. Recheck pending jobs, then record business-table
   fingerprints. Database logging changes require recreating its container;
   use the same pinned local image and existing named data volume, never a new DB.
4. Start PostgreSQL, wait for readiness, then start the reviewed app. Compare
   table fingerprints, original files, mounts, unrelated services and served
   asset/runtime hashes. Verify health checks add no AI usage.
5. On failure, restore the previous Compose file and existing images/volumes.
   A code/config rollback is not permission to restore over production data.

Do not restart the Docker daemon, globally prune resources, delete volumes,
truncate Docker JSON files, or run `docker compose down -v`.

## Local Monitoring

Install the reviewed `scripts/smarthr-monitor.py` at
`/opt/smarthr/ops/smarthr-monitor.py`, then the named service/timer units under
`/etc/systemd/system/`. The timer checks only local health/readiness, the two
SmartHR services and host disk headroom every five minutes. It never sends
emails, calls paid AI, rotates credentials or restarts services automatically.

`smarthr-monitor.py --check` prints a read-only snapshot. Timer runs save only
bounded issue codes under `/var/lib/smarthr-monitor/` and log state transitions
to the system journal. Disk use is a warning at 80% and critical at 92%.
An existing disk warning is reported honestly, not hidden by raising thresholds.

This is local visibility, not an external on-call notification system. An alert
destination and off-site backup service are deliberately not configured. Existing
nightly/local backups remain in place; off-site backup was deferred by the owner.

## Search Startup

Local search columns/indexes are prepared with a five-second lock timeout and
30-second statement timeout before ASGI startup completes. Required schema
failures prevent that app worker from claiming readiness. Optional embedding
warmup remains separate and makes no paid provider call. Retrieval itself is
read-only in both normal and similar-profile modes; existing profile/scoring
semantics are unchanged.
