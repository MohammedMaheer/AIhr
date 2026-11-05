-- Preserve complete meeting URLs and the API's existing 2,000-character locations.
SET LOCAL lock_timeout = '5s';
ALTER TABLE scheduled_interviews ALTER COLUMN location TYPE TEXT;
