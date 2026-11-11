ALTER TABLE job_application_pages
    ADD COLUMN IF NOT EXISTS application_settings JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE job_applications
    ADD COLUMN IF NOT EXISTS resume_url TEXT NOT NULL DEFAULT '';

ALTER TABLE job_applications
    ADD COLUMN IF NOT EXISTS portfolio_url TEXT NOT NULL DEFAULT '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_job_applications_resume_url_length'
          AND conrelid = 'job_applications'::regclass
    ) THEN
        ALTER TABLE job_applications
            ADD CONSTRAINT chk_job_applications_resume_url_length
            CHECK (length(resume_url) <= 2048) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_job_applications_portfolio_url_length'
          AND conrelid = 'job_applications'::regclass
    ) THEN
        ALTER TABLE job_applications
            ADD CONSTRAINT chk_job_applications_portfolio_url_length
            CHECK (length(portfolio_url) <= 2048) NOT VALID;
    END IF;
END $$;

ALTER TABLE job_applications
    VALIDATE CONSTRAINT chk_job_applications_resume_url_length;
ALTER TABLE job_applications
    VALIDATE CONSTRAINT chk_job_applications_portfolio_url_length;
