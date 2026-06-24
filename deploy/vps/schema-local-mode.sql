-- pgvector tables for VPS local-mode (replaces Discovery Engine).
-- Idempotent: safe to run multiple times.

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per resume file, holding its extracted text and embedding.
-- Filename is the storage key (relative to /app/storage/resumes/<filename>).
CREATE TABLE IF NOT EXISTS resume_embeddings (
    id              SERIAL PRIMARY KEY,
    filename        TEXT NOT NULL UNIQUE,
    folder          TEXT NOT NULL DEFAULT 'legacy',  -- 'legacy' or 'resume'
    company_id      INT REFERENCES tenant_companies(id) ON DELETE CASCADE,
    file_size       INT,
    content_type    TEXT,
    extracted_text  TEXT,
    text_length     INT,
    embedding       vector(384),                     -- all-MiniLM-L6-v2
    candidate_years NUMERIC(5,2),
    candidate_location TEXT,
    candidate_languages TEXT[],
    candidate_skills TEXT[],
    profile_source TEXT,
    profile_updated_at TIMESTAMP,
    embedded_at     TIMESTAMP DEFAULT NOW(),
    embed_model     TEXT DEFAULT 'all-MiniLM-L6-v2',
    extraction_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_resume_emb_filename ON resume_embeddings(filename);
CREATE INDEX IF NOT EXISTS idx_resume_emb_company  ON resume_embeddings(company_id);
CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_years ON resume_embeddings(candidate_years);
CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_location ON resume_embeddings(candidate_location);
CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_languages ON resume_embeddings USING gin(candidate_languages);
CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_skills ON resume_embeddings USING gin(candidate_skills);
CREATE INDEX IF NOT EXISTS idx_resume_emb_text_fts
    ON resume_embeddings USING gin(to_tsvector('simple', coalesce(extracted_text, '')));
-- HNSW for fast ANN search (created after data load completes; placeholder ivfflat first)
CREATE INDEX IF NOT EXISTS idx_resume_emb_vec_hnsw
    ON resume_embeddings USING hnsw (embedding vector_cosine_ops);

-- LLM call cost tracking (replaces what GCP billing would show).
CREATE TABLE IF NOT EXISTS llm_call_log (
    id              SERIAL PRIMARY KEY,
    user_id         INT,
    operation       TEXT,
    provider        TEXT,
    model           TEXT,
    input_tokens    INT,
    output_tokens   INT,
    total_tokens    INT,
    latency_ms      INT,
    success         BOOLEAN DEFAULT true,
    error_message   TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_llm_log_user ON llm_call_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_log_op   ON llm_call_log(operation, created_at DESC);

\echo 'Schema applied. Tables created:'
\dt resume_embeddings
\dt llm_call_log
