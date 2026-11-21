"""Versioned scorecard identity; no reuse across changed inputs or documents."""
import hashlib
import json
import os


def signature(query, job_title, bucket, file_path, version, prompt, *,
              keywords=None, auxiliary_prompts=()):
    if not version:
        return None  # Missing metadata must not permit stale reuse.
    provider = os.getenv('LLM_PROVIDER', 'auto').strip().lower()
    # Version 4 also invalidates assessments created before untrusted-input fencing.
    payload = {"schema": 4, "query": query or "", "job_title": job_title or "",
               "bucket": bucket, "file_path": file_path, "resume_version": str(version),
               "prompt": hashlib.sha256(prompt.encode()).hexdigest(),
               "keywords": list(keywords or []),
               "auxiliary_prompts": [hashlib.sha256(value.encode()).hexdigest()
                                     for value in auxiliary_prompts],
               "provider": provider,
               "model": (os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash")
               if provider == "deepseek"
               else "gemini-2.5-flash|" + os.getenv("OPENAI_MODEL", "gpt-4o-mini")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
