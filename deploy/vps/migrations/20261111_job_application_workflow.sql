ALTER TABLE scheduled_interviews
    ADD COLUMN IF NOT EXISTS job_application_id BIGINT;

ALTER TABLE interview_emails_sent
    ADD COLUMN IF NOT EXISTS job_application_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_scheduled_interviews_job_application'
          AND conrelid = 'scheduled_interviews'::regclass
    ) THEN
        ALTER TABLE scheduled_interviews
            ADD CONSTRAINT fk_scheduled_interviews_job_application
            FOREIGN KEY (job_application_id) REFERENCES job_applications(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_interview_emails_job_application'
          AND conrelid = 'interview_emails_sent'::regclass
    ) THEN
        ALTER TABLE interview_emails_sent
            ADD CONSTRAINT fk_interview_emails_job_application
            FOREIGN KEY (job_application_id) REFERENCES job_applications(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_scheduled_interviews_job_application
    ON scheduled_interviews(job_application_id, interview_date DESC, id DESC)
    WHERE job_application_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_interview_emails_job_application
    ON interview_emails_sent(job_application_id, created_at DESC)
    WHERE job_application_id IS NOT NULL;
