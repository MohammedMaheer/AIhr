-- Keep the questions the candidate actually answered, even after a page edit.
ALTER TABLE job_applications
    ADD COLUMN IF NOT EXISTS answer_questions JSONB NOT NULL DEFAULT '{}'::jsonb
    CHECK (jsonb_typeof(answer_questions) = 'object');
