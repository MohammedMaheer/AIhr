-- Additive only; no existing decisions or legacy notes are rewritten.
SELECT pg_advisory_xact_lock(724106405);
CREATE TABLE IF NOT EXISTS candidate_notes (
    search_result_id INTEGER PRIMARY KEY REFERENCES search_results(id) ON DELETE CASCADE,
    comments TEXT NOT NULL DEFAULT '',
    updated_by VARCHAR(100),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_candidate_actions_result_updated
    ON candidate_actions(search_result_id, updated_at DESC, id DESC);
