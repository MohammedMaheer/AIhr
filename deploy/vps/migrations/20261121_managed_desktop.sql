CREATE TABLE IF NOT EXISTS managed_desktop_invites (
    digest text PRIMARY KEY,
    company_id integer NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_desktop_workers (
    id uuid PRIMARY KEY,
    company_id integer NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    name varchar(80) NOT NULL,
    credential text NOT NULL UNIQUE,
    public_key bytea NOT NULL UNIQUE,
    enabled boolean NOT NULL DEFAULT true,
    ready boolean NOT NULL DEFAULT false,
    last_seen timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS managed_desktop_jobs (
    id uuid PRIMARY KEY,
    company_id integer NOT NULL REFERENCES tenant_companies(id) ON DELETE CASCADE,
    bucket text NOT NULL,
    documents jsonb NOT NULL,
    worker_id uuid REFERENCES managed_desktop_workers(id) ON DELETE SET NULL,
    tried uuid[] NOT NULL DEFAULT '{}',
    lease_id uuid,
    lease_until timestamptz,
    expires_at timestamptz NOT NULL,
    input_digest text,
    vectors bytea,
    outcomes jsonb,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(documents)='array' AND jsonb_array_length(documents) BETWEEN 2 AND 8)
);
CREATE INDEX IF NOT EXISTS managed_desktop_open_jobs ON managed_desktop_jobs(company_id,expires_at)
    WHERE finished_at IS NULL;
CREATE INDEX IF NOT EXISTS managed_desktop_assigned_jobs ON managed_desktop_jobs(worker_id,lease_until)
    WHERE finished_at IS NULL;
