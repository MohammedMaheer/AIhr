-- Additive metadata only; retain historical bookings and cancellation audit records.
SET LOCAL lock_timeout = '5s';
ALTER TABLE scheduled_interviews
    ADD COLUMN IF NOT EXISTS position TEXT,
    ADD COLUMN IF NOT EXISTS time_zone TEXT,
    ADD COLUMN IF NOT EXISTS calendar_account_id TEXT;
CREATE TABLE IF NOT EXISTS outreach_message_templates (
    id BIGSERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL, subject VARCHAR(998) NOT NULL, message TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1, deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_outreach_templates_owner
    ON outreach_message_templates(owner_id,company_id) WHERE NOT deleted;
CREATE TABLE IF NOT EXISTS interview_operations (
    operation_id TEXT PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES scheduled_interviews(id) ON DELETE RESTRICT,
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('edit','cancel')),
    state TEXT NOT NULL CHECK (state IN ('pending','unknown','failed','completed')),
    old_data JSONB NOT NULL, target_data JSONB NOT NULL, provider_before JSONB,
    error TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_interview_operation_active
    ON interview_operations(interview_id) WHERE state IN ('pending','unknown');
CREATE INDEX IF NOT EXISTS idx_interview_operation_history
    ON interview_operations(interview_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interview_owner_schedule
    ON scheduled_interviews(created_by,company_id,interview_date DESC,id DESC);
