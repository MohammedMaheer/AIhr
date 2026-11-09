CREATE TABLE IF NOT EXISTS resume_text_recoveries (
    resume_embedding_id INTEGER PRIMARY KEY REFERENCES resume_embeddings(id) ON DELETE CASCADE,
    source_sha256 TEXT NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    text_sha256 TEXT NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    extraction_method TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status = 'accepted'),
    details JSONB NOT NULL DEFAULT '{}',
    recovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
