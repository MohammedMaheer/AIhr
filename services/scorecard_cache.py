"""Versioned scorecard identity; no reuse across changed inputs or documents."""
import hashlib
import json
import os


def signature(query, job_title, bucket, file_path, version, prompt):
    if not version:
        return None  # Missing metadata must not permit stale reuse.
    payload = {"schema": 3, "query": query or "", "job_title": job_title or "",
               "bucket": bucket, "file_path": file_path, "resume_version": str(version),
               "prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "provider": os.getenv("LLM_PROVIDER", "auto"),
               "model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
               if os.getenv("LLM_PROVIDER", "auto").lower() == "deepseek"
               else "gemini-2.5-flash|" + os.getenv("OPENAI_MODEL", "gpt-4o-mini")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
