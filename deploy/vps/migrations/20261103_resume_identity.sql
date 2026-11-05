-- Execute in one transaction after setting smarthr.legacy_bucket to the verified
-- existing bucket. Rehearse on an isolated restore before production.
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS storage_bucket TEXT NOT NULL DEFAULT '';
UPDATE resume_embeddings
   SET storage_bucket = current_setting('smarthr.legacy_bucket')
 WHERE storage_bucket = '';

-- Ownership is recovered only from an unambiguous, exact bucket/path upload.
WITH ownership AS (
    SELECT e.id, MIN(u.company_id) AS company_id
      FROM resume_embeddings e
      JOIN resume_uploads u
        ON u.file_path = 'gs://' || e.storage_bucket || '/' || e.folder || '/' || e.filename
     WHERE e.company_id IS NULL AND u.company_id IS NOT NULL
     GROUP BY e.id
    HAVING COUNT(DISTINCT u.company_id) = 1
)
UPDATE resume_embeddings e SET company_id = o.company_id
  FROM ownership o WHERE e.id = o.id AND e.company_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_resume_emb_storage_identity
    ON resume_embeddings(storage_bucket, folder, filename, (COALESCE(company_id, 0)));
ALTER TABLE resume_embeddings DROP CONSTRAINT IF EXISTS resume_embeddings_filename_key;
