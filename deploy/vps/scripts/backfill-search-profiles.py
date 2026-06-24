#!/usr/bin/env python3
"""Backfill structured candidate profiles for VPS local-mode search.

Uses cached Gemini scorecards when available, then falls back to lightweight
regex/text extraction from resume_embeddings.extracted_text.

Run inside the app container:
  docker compose exec smarthr-app python /app/deploy/vps/scripts/backfill-search-profiles.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

_candidates = []
try:
    _candidates.append(Path(__file__).resolve().parents[3])
except Exception:
    pass
_candidates.extend([Path("/app"), Path.cwd()])
for APP_ROOT in _candidates:
    if (APP_ROOT / "vps_local").exists():
        if str(APP_ROOT) not in sys.path:
            sys.path.insert(0, str(APP_ROOT))
        break

from vps_local.profile_extractor import (  # noqa: E402
    merge_profiles,
    profile_from_analysis,
    profile_from_text,
)


SCHEMA_STATEMENTS = [
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_years NUMERIC(5,2)",
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_location TEXT",
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_languages TEXT[]",
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS candidate_skills TEXT[]",
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS profile_source TEXT",
    "ALTER TABLE resume_embeddings ADD COLUMN IF NOT EXISTS profile_updated_at TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_years ON resume_embeddings(candidate_years)",
    "CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_location ON resume_embeddings(candidate_location)",
    "CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_languages ON resume_embeddings USING gin(candidate_languages)",
    "CREATE INDEX IF NOT EXISTS idx_resume_emb_candidate_skills ON resume_embeddings USING gin(candidate_skills)",
    "CREATE INDEX IF NOT EXISTS idx_resume_emb_text_fts ON resume_embeddings USING gin(to_tsvector('simple', coalesce(extracted_text, '')))",
]


def get_db():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "smarthr-postgres"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ.get("DB_NAME", "recruitment"),
        user=os.environ.get("DB_USER", "smarthr"),
        password=os.environ.get("DB_PASSWORD", ""),
    )


def ensure_schema(cur) -> None:
    for stmt in SCHEMA_STATEMENTS:
        cur.execute(stmt)


def load_cache(cur) -> tuple[dict[str, dict], dict[str, dict]]:
    cur.execute(
        """
        SELECT DISTINCT ON (file_path)
               file_path, gemini_analysis, source, created_at
          FROM cached_resume_analyses
         WHERE gemini_analysis ? 'hr_scorecard'
         ORDER BY file_path, (source = 'live_gemini') DESC, created_at DESC
        """
    )
    by_path: dict[str, dict] = {}
    by_name: dict[str, dict] = {}
    for row in cur.fetchall():
        file_path = row["file_path"] or ""
        profile = profile_from_analysis(row["gemini_analysis"])
        profile["profile_source"] = f"cache:{row.get('source') or 'unknown'}"
        if file_path:
            by_path[file_path] = profile
            by_name[Path(file_path).name] = profile
    return by_path, by_name


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Recompute rows that already have profiles")
    parser.add_argument("--limit", type=int, default=0, help="Optional max rows to update")
    args = parser.parse_args()

    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    ensure_schema(cur)
    conn.commit()

    print("Loading cached scorecard profiles...")
    cache_by_path, cache_by_name = load_cache(cur)
    print(f"Cached profile candidates: paths={len(cache_by_path):,}, filenames={len(cache_by_name):,}")

    where = "" if args.refresh else "WHERE profile_updated_at IS NULL"
    limit = f" LIMIT {int(args.limit)}" if args.limit else ""
    cur.execute(
        f"""
        SELECT id, filename, folder, extracted_text
          FROM resume_embeddings
          {where}
         ORDER BY id
         {limit}
        """
    )
    rows = cur.fetchall()
    print(f"Rows to update: {len(rows):,}")

    updated = 0
    cache_hits = 0
    text_only = 0
    for row in rows:
        filename = row["filename"]
        rel_path = f"{(row['folder'] or 'legacy').rstrip('/')}/{filename}"
        cache_profile = cache_by_path.get(rel_path) or cache_by_name.get(filename)
        if cache_profile:
            cache_hits += 1
        text_profile = profile_from_text(row.get("extracted_text") or "", source="text")
        profile = merge_profiles(cache_profile or {}, text_profile)
        if not cache_profile:
            text_only += 1

        cur.execute(
            """
            UPDATE resume_embeddings
               SET candidate_years = %s,
                   candidate_location = NULLIF(%s, ''),
                   candidate_languages = %s,
                   candidate_skills = %s,
                   profile_source = %s,
                   profile_updated_at = NOW()
             WHERE id = %s
            """,
            (
                profile.get("candidate_years"),
                profile.get("candidate_location") or "",
                profile.get("candidate_languages") or [],
                profile.get("candidate_skills") or [],
                profile.get("profile_source") or "text",
                row["id"],
            ),
        )
        updated += 1
        if updated % 500 == 0:
            conn.commit()
            print(f"  updated {updated:,}/{len(rows):,}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. updated={updated:,}, cache_hits={cache_hits:,}, text_only={text_only:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
