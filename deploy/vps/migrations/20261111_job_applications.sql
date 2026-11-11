CREATE TABLE IF NOT EXISTS job_application_pages (
    id BIGSERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 2 AND 180),
    description TEXT NOT NULL CHECK (length(description) BETWEEN 20 AND 12000),
    location TEXT NOT NULL DEFAULT '' CHECK (length(location) <= 180),
    employment_type TEXT NOT NULL DEFAULT 'Full-time' CHECK (length(employment_type) <= 80),
    custom_questions JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(custom_questions) = 'array'),
    public_token TEXT NOT NULL UNIQUE CHECK (length(public_token) >= 32),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'paused', 'closed')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_application_pages_company_updated
    ON job_application_pages(company_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_application_pages_public
    ON job_application_pages(public_token, status);

CREATE TABLE IF NOT EXISTS job_applications (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT NOT NULL REFERENCES job_application_pages(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    resume_upload_id INTEGER REFERENCES resume_uploads(id) ON DELETE SET NULL,
    vector_indexed BOOLEAN NOT NULL DEFAULT FALSE,
    candidate_name TEXT NOT NULL CHECK (length(candidate_name) BETWEEN 2 AND 160),
    normalized_email TEXT NOT NULL CHECK (length(normalized_email) BETWEEN 3 AND 254),
    phone TEXT NOT NULL DEFAULT '' CHECK (length(phone) <= 40),
    location TEXT NOT NULL DEFAULT '' CHECK (length(location) <= 180),
    years_experience NUMERIC(4,1) CHECK (years_experience IS NULL OR years_experience BETWEEN 0 AND 80),
    linkedin_url TEXT NOT NULL DEFAULT '' CHECK (length(linkedin_url) <= 500),
    answers JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(answers) = 'object'),
    consent_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('processing', 'received', 'reviewing', 'shortlisted', 'rejected', 'hired', 'withdrawn', 'erased')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    erased_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_job_applications_unique_email
    ON job_applications(page_id, normalized_email) WHERE status <> 'erased';
CREATE INDEX IF NOT EXISTS idx_job_applications_company_recent
    ON job_applications(company_id, created_at DESC) WHERE status <> 'erased';
CREATE INDEX IF NOT EXISTS idx_job_applications_page_status
    ON job_applications(page_id, status, created_at DESC) WHERE status <> 'erased';
