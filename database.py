"""
Database Manager Module
========================

PostgreSQL connection pool and query layer for the SmartHR platform.

Features:
    - Automatic GCP Cloud Run detection (Unix socket) vs local TCP connection
    - Connection pooling with retry logic (psycopg2 SimpleConnectionPool)
    - Multi-tenant data isolation (company_id scoping on all queries)
    - User management (bcrypt auth, session tokens, role-based access)
    - Search history, candidate results, HR scorecards (JSONB storage)
    - Interview scheduling, candidate pipeline actions, audit logging
    - Subscription limit enforcement (max users, resumes, searches per company)

Configuration:
    Reads from config.json['postgresql'] with env var overrides:
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, CLOUD_SQL_CONNECTION_NAME
"""
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2.pool import SimpleConnectionPool
import json
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging
import bcrypt
import secrets
import os
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, timedelta)):
            return obj.isoformat()
        elif hasattr(obj, 'date'):  # Handle date objects
            return obj.isoformat()
            return super().default(obj)


_LOCATION_QUALIFIER_RE = re.compile(
    r"\([^)]*(?:implied|assumed|inferred|phone|mobile|email|contact|"
    r"number|based on)[^)]*\)",
    re.IGNORECASE,
)
_LOCATION_CONTACT_RE = re.compile(
    r"\b(?:phone|mobile|email|e-mail|contact|telephone|tel|call|calls|"
    r"whatsapp|number)\b",
    re.IGNORECASE,
)
_MISSING_LOCATION_VALUES = {
    "", "n/a", "na", "none", "unknown", "not available", "not provided",
    "not specified", "not mentioned", "not disclosed",
}


