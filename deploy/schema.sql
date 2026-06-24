-- =============================================================================
-- SmartHR Database Schema
-- All tables required by database.py
-- Run this once on a fresh PostgreSQL database to initialize the schema.
-- =============================================================================

-- Enable UUID extension (optional, used for some primary keys)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- CORE MULTI-TENANT TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS tenant_companies (
    id                SERIAL PRIMARY KEY,
    company_name      VARCHAR(255) NOT NULL,
    company_code      VARCHAR(100) UNIQUE NOT NULL,
    subscription_plan VARCHAR(50)  DEFAULT 'basic',
    max_users         INTEGER      DEFAULT 10,
    max_resumes       INTEGER      DEFAULT 1000,
    max_searches      INTEGER      DEFAULT 10000,
    gcs_bucket_name   VARCHAR(255),
    datastore_id      VARCHAR(255),
    is_active         BOOLEAN      DEFAULT TRUE,
    created_by        INTEGER,
    created_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- USER MANAGEMENT TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255),
    user_type     VARCHAR(50)  NOT NULL CHECK (user_type IN ('super_admin', 'tenant_admin', 'tenant_user')),
    is_active     BOOLEAN      DEFAULT TRUE,
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    last_login    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_companies (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    role       VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    joined_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, company_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id            SERIAL PRIMARY KEY,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at    TIMESTAMP NOT NULL,
    ip_address    VARCHAR(50),
    user_agent    TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Now add FK for tenant_companies.created_by (after users table exists)
ALTER TABLE tenant_companies
    ADD CONSTRAINT fk_tenant_companies_created_by
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    NOT VALID;  -- NOT VALID allows seeding without circular FK issues

-- =============================================================================
-- RESUME MANAGEMENT TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS resume_uploads (
    id                  SERIAL PRIMARY KEY,
    file_name           VARCHAR(500) NOT NULL,
    file_path           TEXT NOT NULL,
    file_size           BIGINT,
    mime_type           VARCHAR(100),
    uploaded_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    company_id          INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    upload_timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SEARCH & CANDIDATE TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS search_history (
    id                   SERIAL PRIMARY KEY,
    search_query         TEXT NOT NULL,
    job_title            VARCHAR(500),
    result_count         INTEGER DEFAULT 0,
    search_timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    search_method        VARCHAR(100) DEFAULT 'hr-scorecard',
    created_by_user_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    company_id           INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_results (
    id                   SERIAL PRIMARY KEY,
    search_id            INTEGER NOT NULL REFERENCES search_history(id) ON DELETE CASCADE,
    candidate_name       VARCHAR(500),
    candidate_email      VARCHAR(255),
    candidate_phone      VARCHAR(100),
    candidate_location   VARCHAR(500),
    position_applied     VARCHAR(500),
    experience_years     INTEGER,
    match_score          NUMERIC(5, 2) DEFAULT 0,
    match_status         VARCHAR(100),
    file_path            TEXT,
    gemini_analysis      JSONB,
    hr_scorecard         JSONB,
    company_id           INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    uploaded_by_user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (search_id, file_path)
);

CREATE TABLE IF NOT EXISTS candidate_actions (
    id                SERIAL PRIMARY KEY,
    search_result_id  INTEGER NOT NULL REFERENCES search_results(id) ON DELETE CASCADE,
    candidate_name    VARCHAR(500),
    action_type       VARCHAR(100) NOT NULL CHECK (action_type IN ('shortlisted', 'rejected', 'interviewed', 'selected', 'hired')),
    action_status     BOOLEAN DEFAULT TRUE,
    comments          TEXT,
    user_id           VARCHAR(100),   -- stored as string for flexibility
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- INTERVIEW SCHEDULING TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS scheduled_interviews (
    id                SERIAL PRIMARY KEY,
    candidate_name    VARCHAR(500) NOT NULL,
    candidate_email   VARCHAR(255),
    interview_type    VARCHAR(100) NOT NULL,
    interview_date    DATE NOT NULL,
    interview_time    TIME,
    duration_minutes  INTEGER DEFAULT 60,
    location          VARCHAR(500),
    interviewer       VARCHAR(500),
    notes             TEXT,
    status            VARCHAR(50) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    created_by        VARCHAR(100),   -- stored as string for flexibility
    company_id        INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    meeting_provider  VARCHAR(40),
    meeting_join_url  TEXT,
    meeting_event_id  VARCHAR(255),
    search_result_id  INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-tenant customised email templates for shortlist / interview-invite /
-- rejection / custom communications. Rows with company_id IS NULL are
-- global defaults seeded on first run.
CREATE TABLE IF NOT EXISTS email_templates (
    id         SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    kind       VARCHAR(40) NOT NULL,
    name       VARCHAR(200) NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_email_templates_company_kind
    ON email_templates(company_id, kind);

-- Log of every candidate-facing email sent.
CREATE TABLE IF NOT EXISTS interview_emails_sent (
    id               SERIAL PRIMARY KEY,
    company_id       INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    sent_by_user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    recipient_email  VARCHAR(320) NOT NULL,
    candidate_name   VARCHAR(500),
    kind             VARCHAR(40),
    subject          TEXT,
    body             TEXT,
    provider         VARCHAR(40),
    status           VARCHAR(40) DEFAULT 'sent',
    error_message    TEXT,
    search_result_id INTEGER,
    interview_id     INTEGER REFERENCES scheduled_interviews(id) ON DELETE SET NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-user OAuth tokens (Google, Microsoft) for calendar/mail integration.
CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider      VARCHAR(40) NOT NULL,
    access_token  TEXT,
    refresh_token TEXT,
    expires_at    TIMESTAMP,
    scope         TEXT,
    email         VARCHAR(320),
    extra         JSONB,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, provider)
);

-- =============================================================================
-- BACKGROUND TASKS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS hr_scorecard_tasks (
    task_id       VARCHAR(255) PRIMARY KEY,
    query         TEXT,
    job_title     VARCHAR(500),
    result_count  INTEGER DEFAULT 0,
    user_id       VARCHAR(100),
    company_id    INTEGER REFERENCES tenant_companies(id) ON DELETE SET NULL,
    status        VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    progress      TEXT,           -- JSON string of progress steps
    error_message TEXT,
    search_id     INTEGER REFERENCES search_history(id) ON DELETE SET NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at  TIMESTAMP
);

-- =============================================================================
-- AI ANALYSIS CACHE
-- Caches per-(company_id, file_path, jd_hash) Gemini scorecards so repeated
-- tenant-scoped searches with the same job description avoid re-running the LLM.
-- A nullable jd_hash with source='migrated_legacy' is used by the legacy
-- importer to seed analyses that pre-date this app (no JD available).
-- =============================================================================

CREATE TABLE IF NOT EXISTS cached_resume_analyses (
    id              SERIAL PRIMARY KEY,
    file_path       TEXT NOT NULL,
    jd_hash         CHAR(64) NOT NULL,
    jd_summary      TEXT,
    company_id      INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
    gemini_analysis JSONB NOT NULL,
    match_score     NUMERIC(5,2),
    source          VARCHAR(40) DEFAULT 'live_gemini',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_cached_resume_analyses_tenant_file_jd
    ON cached_resume_analyses(company_id, file_path, jd_hash)
    WHERE company_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cached_resume_analyses_global_file_jd
    ON cached_resume_analyses(file_path, jd_hash)
    WHERE company_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_cached_resume_analyses_file ON cached_resume_analyses(file_path);
CREATE INDEX IF NOT EXISTS idx_cached_resume_analyses_company ON cached_resume_analyses(company_id);

-- =============================================================================
-- AUDIT LOG TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    company_id  INTEGER REFERENCES tenant_companies(id) ON DELETE SET NULL,
    action      VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100),
    entity_id   INTEGER,
    old_values  JSONB,
    new_values  JSONB,
    ip_address  VARCHAR(50),
    user_agent  TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_users_email            ON users(email);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token    ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires  ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_search_history_company ON search_history(company_id);
CREATE INDEX IF NOT EXISTS idx_search_results_search  ON search_results(search_id);
CREATE INDEX IF NOT EXISTS idx_search_results_company ON search_results(company_id);
CREATE INDEX IF NOT EXISTS idx_resume_uploads_company ON resume_uploads(company_id);
CREATE INDEX IF NOT EXISTS idx_candidate_actions_result ON candidate_actions(search_result_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_interviews_date ON scheduled_interviews(interview_date);
CREATE INDEX IF NOT EXISTS idx_hr_tasks_status        ON hr_scorecard_tasks(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user        ON audit_logs(user_id);

-- =============================================================================
-- Initial super-admin accounts must be created through a controlled
-- deployment script or the application admin flow. Do not seed default
-- credentials in schema files.
-- =============================================================================
