ALTER TABLE search_history
    ADD COLUMN IF NOT EXISTS folder_filters JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS resume_filters JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE resume_embeddings
    ADD COLUMN IF NOT EXISTS search_tags TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS source_uploaded_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS source_received_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_resume_embeddings_tags ON resume_embeddings USING GIN(search_tags);
CREATE INDEX IF NOT EXISTS idx_resume_embeddings_uploaded ON resume_embeddings(company_id,source_uploaded_at);
CREATE INDEX IF NOT EXISTS idx_resume_embeddings_received ON resume_embeddings(company_id,source_received_at);
CREATE INDEX IF NOT EXISTS idx_resume_uploads_library
    ON resume_uploads(company_id,upload_timestamp DESC,id DESC);