def _clean_candidate_location_display(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = _LOCATION_QUALIFIER_RE.sub("", text)
    text = _LOCATION_CONTACT_RE.split(text, maxsplit=1)[0]
    text = re.split(r"[\n\r;|]", text, maxsplit=1)[0]
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    if text.lower() in _MISSING_LOCATION_VALUES:
        return None
    return text or None

class DatabaseManager:
    def __init__(self, config_path='config.json'):
        """Initialize database connection pool"""
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.db_config = config['postgresql']

        # Check if running on GCP Cloud Run
        is_gcp = self._is_running_on_gcp()

        if is_gcp:
            # Use Cloud SQL Unix socket connection for GCP
            cloud_sql_connection_name = os.getenv('CLOUD_SQL_CONNECTION_NAME',
                                                   self.db_config.get('cloud_sql_connection_name',
                                                                     'your-gcp-project-id:me-central1:your-cloudsql-instance'))
            self.db_config['host'] = f"/cloudsql/{cloud_sql_connection_name}"
            self.db_config['port'] = None  # Not needed for Unix socket
            logger.info(f"🌩️ Detected GCP environment - using Cloud SQL Unix socket: {self.db_config['host']}")
        else:
            # Override with environment variables if available (for local development)
            self.db_config['host'] = os.getenv('DB_HOST', self.db_config['host'])
            self.db_config['port'] = int(os.getenv('DB_PORT', self.db_config['port']))
            logger.info(f"🏠 Local environment - using TCP connection: {self.db_config['host']}:{self.db_config['port']}")

        # Common environment variable overrides
        self.db_config['database'] = os.getenv('DB_NAME', self.db_config['database'])
        self.db_config['user'] = os.getenv('DB_USER', self.db_config['user'])
        self.db_config['password'] = os.getenv('DB_PASSWORD', self.db_config['password'])

        self.pool = None
        self._initialize_pool()

    def _is_running_on_gcp(self):
        """Detect if running on Google Cloud Platform"""
        # Check for GCP-specific environment variables
        gcp_indicators = [
            'GOOGLE_CLOUD_PROJECT',
            'GAE_APPLICATION',
            'K_SERVICE',  # Cloud Run
            'FUNCTION_NAME',  # Cloud Functions
            'CLOUD_SQL_CONNECTION_NAME'
        ]

        for indicator in gcp_indicators:
            if os.getenv(indicator):
                logger.info(f"🌩️ GCP detected via environment variable: {indicator}")
                return True

        # Check for GCP metadata server (more reliable)
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                'http://metadata.google.internal/computeMetadata/v1/',
                headers={'Metadata-Flavor': 'Google'}
            )
            urllib.request.urlopen(req, timeout=1)
            logger.info("🌩️ GCP detected via metadata server")
            return True
        except (urllib.error.URLError, OSError, Exception):
            pass

        logger.info("🏠 Local environment detected")
        return False

    def _initialize_pool(self):
        """Create connection pool with retry logic"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to create database connection pool (attempt {attempt + 1}/{max_retries})")

                # Build connection parameters
                conn_params = {
                    'database': self.db_config['database'],
                    'user': self.db_config['user'],
                    'password': self.db_config['password'],
                    'sslmode': self.db_config.get('ssl_mode', 'require'),
                    'connect_timeout': 30
                }

                # Add host and port only if not using Unix socket
                if self.db_config['host'].startswith('/cloudsql/'):
                    # Unix socket connection for Cloud SQL
                    conn_params['host'] = self.db_config['host']
                    # Don't set port for Unix socket connections
                    logger.info(f"🔌 Using Unix socket connection: {self.db_config['host']}")
                else:
                    # TCP connection for local/external databases
                    conn_params['host'] = self.db_config['host']
                    conn_params['port'] = self.db_config['port']
                    logger.info(f"🔌 Using TCP connection: {self.db_config['host']}:{self.db_config['port']}")

                self.pool = SimpleConnectionPool(
                    1,  # minimum connections
                    self.db_config.get('pool_size', 40),  # maximum connections
                    **conn_params
                )
                logger.info("✅ Database connection pool created successfully")
                return

            except Exception as e:
                logger.error(f"❌ Error creating connection pool (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    import time
                    time.sleep(retry_delay)
                else:
                    logger.error("💥 Failed to create database connection pool after all retries")
                    raise

    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Get a database cursor from the pool"""
        conn = None
        try:
            conn = self.pool.getconn()
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor, conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                cursor.close()
                self.pool.putconn(conn)

    def check_search_limit(self, company_id):
        """Check if company can perform another search without saving anything"""
        if not company_id:
            return True  # No limits for super admin or no company context

        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT COALESCE(max_searches, 10000) as max_searches,
                       (SELECT COUNT(*) FROM search_history WHERE company_id = %s AND search_timestamp >= DATE_TRUNC('month', CURRENT_DATE)) as current_searches
                FROM tenant_companies WHERE id = %s
            """, (company_id, company_id))

            company_data = cursor.fetchone()
            if company_data:
                max_searches = company_data['max_searches'] or 10000
                current_searches = company_data['current_searches'] or 0

                if current_searches >= max_searches:
                    raise Exception(f"Company has reached maximum search limit ({max_searches} searches per month). Cannot perform new search.")

            return True

    # ------------------------------------------------------------------
    # Cached resume analyses (tenant-scoped Gemini scorecards)
    # ------------------------------------------------------------------
    _cache_table_ensured = False

    def ensure_cached_resume_analyses_table(self):
        """Create the cache table on demand (idempotent). Called lazily so
        deployments without a fresh schema.sql apply still work."""
        if DatabaseManager._cache_table_ensured:
            return
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cached_resume_analyses (
                        id              SERIAL PRIMARY KEY,
                        file_path       TEXT NOT NULL,
                        jd_hash         CHAR(64) NOT NULL,
                        jd_summary      TEXT,
                        company_id      INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
                        gemini_analysis JSONB NOT NULL,
                        match_score     NUMERIC(5,2),
                        source          VARCHAR(40) DEFAULT 'live_gemini',
                        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (file_path, jd_hash)
                    )
                """)
                cursor.execute("""
                    ALTER TABLE cached_resume_analyses
                    DROP CONSTRAINT IF EXISTS cached_resume_analyses_file_path_jd_hash_key
                """)
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_cached_resume_analyses_tenant_file_jd
                    ON cached_resume_analyses(company_id, file_path, jd_hash)
                    WHERE company_id IS NOT NULL
                """)
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_cached_resume_analyses_global_file_jd
                    ON cached_resume_analyses(file_path, jd_hash)
                    WHERE company_id IS NULL
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cached_resume_analyses_file ON cached_resume_analyses(file_path)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_cached_resume_analyses_company ON cached_resume_analyses(company_id)")
            DatabaseManager._cache_table_ensured = True
        except Exception as e:
            logger.warning(f"Could not ensure cached_resume_analyses table: {e}")

    _perf_indexes_ensured = False

    def ensure_perf_indexes(self):
        """Best-effort creation of indexes for hot read paths. Idempotent;
        only runs once per process. Failures are logged, not fatal — some
        indexes may already exist with different names from earlier
        migrations."""
        if DatabaseManager._perf_indexes_ensured:
            return
        statements = [
            "CREATE INDEX IF NOT EXISTS idx_resume_uploads_company ON resume_uploads(company_id)",
            "CREATE INDEX IF NOT EXISTS idx_resume_uploads_file_path ON resume_uploads(file_path)",
            "CREATE INDEX IF NOT EXISTS idx_resume_uploads_company_path ON resume_uploads(company_id, file_path)",
            "CREATE INDEX IF NOT EXISTS idx_search_history_company_ts ON search_history(company_id, search_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history(created_by_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_search_results_search_id ON search_results(search_id)",
            "CREATE INDEX IF NOT EXISTS idx_search_results_file_path ON search_results(file_path)",
            "CREATE INDEX IF NOT EXISTS idx_candidate_actions_search_result ON candidate_actions(search_result_id)",
            "CREATE INDEX IF NOT EXISTS idx_hr_scorecard_tasks_task_id ON hr_scorecard_tasks(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_hr_scorecard_tasks_user ON hr_scorecard_tasks(user_id)",
        ]
        for stmt in statements:
            try:
                with self.get_cursor() as (cursor, conn):
                    cursor.execute(stmt)
            except Exception as e:
                logger.warning(f"Index ensure failed (non-fatal): {stmt} — {e}")
        DatabaseManager._perf_indexes_ensured = True

    def cleanup_stale_data(self, audit_log_days: int = 180, expired_session_grace_days: int = 7):
        """Best-effort retention pruning: delete expired sessions and old audit logs.

        Idempotent and safe to call at startup. Failures are logged but never
        raised, since this is a hygiene job, not a hot path."""
        deleted_sessions = 0
        deleted_audit = 0
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "DELETE FROM user_sessions WHERE expires_at < NOW() - INTERVAL '%s days'",
                    (expired_session_grace_days,),
                )
                deleted_sessions = cursor.rowcount or 0
        except Exception as e:
            logger.warning(f"Session cleanup failed (non-fatal): {e}")
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute(
                    "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '%s days'",
                    (audit_log_days,),
                )
                deleted_audit = cursor.rowcount or 0
        except Exception as e:
            logger.warning(f"Audit log cleanup failed (non-fatal): {e}")
        if deleted_sessions or deleted_audit:
            logger.info(
                f"Retention cleanup: pruned {deleted_sessions} expired sessions, "
                f"{deleted_audit} audit log rows older than {audit_log_days} days"
            )
        return {"sessions": deleted_sessions, "audit_logs": deleted_audit}

    def get_cached_resume_analysis(self, file_path, jd_hash, company_id=None):
        """Return the cached row dict for (file_path, jd_hash) or None."""
        if not file_path or not jd_hash:
            return None
        self.ensure_cached_resume_analyses_table()
        try:
            with self.get_cursor() as (cursor, conn):
                if company_id is not None:
                    if os.getenv("ALLOW_LEGACY_GLOBAL_ANALYSIS_CACHE", "").lower() in {"1", "true", "yes"}:
                        cursor.execute("""
                            SELECT id, file_path, jd_hash, jd_summary, company_id,
                                   gemini_analysis, match_score, source, created_at
                            FROM cached_resume_analyses
                            WHERE file_path = %s
                              AND (jd_hash = %s OR jd_hash = '__legacy_no_jd__')
                              AND (company_id = %s OR company_id IS NULL)
                            ORDER BY (company_id = %s) DESC, (jd_hash = %s) DESC, created_at DESC
                            LIMIT 1
                        """, (file_path, jd_hash, company_id, company_id, jd_hash))
                    else:
                        cursor.execute("""
                            SELECT id, file_path, jd_hash, jd_summary, company_id,
                                   gemini_analysis, match_score, source, created_at
                            FROM cached_resume_analyses
                            WHERE file_path = %s
                              AND (jd_hash = %s OR jd_hash = '__legacy_no_jd__')
                              AND company_id = %s
                            ORDER BY (jd_hash = %s) DESC, created_at DESC
                            LIMIT 1
                        """, (file_path, jd_hash, company_id, jd_hash))
                else:
                    cursor.execute("""
                        SELECT id, file_path, jd_hash, jd_summary, company_id,
                               gemini_analysis, match_score, source, created_at
                        FROM cached_resume_analyses
                        WHERE file_path = %s
                          AND (jd_hash = %s OR jd_hash = '__legacy_no_jd__')
                        ORDER BY (jd_hash = %s) DESC, created_at DESC
                        LIMIT 1
                    """, (file_path, jd_hash, jd_hash))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"get_cached_resume_analysis failed for {file_path}: {e}")
            return None

    def save_cached_resume_analysis(self, file_path, jd_hash, gemini_analysis,
                                     match_score=None, jd_summary=None,
                                     company_id=None, source='live_gemini'):
        """Insert/update a cached analysis. Safe-by-default; logs on failure."""
        if not file_path or not jd_hash or not gemini_analysis:
            return False
        self.ensure_cached_resume_analyses_table()
        try:
            with self.get_cursor() as (cursor, conn):
                saved = False
                if company_id is not None:
                    cursor.execute("""
                        UPDATE cached_resume_analyses
                        SET gemini_analysis = %s,
                            match_score     = %s,
                            jd_summary      = %s,
                            source          = %s,
                            created_at      = CURRENT_TIMESTAMP
                        WHERE company_id = %s
                          AND file_path = %s
                          AND jd_hash = %s
                    """, (
                        Json(gemini_analysis), match_score, jd_summary, source,
                        company_id, file_path, jd_hash,
                    ))
                else:
                    cursor.execute("""
                        UPDATE cached_resume_analyses
                        SET gemini_analysis = %s,
                            match_score     = %s,
                            jd_summary      = %s,
                            source          = %s,
                            created_at      = CURRENT_TIMESTAMP
                        WHERE company_id IS NULL
                          AND file_path = %s
                          AND jd_hash = %s
                    """, (
                        Json(gemini_analysis), match_score, jd_summary, source,
                        file_path, jd_hash,
                    ))

                if cursor.rowcount:
                    saved = True
                else:
                    cursor.execute("""
                        INSERT INTO cached_resume_analyses
                            (file_path, jd_hash, jd_summary, company_id,
                             gemini_analysis, match_score, source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (file_path, jd_hash, jd_summary, company_id,
                          Json(gemini_analysis), match_score, source))
                    saved = True

            if saved:
                self.update_resume_search_profile_from_analysis(
                    file_path=file_path,
                    gemini_analysis=gemini_analysis,
                    source=source,
                )
            return True
        except Exception as e:
            logger.warning(f"save_cached_resume_analysis failed for {file_path}: {e}")
            return False

    def update_resume_search_profile_from_analysis(self, file_path, gemini_analysis, source='live_gemini'):
        """Refresh VPS local-mode structured search profile after a scorecard save."""
        if not file_path or not os.getenv("SMARTHR_LOCAL_MODE", "").lower() in {"1", "true", "yes", "on"}:
            return False
        try:
            from pathlib import Path
            from vps_local.profile_extractor import profile_from_analysis

            profile = profile_from_analysis(gemini_analysis)
            filename = Path(file_path).name
            rel_path = str(file_path).strip("/")
            folder = rel_path.split("/", 1)[0] if "/" in rel_path else None
            with self.get_cursor() as (cursor, conn):
                cursor.execute("SELECT to_regclass('public.resume_embeddings') AS table_name")
                exists = cursor.fetchone()
                if not exists or not exists.get('table_name'):
                    return False
                for stmt in (
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_years NUMERIC(5,2)",
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_location TEXT",
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_languages TEXT[]",
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_skills TEXT[]",
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS profile_source TEXT",
                    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS profile_updated_at TIMESTAMP",
                ):
                    cursor.execute(stmt)
                cursor.execute(
                    """
                    UPDATE resume_embeddings
                       SET candidate_years = COALESCE(%s, candidate_years),
                           candidate_location = COALESCE(NULLIF(%s, ''), candidate_location),
                           candidate_languages = CASE
                               WHEN cardinality(%s::text[]) > 0 THEN %s::text[]
                               ELSE candidate_languages
                           END,
                           candidate_skills = CASE
                               WHEN cardinality(%s::text[]) > 0 THEN %s::text[]
                               ELSE candidate_skills
                           END,
                           profile_source = %s,
                           profile_updated_at = NOW()
                     WHERE filename = %s
                        OR (folder = %s AND filename = %s)
                        OR (folder || '/' || filename) = %s
                    """,
                    (
                        profile.get("candidate_years"),
                        profile.get("candidate_location") or "",
                        profile.get("candidate_languages") or [],
                        profile.get("candidate_languages") or [],
                        profile.get("candidate_skills") or [],
                        profile.get("candidate_skills") or [],
                        f"cache:{source or 'unknown'}",
                        filename,
                        folder,
                        filename,
                        rel_path,
                    ),
                )
                return cursor.rowcount > 0
        except Exception as e:
            logger.warning(f"update_resume_search_profile_from_analysis failed for {file_path}: {e}")
            return False

    def save_search_history(self, query, job_title=None, result_count=0, user_id=None, company_id=None, search_method='hr-scorecard'):
        """Save a search to history and return the search_id"""
        with self.get_cursor() as (cursor, conn):
            # Check search limit for company if applicable
            if company_id:
                cursor.execute("""
                    SELECT COALESCE(max_searches, 10000) as max_searches,
                           (SELECT COUNT(*) FROM search_history WHERE company_id = %s AND search_timestamp >= DATE_TRUNC('month', CURRENT_DATE)) as current_searches
                    FROM tenant_companies WHERE id = %s
                """, (company_id, company_id))

                company_data = cursor.fetchone()
                if company_data:
                    max_searches = company_data['max_searches'] or 10000
                    current_searches = company_data['current_searches'] or 0

                    if current_searches >= max_searches:
                        raise Exception(f"Company has reached maximum search limit ({max_searches} searches per month). Cannot perform new search.")

            cursor.execute("""
                INSERT INTO search_history
                (search_query, job_title, result_count, created_by_user_id, company_id, search_method)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (query, job_title, result_count, user_id, company_id, search_method))

            search_id = cursor.fetchone()['id']
            return search_id

    def save_search_results(self, search_id, results, company_id=None, user_id=None):
        """Save all search results for a given search"""
        with self.get_cursor() as (cursor, conn):
            for result in results:
                # Extract data from result
                gemini_analysis = result.get('gemini_analysis', {})
                hr_scorecard = gemini_analysis.get('hr_scorecard') or gemini_analysis.get('analysis_json', {})
                candidate_overview = hr_scorecard.get('candidate_overview', {})

                # Extract years from experience string (e.g., "6 Years" -> 6)
                experience_str = candidate_overview.get('experience_years', '')
                experience_years = None
                if experience_str:
                    # Try to extract number from strings like "6 Years", "5+ years", etc.
                    match = re.search(r'(\d+)', str(experience_str))
                    if match:
                        experience_years = int(match.group(1))

                candidate_location = _clean_candidate_location_display(
                    candidate_overview.get('location')
                )
                if candidate_location:
                    candidate_overview['location'] = candidate_location

                # Prepare data for insertion
                data = {
                    'search_id': search_id,
                    'candidate_name': candidate_overview.get('name', 'Unknown'),
                    'candidate_email': candidate_overview.get('email'),
                    'candidate_phone': candidate_overview.get('phone'),
                    'candidate_location': candidate_location,
                    'position_applied': candidate_overview.get('position_applied_for'),
                    'experience_years': experience_years,  # Now an integer or None
                    'match_score': gemini_analysis.get('match_score', 0),
                    'match_status': candidate_overview.get('match_status'),
                    'file_path': result.get('file_path'),
                    'gemini_analysis': Json(gemini_analysis),
                    'hr_scorecard': Json(hr_scorecard)
                }

                # Add company_id and user_id to data
                if company_id:
                    data['company_id'] = company_id
                if user_id:
                    data['uploaded_by_user_id'] = user_id

                # Ensure keys exist for SQL parameter substitution even when
                # the caller (e.g. super_admin with no tenant company) didn't
                # provide them; otherwise psycopg2 raises KeyError on the
                # %(company_id)s / %(uploaded_by_user_id)s placeholders.
                data.setdefault('company_id', None)
                data.setdefault('uploaded_by_user_id', None)

                cursor.execute("""
                    INSERT INTO search_results
                    (search_id, candidate_name, candidate_email, candidate_phone,
                     candidate_location, position_applied, experience_years,
                     match_score, match_status, file_path, gemini_analysis, hr_scorecard,
                     company_id, uploaded_by_user_id)
                    VALUES (%(search_id)s, %(candidate_name)s, %(candidate_email)s,
                            %(candidate_phone)s, %(candidate_location)s, %(position_applied)s,
                            %(experience_years)s, %(match_score)s, %(match_status)s,
                            %(file_path)s, %(gemini_analysis)s, %(hr_scorecard)s,
                            %(company_id)s, %(uploaded_by_user_id)s)
                    ON CONFLICT (search_id, file_path) DO UPDATE SET
                        candidate_name = EXCLUDED.candidate_name,
                        candidate_email = EXCLUDED.candidate_email,
                        candidate_phone = EXCLUDED.candidate_phone,
                        candidate_location = EXCLUDED.candidate_location,
                        position_applied = EXCLUDED.position_applied,
                        experience_years = EXCLUDED.experience_years,
                        match_score = EXCLUDED.match_score,
                        match_status = EXCLUDED.match_status,
                        gemini_analysis = EXCLUDED.gemini_analysis,
                        hr_scorecard = EXCLUDED.hr_scorecard,
                        company_id = EXCLUDED.company_id,
                        uploaded_by_user_id = EXCLUDED.uploaded_by_user_id
                """, data)

    def get_search_history(self, user_id=None, company_id=None, limit=50, offset=0):
        """Get a page of search history for a user or company.

        Returns the matching rows ordered newest-first, sliced by limit/offset.
        Use ``count_search_history`` to get the total count for pagination.
        """
        with self.get_cursor() as (cursor, conn):
            # Build WHERE clause based on parameters
            where_conditions = []
            params = []

            if user_id:
                where_conditions.append("sh.created_by_user_id = %s")
                params.append(user_id)

            if company_id:
                where_conditions.append("sh.company_id = %s")
                params.append(company_id)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            params.append(int(limit))
            params.append(int(offset))

            query = f"""
                SELECT
                    sh.id,
                    sh.search_query,
                    sh.job_title,
                    sh.result_count,
                    sh.search_timestamp,
                    sh.search_method,
                    sh.created_by_user_id,
                    sh.company_id,
                    COUNT(sr.id) as actual_results,
                    ARRAY_AGG(
                        JSON_BUILD_OBJECT(
                            'name', sr.candidate_name,
                            'score', sr.match_score,
                            'role', sr.position_applied
                        ) ORDER BY sr.match_score DESC
                    ) FILTER (WHERE sr.id IS NOT NULL) as top_results
                FROM search_history sh
                LEFT JOIN search_results sr ON sh.id = sr.search_id
                {where_clause}
                GROUP BY sh.id
                ORDER BY sh.search_timestamp DESC
                LIMIT %s OFFSET %s
            """

            cursor.execute(query, params)
            return cursor.fetchall()

    def count_search_history(self, user_id=None, company_id=None):
        """Return the total number of search_history rows visible to the caller."""
        with self.get_cursor() as (cursor, conn):
            where_conditions = []
            params = []

            if user_id:
                where_conditions.append("created_by_user_id = %s")
                params.append(user_id)

            if company_id:
                where_conditions.append("company_id = %s")
                params.append(company_id)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            cursor.execute(f"SELECT COUNT(*) AS c FROM search_history {where_clause}", params)
            row = cursor.fetchone()
            if row is None:
                return 0
            # Support both dict-row and tuple-row cursors
            if isinstance(row, dict):
                return int(row.get("c", 0) or 0)
            return int(row[0] or 0)

    def get_search_results(self, search_id, company_id=None):
        """Get all results for a specific search"""
        with self.get_cursor() as (cursor, conn):
            params = [search_id]
            company_filter = ""
            if company_id is not None:
                company_filter = "AND sh.company_id = %s"
                params.append(company_id)

            cursor.execute(f"""
                SELECT
                    sr.id,
                    sr.candidate_name,
                    sr.candidate_email,
                    sr.candidate_phone,
                    sr.candidate_location,
                    sr.position_applied,
                    sr.experience_years,
                    sr.match_score,
                    sr.match_status,
                    sr.file_path,
                    sr.gemini_analysis,
                    sr.hr_scorecard,
                    sr.created_at
                FROM search_results sr
                JOIN search_history sh ON sh.id = sr.search_id
                WHERE sr.search_id = %s
                {company_filter}
                ORDER BY sr.match_score DESC
            """, params)

            return cursor.fetchall()

    def save_candidate_action(self, search_result_id, candidate_name, action_type,
                            action_status=True, comments=None, user_id=None, company_id=None):
        """Save or update HR action for a candidate.

        If company_id is provided, the search_result MUST belong to that
        company (joined via search_history). Returns False on tenant
        mismatch so the caller can 404.
        """
        with self.get_cursor() as (cursor, conn):
            # Tenant check: verify the underlying search_result belongs to
            # the caller's company before allowing any write.
            if company_id is not None:
                cursor.execute("""
                    SELECT sr.id
                    FROM search_results sr
                    JOIN search_history sh ON sh.id = sr.search_id
                    WHERE sr.id = %s AND sh.company_id = %s
                """, (search_result_id, company_id))
                if not cursor.fetchone():
                    return False

            # Check if action already exists
            cursor.execute("""
                SELECT id FROM candidate_actions
                WHERE search_result_id = %s AND action_type = %s
            """, (search_result_id, action_type))

            existing = cursor.fetchone()

            if existing:
                # Update existing action
                cursor.execute("""
                    UPDATE candidate_actions
                    SET action_status = %s, comments = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (action_status, comments, existing['id']))
            else:
                # Insert new action
                cursor.execute("""
                    INSERT INTO candidate_actions
                    (search_result_id, candidate_name, action_type, action_status, comments, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (search_result_id, candidate_name, action_type, action_status, comments, user_id))
            return True

    def get_candidate_actions(self, search_result_id):
        """Get all actions for a specific candidate"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT
                    action_type,
                    action_status,
                    comments,
                    created_at,
                    updated_at
                FROM candidate_actions
                WHERE search_result_id = %s
            """, (search_result_id,))

            return cursor.fetchall()

    def get_candidates_by_action(self, user_id, action_type, company_id=None, limit=200):
        """List candidates that the user has marked with the given action_type.

        Returns rows joined to search_results + search_history so the UI can
        render a per-status candidate list with enough context (score,
        position, source search).
        """
        with self.get_cursor() as (cursor, _conn):
            where = ("WHERE (ca.user_id = %s OR ca.user_id IS NULL) "
                     "AND LOWER(ca.action_type) = %s "
                     "AND ca.action_status = true")
            params = [str(user_id), action_type.lower()]
            if company_id:
                where += " AND sr.company_id = %s"
                params.append(int(company_id))
            cursor.execute(f"""
                SELECT
                    sr.id                AS search_result_id,
                    sr.search_id         AS search_id,
                    sr.candidate_name    AS candidate_name,
                    sr.candidate_email   AS candidate_email,
                    sr.candidate_phone   AS candidate_phone,
                    sr.candidate_location AS candidate_location,
                    sr.position_applied  AS position_applied,
                    sr.experience_years  AS experience_years,
                    sr.match_score       AS match_score,
                    sr.match_status      AS match_status,
                    sr.file_path         AS file_path,
                    ca.comments          AS comments,
                    ca.updated_at        AS actioned_at,
                    ca.created_at        AS actioned_created_at,
                    sh.search_query      AS search_query
                FROM candidate_actions ca
                JOIN search_results sr ON ca.search_result_id = sr.id
                LEFT JOIN search_history sh ON sr.search_id = sh.id
                {where}
                ORDER BY ca.updated_at DESC NULLS LAST, ca.created_at DESC
                LIMIT %s
            """, params + [int(limit)])
            return cursor.fetchall()

    def delete_search_history(self, search_id, user_id=None, company_id=None):
        """Delete a search and all its associated data.

        When `company_id` is provided, the row MUST also belong to that
        company — prevents cross-tenant deletion via guessed search_id.
        """
        with self.get_cursor() as (cursor, conn):
            clauses = ["id = %s"]
            params = [search_id]
            if user_id is not None:
                clauses.append("created_by_user_id = %s")
                params.append(user_id)
            if company_id is not None:
                clauses.append("company_id = %s")
                params.append(company_id)
            cursor.execute(
                f"DELETE FROM search_history WHERE {' AND '.join(clauses)}",
                params,
            )
            return cursor.rowcount > 0

    def delete_all_search_history_for_user(self, user_id, company_id=None):
        """Delete every search_history row owned by user_id (optionally scoped to company)."""
        with self.get_cursor() as (cursor, conn):
            if company_id is not None:
                cursor.execute(
                    "DELETE FROM search_history WHERE created_by_user_id = %s AND company_id = %s",
                    (user_id, company_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM search_history WHERE created_by_user_id = %s",
                    (user_id,),
                )
            return cursor.rowcount

    def close(self):
        """Close all connections in the pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection pool closed")

    # ============= User Management Methods =============

    def create_user(self, email, password, full_name, user_type, company_id=None, created_by=None):
        """Create a new user"""
        # Hash the password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with self.get_cursor() as (cursor, conn):
            # Check user limit for company if applicable
            if company_id and user_type in ('tenant_admin', 'tenant_user'):
                cursor.execute("""
                    SELECT max_users,
                           (SELECT COUNT(*) FROM user_companies WHERE company_id = %s) as current_users
                    FROM tenant_companies WHERE id = %s
                """, (company_id, company_id))

                company_data = cursor.fetchone()
                if company_data:
                    max_users = company_data['max_users'] or 10
                    current_users = company_data['current_users'] or 0

                    if current_users >= max_users:
                        raise Exception(f"Company has reached maximum user limit ({max_users} users). Cannot create new user.")

            # Create user
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, user_type)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (email, password_hash, full_name, user_type))

            user_id = cursor.fetchone()['id']

            # If company_id provided, link user to company
            if company_id and user_type in ('tenant_admin', 'tenant_user'):
                role = 'admin' if user_type == 'tenant_admin' else 'user'
                cursor.execute("""
                    INSERT INTO user_companies (user_id, company_id, role)
                    VALUES (%s, %s, %s)
                """, (user_id, company_id, role))

            # Log the action
            if created_by:
                self.log_audit(created_by, company_id, 'CREATE_USER', 'users', user_id,
                             None, {'email': email, 'user_type': user_type})

            return user_id

    def authenticate_user(self, email, password):
        """Authenticate a user and return user info if successful"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT id, email, password_hash, full_name, user_type, is_active
                FROM users
                WHERE email = %s
            """, (email,))

            user = cursor.fetchone()

            if not user or not user['is_active']:
                return None

            # Check password
            if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user['id'],))

                # Get user's company info if applicable
                company_info = None
                if user['user_type'] in ('tenant_admin', 'tenant_user'):
                    cursor.execute("""
                        SELECT uc.company_id, uc.role, tc.company_name, tc.company_code,
                               tc.subscription_plan, tc.max_users, tc.max_resumes,
                               COALESCE(tc.max_searches, 10000) AS max_searches,
                               tc.gcs_bucket_name, tc.datastore_id, tc.is_active
                        FROM user_companies uc
                        JOIN tenant_companies tc ON uc.company_id = tc.id
                        WHERE uc.user_id = %s AND tc.is_active = true
                    """, (user['id'],))
                    company_info = cursor.fetchone()

                return {
                    'id': user['id'],
                    'email': user['email'],
                    'full_name': user['full_name'],
                    'user_type': user['user_type'],
                    'company': company_info
                }

            return None

    def create_session(self, user_id, ip_address=None, user_agent=None):
        """Create a new session for authenticated user"""
        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)  # 7 day session

        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                INSERT INTO user_sessions (session_token, user_id, expires_at, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
            """, (session_token, user_id, expires_at, ip_address, user_agent))

            return session_token

    def verify_session(self, session_token):
        """Verify a session token and return user info if valid"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT u.id, u.email, u.full_name, u.user_type, u.is_active, s.expires_at
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.session_token = %s AND s.expires_at > CURRENT_TIMESTAMP
            """, (session_token,))

            result = cursor.fetchone()

            if result and result['is_active']:
                # Get company info if applicable
                company_info = None
                if result['user_type'] in ('tenant_admin', 'tenant_user'):
                    cursor.execute("""
                        SELECT uc.company_id, uc.role, tc.company_name, tc.company_code,
                               tc.subscription_plan, tc.max_users, tc.max_resumes,
                               COALESCE(tc.max_searches, 10000) AS max_searches,
                               tc.gcs_bucket_name, tc.datastore_id, tc.is_active
                        FROM user_companies uc
                        JOIN tenant_companies tc ON uc.company_id = tc.id
                        WHERE uc.user_id = %s AND tc.is_active = true
                    """, (result['id'],))
                    company_info = cursor.fetchone()

                return {
                    'id': result['id'],
                    'email': result['email'],
                    'full_name': result['full_name'],
                    'user_type': result['user_type'],
                    'company': company_info
                }

            return None

    def logout_user(self, session_token):
        """Logout user by deleting session"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                DELETE FROM user_sessions WHERE session_token = %s
            """, (session_token,))
            return cursor.rowcount > 0

    def create_tenant_company(self, company_name, company_code, created_by,
                            subscription_plan='basic', max_users=10, max_resumes=1000, max_searches=10000,
                            gcs_bucket_name=None, datastore_id=None):
        """Create a new tenant company with isolated resources"""
        with self.get_cursor() as (cursor, conn):
            # Try to insert with max_searches if column exists, fallback without it
            try:
                cursor.execute("""
                    INSERT INTO tenant_companies
                    (company_name, company_code, subscription_plan, max_users, max_resumes, max_searches, created_by, gcs_bucket_name, datastore_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (company_name, company_code, subscription_plan, max_users, max_resumes, max_searches, created_by, gcs_bucket_name, datastore_id))
            except Exception as e:
                # If max_searches column doesn't exist, fallback to old schema
                if "max_searches" in str(e).lower():
                    cursor.execute("""
                        INSERT INTO tenant_companies
                        (company_name, company_code, subscription_plan, max_users, max_resumes, created_by, gcs_bucket_name, datastore_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (company_name, company_code, subscription_plan, max_users, max_resumes, created_by, gcs_bucket_name, datastore_id))
                else:
                    raise e

            company_id = cursor.fetchone()['id']

            # Log the action (don't pass company_id as it references itself)
            self.log_audit(created_by, None, 'CREATE_COMPANY', 'tenant_companies', company_id,
                         None, {'company_name': company_name, 'company_code': company_code,
                                'gcs_bucket_name': gcs_bucket_name, 'datastore_id': datastore_id})

            return company_id

    def update_company_resources(self, company_id, gcs_bucket_name=None, datastore_id=None):
        """Update company with GCS bucket and datastore information"""
        with self.get_cursor() as (cursor, conn):
            # Get current values for audit
            cursor.execute("SELECT * FROM tenant_companies WHERE id = %s", (company_id,))
            old_values = dict(cursor.fetchone())

            # Build update query dynamically
            update_fields = []
            values = []

            if gcs_bucket_name is not None:
                update_fields.append("gcs_bucket_name = %s")
                values.append(gcs_bucket_name)

            if datastore_id is not None:
                update_fields.append("datastore_id = %s")
                values.append(datastore_id)

            if update_fields:
                values.append(company_id)
                query = f"UPDATE tenant_companies SET {', '.join(update_fields)} WHERE id = %s"
                cursor.execute(query, values)

                # Log the action
                new_values = {'gcs_bucket_name': gcs_bucket_name, 'datastore_id': datastore_id}
                self.log_audit(None, company_id, 'UPDATE_COMPANY_RESOURCES', 'tenant_companies', company_id,
                             old_values, new_values)

                return cursor.rowcount > 0

            return False

    def get_company_by_id(self, company_id):
        """Get company by ID with all details"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT * FROM tenant_companies WHERE id = %s
            """, (company_id,))
            return cursor.fetchone()

    def get_company_by_code(self, company_code):
        """Get company by code with all details"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT * FROM tenant_companies WHERE company_code = %s
            """, (company_code,))
            return cursor.fetchone()

    def get_all_companies(self):
        """Get all tenant companies (for super admin)"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT tc.*, u.full_name as created_by_name,
                       (SELECT COUNT(*) FROM user_companies WHERE company_id = tc.id) as user_count,
                       (SELECT COUNT(*) FROM resume_uploads WHERE company_id = tc.id) as resume_count,
                       (SELECT COUNT(*) FROM search_history WHERE company_id = tc.id) as search_count,
                       (SELECT email FROM users WHERE id = (
                           SELECT user_id FROM user_companies
                           WHERE company_id = tc.id AND role = 'admin'
                           LIMIT 1
                       )) as admin_email,
                       (SELECT full_name FROM users WHERE id = (
                           SELECT user_id FROM user_companies
                           WHERE company_id = tc.id AND role = 'admin'
                           LIMIT 1
                       )) as admin_name
                FROM tenant_companies tc
                LEFT JOIN users u ON tc.created_by = u.id
                ORDER BY tc.created_at DESC
            """)
            return cursor.fetchall()

    def get_company_users(self, company_id, limit=500, offset=0):
        """Get users in a company. Capped at `limit` (max 1000) to prevent runaway responses."""
        try:
            limit = max(1, min(int(limit), 1000))
        except (TypeError, ValueError):
            limit = 500
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT u.*, uc.role, uc.joined_at, tc.company_name, tc.company_code
                FROM users u
                JOIN user_companies uc ON u.id = uc.user_id
                JOIN tenant_companies tc ON uc.company_id = tc.id
                WHERE uc.company_id = %s
                ORDER BY uc.joined_at DESC
                LIMIT %s OFFSET %s
            """, (company_id, limit, offset))
            return cursor.fetchall()

    def update_user(self, user_id, updates, updated_by):
        """Update user information"""
        allowed_fields = ['full_name', 'email', 'is_active', 'user_type']
        update_fields = []
        values = []

        for field, value in updates.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = %s")
                values.append(value)

        if not update_fields:
            return False

        values.append(user_id)

        with self.get_cursor() as (cursor, conn):
            # Get old values for audit
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            old_values = dict(cursor.fetchone())

            # Update user
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, values)

            # Log the action
            self.log_audit(updated_by, None, 'UPDATE_USER', 'users', user_id,
                         old_values, updates)

            return cursor.rowcount > 0

    def delete_user(self, user_id, deleted_by):
        """Hard-delete a user. Cascades to user_sessions/audit_logs per FK rules;
        FK refs from other tables (companies.created_by, resume_uploads.uploaded_by,
        etc.) are ON DELETE SET NULL so historical records are preserved.

        Returns True if a row was deleted.
        """
        with self.get_cursor() as (cursor, conn):
            # Snapshot for audit trail before deletion
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cursor.fetchone()
            if not row:
                return False
            old_values = dict(row)
            # Strip password hash from audit payload
            old_values.pop('password_hash', None)

            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            deleted = cursor.rowcount > 0

            if deleted:
                # Note: audit log row's user_id FK is ON DELETE SET NULL so this
                # row survives even after the actor itself is deleted later.
                self.log_audit(deleted_by, None, 'DELETE_USER', 'users', user_id,
                               old_values, None)
            return deleted

    def log_audit(self, user_id, company_id, action, entity_type, entity_id,
                  old_values=None, new_values=None, ip_address=None, user_agent=None):
        """Log an audit entry"""
        try:
            with self.get_cursor() as (cursor, conn):
                # Convert datetime objects to strings before JSON serialization
                if old_values:
                    old_values = json.loads(json.dumps(old_values, cls=DateTimeEncoder))
                if new_values:
                    new_values = json.loads(json.dumps(new_values, cls=DateTimeEncoder))

                cursor.execute("""
                    INSERT INTO audit_logs
                    (user_id, company_id, action, entity_type, entity_id,
                     old_values, new_values, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (user_id, company_id, action, entity_type, entity_id,
                      Json(old_values) if old_values else None,
                      Json(new_values) if new_values else None,
                      ip_address, user_agent))
        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")
            # Don't raise the exception to avoid breaking the main operation

    def get_user_by_id(self, user_id):
        """Get user by ID"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT id, email, full_name, user_type, is_active, created_at, last_login
                FROM users WHERE id = %s
            """, (user_id,))
            return cursor.fetchone()

    def change_password(self, user_id, new_password):
        """Change user password"""
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                UPDATE users SET password_hash = %s WHERE id = %s
            """, (password_hash, user_id))
            return cursor.rowcount > 0

    def track_resume_upload(self, file_name, file_path, file_size, mime_type, user_id, company_id):
        """Track a resume upload (limit checking should be done before calling this method)"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                INSERT INTO resume_uploads
                (file_name, file_path, file_size, mime_type, uploaded_by_user_id, company_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (file_name, file_path, file_size, mime_type, user_id, company_id))
            return cursor.fetchone()['id']

    def get_user_uploads(self, user_id, limit=100):
        """Get uploads by a specific user"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT * FROM resume_uploads
                WHERE uploaded_by_user_id = %s
                ORDER BY upload_timestamp DESC
                LIMIT %s
            """, (user_id, limit))
            return cursor.fetchall()

    def resume_belongs_to_company(self, file_path, company_id):
        """Tenant-isolation guard for download-resume: returns True if a row
        exists in resume_uploads for the given file_path AND company_id, OR
        if the file appears as a result row in any search owned by the
        company. The second clause covers legacy rows where the upload may
        not have been tracked but a search produced a result."""
        if not file_path or company_id is None:
            return False
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT 1 FROM resume_uploads
                WHERE file_path = %s AND company_id = %s
                LIMIT 1
            """, (file_path, company_id))
            if cursor.fetchone():
                return True
            cursor.execute("""
                SELECT 1
                FROM search_results sr
                JOIN search_history sh ON sh.id = sr.search_id
                WHERE sr.file_path = %s AND sh.company_id = %s
                LIMIT 1
            """, (file_path, company_id))
            return cursor.fetchone() is not None

    def get_company_uploads(self, company_id, limit=100):
        """Get all uploads for a company"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT ru.*, u.full_name as uploaded_by_name
                FROM resume_uploads ru
                JOIN users u ON ru.uploaded_by_user_id = u.id
                WHERE ru.company_id = %s
                ORDER BY ru.upload_timestamp DESC
                LIMIT %s
            """, (company_id, limit))
            return cursor.fetchall()

    def get_all_users(self):
        """Get all users with their company info"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT
                    u.id,
                    u.email,
                    u.full_name,
                    u.user_type,
                    u.is_active,
                    u.created_at,
                    u.last_login,
                    tc.company_name,
                    tc.company_code,
                    (SELECT COUNT(*) FROM resume_uploads ru WHERE ru.uploaded_by_user_id = u.id) as resume_count
                FROM users u
                LEFT JOIN user_companies uc ON u.id = uc.user_id
                LEFT JOIN tenant_companies tc ON uc.company_id = tc.id
                ORDER BY u.created_at DESC
            """)
            return cursor.fetchall()

    def get_system_stats(self):
        """Get system-wide statistics"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM users) as total_users,
                    (SELECT COUNT(*) FROM tenant_companies) as total_companies,
                    (SELECT COUNT(*) FROM resume_uploads) as total_resumes,
                    (SELECT COUNT(*) FROM search_history) as total_searches,
                    (SELECT COUNT(*) FROM users WHERE user_type = 'super_admin') as super_admins,
                    (SELECT COUNT(*) FROM users WHERE user_type = 'tenant_admin') as tenant_admins,
                    (SELECT COUNT(*) FROM users WHERE user_type = 'tenant_user') as tenant_users,
                    (SELECT COUNT(*) FROM users WHERE last_login > NOW() - INTERVAL '7 days') as active_users_7d
            """)
            return cursor.fetchone()

    def get_company_stats(self, company_id):
        """Get company-specific statistics"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM user_companies WHERE company_id = %s) as total_users,
                    (SELECT COUNT(*) FROM resume_uploads WHERE company_id = %s) as total_resumes,
                    (SELECT COUNT(*) FROM search_history WHERE company_id = %s) as total_searches,
                    (SELECT subscription_plan FROM tenant_companies WHERE id = %s) as subscription_plan,
                    (SELECT max_users FROM tenant_companies WHERE id = %s) as max_users,
                    (SELECT max_resumes FROM tenant_companies WHERE id = %s) as max_resumes,
                    (SELECT COALESCE(max_searches, 10000) FROM tenant_companies WHERE id = %s) as max_searches
            """, (company_id, company_id, company_id, company_id, company_id, company_id, company_id))
            return cursor.fetchone()

    def get_candidate_action_stats(self, user_id, company_id=None):
        """Get candidate action statistics for dashboard"""
        with self.get_cursor() as (cursor, conn):
            # Get actions for the user's candidates - include NULL user_ids for backward compatibility
            where_clause = "WHERE (ca.user_id = %s OR ca.user_id IS NULL)"
            params = [str(user_id)]  # Ensure string type for user_id

            if company_id:
                where_clause += " AND sr.company_id = %s"
                params.append(int(company_id))  # Ensure integer type for company_id

            cursor.execute(f"""
                SELECT
                    ca.action_type,
                    COUNT(*) as count
                FROM candidate_actions ca
                JOIN search_results sr ON ca.search_result_id = sr.id
                {where_clause}
                AND ca.action_status = true
                AND ca.created_at >= NOW() - INTERVAL '30 days'
                GROUP BY ca.action_type
            """, params)

            actions = cursor.fetchall()

            # Initialize default values
            stats = {
                'rejected': 0,
                'shortlisted': 0,
                'interviewed': 0,
                'selected': 0,  # Add selected as a separate count
                'hired': 0      # Keep for backward compatibility
            }

            # Update with actual data and handle action type mapping
            for action in actions:
                action_type = action['action_type'].lower()
                if action_type in stats:
                    stats[action_type] = action['count']

            return stats

    def get_user_search_stats(self, user_id, company_id=None):
        """Get user search statistics for dashboard"""
        with self.get_cursor() as (cursor, conn):
            where_clause = "WHERE sh.created_by_user_id = %s"
            params = [user_id]

            if company_id:
                where_clause += " AND sh.company_id = %s"
                params.append(company_id)

            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_searches,
                    COUNT(CASE WHEN sh.search_timestamp >= NOW() - INTERVAL '7 days' THEN 1 END) as searches_this_week,
                    COUNT(CASE WHEN sh.search_timestamp >= NOW() - INTERVAL '30 days' THEN 1 END) as searches_this_month,
                    AVG(sh.result_count) as avg_results_per_search,
                    AVG(sr.match_score) as avg_match_score
                FROM search_history sh
                LEFT JOIN search_results sr ON sh.id = sr.search_id
                {where_clause}
            """, params)

            return cursor.fetchone()

    def get_trending_skills(self, company_id=None):
        """Get trending skills from recent searches"""
        with self.get_cursor() as (cursor, conn):
            where_clause = "WHERE sh.search_timestamp >= NOW() - INTERVAL '30 days'"
            params = []

            if company_id:
                where_clause += " AND sh.company_id = %s"
                params.append(company_id)

            cursor.execute(f"""
                SELECT
                    LOWER(TRIM(skill)) as skill,
                    COUNT(*) as frequency
                FROM (
                    SELECT UNNEST(string_to_array(
                        REGEXP_REPLACE(sh.search_query, '[^a-zA-Z0-9\\s+#.-]', ' ', 'g'),
                        ' '
                    )) as skill
                    FROM search_history sh
                    {where_clause}
                ) skills
                WHERE LENGTH(skill) > 2
                AND skill NOT IN ('and', 'the', 'for', 'with', 'developer', 'engineer', 'experience', 'years', 'senior', 'junior', 'legacy', 'import', 'general')
                GROUP BY LOWER(TRIM(skill))
                ORDER BY frequency DESC
                LIMIT 10
            """, params)

            return cursor.fetchall()

    def get_upcoming_events(self, user_id, company_id=None):
        """Get upcoming events for the user"""
        with self.get_cursor() as (cursor, conn):
            events = []

            # Get scheduled interviews first
            try:
                interview_where = "WHERE created_by = %s AND interview_date >= CURRENT_DATE AND status = 'scheduled'"
                interview_params = [str(user_id)]  # Ensure string type for user_id

                if company_id:
                    interview_where += " AND company_id = %s"
                    interview_params.append(int(company_id))  # Ensure integer type for company_id

                cursor.execute(f"""
                    SELECT
                        candidate_name,
                        interview_type,
                        interview_date,
                        interview_time,
                        location,
                        interviewer,
                        notes
                    FROM scheduled_interviews
                    {interview_where}
                    ORDER BY interview_date ASC, interview_time ASC
                    LIMIT 10
                """, interview_params)

                interviews = cursor.fetchall()

                # Add scheduled interviews to events
                for interview in interviews:
                    events.append({
                        'title': f'{interview["interview_type"].title()} with {interview["candidate_name"]}',
                        'candidate': interview['candidate_name'],
                        'type': 'interview',
                        'date': interview['interview_date'].strftime('%Y-%m-%d'),
                        'time': interview['interview_time'].strftime('%H:%M') if interview['interview_time'] else '',
                        'location': interview['location'],
                        'interviewer': interview['interviewer'],
                        'comments': interview['notes']
                    })
            except Exception as e:
                print(f"Error getting scheduled interviews: {e}")

            # Get recent candidate actions for follow-ups
            try:
                action_where = "WHERE ca.user_id = %s"
                action_params = [str(user_id)]  # Ensure string type for user_id

                if company_id:
                    action_where += " AND sr.company_id = %s"
                    action_params.append(int(company_id))  # Ensure integer type for company_id

                cursor.execute(f"""
                    SELECT
                        sr.candidate_name,
                        sr.position_applied,
                        ca.action_type,
                        ca.created_at,
                        ca.comments
                    FROM candidate_actions ca
                    JOIN search_results sr ON ca.search_result_id = sr.id
                    {action_where}
                    AND ca.action_type IN ('shortlisted', 'interviewed')
                    AND ca.created_at >= NOW() - INTERVAL '7 days'
                    ORDER BY ca.created_at DESC
                    LIMIT 5
                """, action_params)

                actions = cursor.fetchall()

                # Convert to events format
                for action in actions:
                    event_type = "Follow-up" if action['action_type'] == 'shortlisted' else "Decision"
                    events.append({
                        'title': f"{event_type}: {action['candidate_name']}",
                        'candidate': action['candidate_name'],
                        'position': action['position_applied'],
                        'type': action['action_type'],
                        'date': action['created_at'].strftime('%Y-%m-%d'),
                        'comments': action['comments']
                    })
            except Exception as e:
                print(f"Error getting candidate actions: {e}")

            return events

    # ------------------------------------------------------------------
    # Integration tables: interview meeting links, email templates,
    # email send log, OAuth tokens (per-user for Google/Microsoft).
    # ------------------------------------------------------------------
    _integrations_tables_ensured = False

    def ensure_integrations_tables(self):
        """Create/extend tables for the Teams/Meet + email integration.

        Idempotent. Safe to call on every code path that needs the data.
        """
        if DatabaseManager._integrations_tables_ensured:
            return
        try:
            with self.get_cursor() as (cursor, conn):
                # 1. Extend scheduled_interviews with meeting-link columns.
                cursor.execute("""
                    ALTER TABLE scheduled_interviews
                        ADD COLUMN IF NOT EXISTS meeting_provider   VARCHAR(40),
                        ADD COLUMN IF NOT EXISTS meeting_join_url   TEXT,
                        ADD COLUMN IF NOT EXISTS meeting_event_id   VARCHAR(255),
                        ADD COLUMN IF NOT EXISTS search_result_id   INTEGER
                """)
                # 2. Per-tenant email templates.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_templates (
                        id          SERIAL PRIMARY KEY,
                        company_id  INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
                        kind        VARCHAR(40) NOT NULL,
                        name        VARCHAR(200) NOT NULL,
                        subject     TEXT NOT NULL,
                        body        TEXT NOT NULL,
                        is_default  BOOLEAN DEFAULT FALSE,
                        created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # De-duplicate any historical rows that share (company_id, kind, name)
                # before adding the unique constraint.
                cursor.execute("""
                    DELETE FROM email_templates a USING email_templates b
                     WHERE a.id > b.id
                       AND a.kind = b.kind
                       AND a.name = b.name
                       AND a.company_id IS NOT DISTINCT FROM b.company_id
                """)
                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_email_templates_scope_name
                        ON email_templates ((COALESCE(company_id, 0)), kind, name)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email_templates_company_kind
                        ON email_templates(company_id, kind)
                """)
                # 3. Log of sent emails.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS interview_emails_sent (
                        id              SERIAL PRIMARY KEY,
                        company_id      INTEGER REFERENCES tenant_companies(id) ON DELETE CASCADE,
                        sent_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        recipient_email VARCHAR(320) NOT NULL,
                        candidate_name  VARCHAR(500),
                        kind            VARCHAR(40),
                        subject         TEXT,
                        body            TEXT,
                        provider        VARCHAR(40),
                        status          VARCHAR(40) DEFAULT 'sent',
                        error_message   TEXT,
                        search_result_id INTEGER,
                        interview_id    INTEGER REFERENCES scheduled_interviews(id) ON DELETE SET NULL,
                        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # 4. OAuth tokens for Google / Microsoft per-user.
                cursor.execute("""
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
                    )
                """)
            DatabaseManager._integrations_tables_ensured = True
            logger.info("Integration tables ensured (interviews/emails/oauth).")
        except Exception as e:
            logger.warning(f"ensure_integrations_tables failed (non-fatal): {e}")

    # -------- Email templates -----------------------------------------
    def upsert_email_template(self, company_id, kind, name, subject, body,
                              template_id=None, is_default=False, created_by=None):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            if template_id:
                cursor.execute("""
                    UPDATE email_templates
                       SET name=%s, subject=%s, body=%s, is_default=%s,
                           updated_at=CURRENT_TIMESTAMP
                     WHERE id=%s AND (company_id=%s OR (company_id IS NULL AND %s IS NULL))
                """, (name, subject, body, bool(is_default), template_id,
                      company_id, company_id))
                return template_id if cursor.rowcount else None
            cursor.execute("""
                INSERT INTO email_templates (company_id, kind, name, subject, body,
                                             is_default, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT ((COALESCE(company_id, 0)), kind, name)
                    DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (company_id, kind, name, subject, body, bool(is_default), created_by))
            return cursor.fetchone()['id']

    def list_email_templates(self, company_id, kind=None):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            params = [company_id, company_id]
            sql = """
                SELECT id, company_id, kind, name, subject, body, is_default,
                       created_at, updated_at
                  FROM email_templates
                 WHERE (company_id = %s OR (company_id IS NULL AND %s IS NULL))
            """
            if kind:
                sql += " AND kind = %s"
                params.append(kind)
            sql += " ORDER BY is_default DESC, kind, name"
            cursor.execute(sql, params)
            return cursor.fetchall()

    def get_email_template(self, template_id, company_id):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT * FROM email_templates
                 WHERE id=%s AND (company_id=%s OR (company_id IS NULL AND %s IS NULL))
            """, (template_id, company_id, company_id))
            return cursor.fetchone()

    def delete_email_template(self, template_id, company_id):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                DELETE FROM email_templates
                 WHERE id=%s AND (company_id=%s OR (company_id IS NULL AND %s IS NULL))
            """, (template_id, company_id, company_id))
            return cursor.rowcount > 0

    def log_email_sent(self, *, company_id, sent_by_user_id, recipient_email,
                       candidate_name, kind, subject, body, provider, status='sent',
                       error_message=None, search_result_id=None, interview_id=None):
        self.ensure_integrations_tables()
        try:
            with self.get_cursor() as (cursor, conn):
                cursor.execute("""
                    INSERT INTO interview_emails_sent
                        (company_id, sent_by_user_id, recipient_email, candidate_name,
                         kind, subject, body, provider, status, error_message,
                         search_result_id, interview_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (company_id, sent_by_user_id, recipient_email, candidate_name,
                      kind, subject, body, provider, status, error_message,
                      search_result_id, interview_id))
                return cursor.fetchone()['id']
        except Exception as e:
            logger.warning(f"log_email_sent failed: {e}")
            return None

    # -------- OAuth token storage -------------------------------------
    def save_oauth_token(self, user_id, provider, *, access_token, refresh_token=None,
                         expires_at=None, scope=None, email=None, extra=None):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                INSERT INTO oauth_tokens
                    (user_id, provider, access_token, refresh_token, expires_at,
                     scope, email, extra, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, provider) DO UPDATE SET
                    access_token  = EXCLUDED.access_token,
                    refresh_token = COALESCE(EXCLUDED.refresh_token, oauth_tokens.refresh_token),
                    expires_at    = EXCLUDED.expires_at,
                    scope         = COALESCE(EXCLUDED.scope, oauth_tokens.scope),
                    email         = COALESCE(EXCLUDED.email, oauth_tokens.email),
                    extra         = COALESCE(EXCLUDED.extra, oauth_tokens.extra),
                    updated_at    = CURRENT_TIMESTAMP
            """, (user_id, provider, access_token, refresh_token, expires_at,
                  scope, email, Json(extra) if extra else None))

    def get_oauth_token(self, user_id, provider):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT * FROM oauth_tokens
                 WHERE user_id=%s AND provider=%s
            """, (user_id, provider))
            return cursor.fetchone()

    def delete_oauth_token(self, user_id, provider):
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                DELETE FROM oauth_tokens WHERE user_id=%s AND provider=%s
            """, (user_id, provider))
            return cursor.rowcount > 0

    def schedule_interview(self, interview_data):
        """Schedule an interview with a candidate"""
        self.ensure_integrations_tables()
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                INSERT INTO scheduled_interviews
                (candidate_name, candidate_email, interview_type, interview_date,
                 interview_time, duration_minutes, location, interviewer, notes,
                 created_by, company_id, status,
                 meeting_provider, meeting_join_url, meeting_event_id,
                 search_result_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s)
                RETURNING id
            """, (
                interview_data['candidate_name'],
                interview_data['candidate_email'],
                interview_data['interview_type'],
                interview_data['interview_date'],
                interview_data['interview_time'],
                int(interview_data['duration']),
                interview_data['location'],
                interview_data['interviewer'],
                interview_data['notes'],
                interview_data['created_by'],
                interview_data['company_id'],
                'scheduled',
                interview_data.get('meeting_provider'),
                interview_data.get('meeting_join_url'),
                interview_data.get('meeting_event_id'),
                interview_data.get('search_result_id'),
            ))

            interview_id = cursor.fetchone()['id']

            # Log the action - ensure user_id is converted to integer if it's a string
            user_id = interview_data['created_by']
            if isinstance(user_id, str) and user_id.isdigit():
                user_id = int(user_id)
            elif isinstance(user_id, str):
                # If it's a non-numeric string, try to handle gracefully
                user_id = None

            self.log_audit(
                user_id,
                interview_data['company_id'],
                'SCHEDULE_INTERVIEW',
                'scheduled_interviews',
                interview_id,
                None,
                interview_data
            )

            return interview_id

    def get_scheduled_interviews(self, user_id=None, company_id=None, include_past=False):
        """Get scheduled interviews"""
        with self.get_cursor() as (cursor, conn):
            where_clauses = []
            params = []

            if user_id:
                where_clauses.append("created_by = %s")
                params.append(user_id)

            if company_id:
                where_clauses.append("company_id = %s")
                params.append(company_id)

            if not include_past:
                where_clauses.append("interview_date >= CURRENT_DATE")

            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            cursor.execute(f"""
                SELECT * FROM scheduled_interviews
                {where_clause}
                ORDER BY interview_date ASC, interview_time ASC
            """, params)

            return cursor.fetchall()

    def save_hr_scorecard_task(self, task_id, query, job_title, result_count, user_id,
                              company_id=None, status='pending', created_at=None):
        """Save a new HR scorecard task to the database"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                INSERT INTO hr_scorecard_tasks
                (task_id, query, job_title, result_count, user_id, company_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING task_id
            """, (
                task_id,
                query,
                job_title,
                result_count,
                str(user_id),  # Ensure user_id is string
                company_id,
                status,
                created_at or datetime.utcnow(),
                datetime.utcnow()
            ))

            result = cursor.fetchone()
            return result is not None

    def update_task_status(self, task_id, update_data):
        """Update task status and other fields"""
        with self.get_cursor() as (cursor, conn):
            # Normalize legacy/alias status values to match the DB CHECK
            # constraint (which only allows pending/processing/completed/failed).
            if isinstance(update_data, dict) and 'status' in update_data:
                _status_aliases = {'running': 'processing', 'in_progress': 'processing'}
                update_data = dict(update_data)  # avoid mutating caller's dict
                update_data['status'] = _status_aliases.get(update_data['status'], update_data['status'])

            # Build dynamic update query
            set_clauses = []
            params = []

            # Always update the updated_at timestamp
            set_clauses.append("updated_at = %s")
            params.append(datetime.utcnow())

            # Whitelist of columns the caller is allowed to mutate. This guards
            # against any future caller passing user-controlled keys into
            # update_data (which would otherwise be interpolated straight into
            # the SQL string below).
            _ALLOWED_FIELDS = {
                'status', 'progress', 'error_message', 'search_id',
                'completed_at',
            }

            # Add other fields to update
            for field, value in update_data.items():
                if field == 'updated_at':
                    continue  # Already handled above
                if field not in _ALLOWED_FIELDS:
                    logger.warning(
                        "update_task_status: ignoring disallowed field %r", field
                    )
                    continue
                set_clauses.append(f"{field} = %s")
                params.append(value)

            # Add task_id as the last parameter for WHERE clause
            params.append(task_id)

            cursor.execute(f"""
                UPDATE hr_scorecard_tasks
                SET {', '.join(set_clauses)}
                WHERE task_id = %s
            """, params)

            return cursor.rowcount > 0

    def get_task_status(self, task_id):
        """Get task status and metadata"""
        with self.get_cursor() as (cursor, conn):
            cursor.execute("""
                SELECT
                    task_id,
                    query,
                    job_title,
                    result_count,
                    user_id,
                    company_id,
                    status,
                    progress,
                    error_message,
                    search_id,
                    created_at,
                    updated_at,
                    completed_at
                FROM hr_scorecard_tasks
                WHERE task_id = %s
            """, (task_id,))

            result = cursor.fetchone()
            if result:
                # Convert to dict and handle JSON fields
                task_data = dict(result)

                # Parse progress JSON if it exists
                if task_data.get('progress'):
                    try:
                        task_data['progress'] = json.loads(task_data['progress'])
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, keep as string
                        pass

                # Convert datetime objects to ISO format for JSON serialization
                for field in ['created_at', 'updated_at', 'completed_at']:
                    if task_data.get(field):
                        task_data[field] = task_data[field].isoformat()

                return task_data

            return None

# Create a singleton instance
db_manager = None

def get_db_manager():
    """Get or create the database manager instance with error handling"""
    global db_manager
    if db_manager is None:
        try:
            db_manager = DatabaseManager()
            logger.info("✅ Database manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database manager: {e}")
            # For development/testing, return None to allow app to continue
            db_manager = None
            return None
    return db_manager
