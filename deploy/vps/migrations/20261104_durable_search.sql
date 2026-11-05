-- Additive migration. Old completed/failed tasks are not re-enqueued.
SELECT pg_advisory_xact_lock(724106403);
ALTER TABLE hr_scorecard_tasks
    ADD COLUMN IF NOT EXISTS task_payload JSONB,
    ADD COLUMN IF NOT EXISTS lease_token TEXT,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_hr_tasks_queue_ready
    ON hr_scorecard_tasks(next_attempt_at, created_at)
    WHERE task_payload IS NOT NULL AND status IN ('pending', 'processing');
