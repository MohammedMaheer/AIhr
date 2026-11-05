"""Short-lived, identity-scoped reuse of exact search inputs, never summaries."""
from __future__ import annotations

import hashlib
import json

from services.llm_cache import PreparationCache


class SearchReuse:
    def __init__(self):
        # At most 8 MiB of UTF-8 text and 8 MiB of keyword JSON, plus overhead.
        self.documents = PreparationCache(max_entries=32, ttl_seconds=300)
        self.keywords = PreparationCache(max_entries=64, ttl_seconds=900)

    def extract(self, content: bytes, bucket: str, path: str, user: dict, compute):
        identity = json.dumps([bucket, path, hashlib.sha256(content).hexdigest()])
        key = PreparationCache.key("document-text-v1", identity, user)
        result = self.documents.get_or_compute(
            key, lambda: {"text": compute()},
            lambda value: isinstance(value.get("text"), str)
            and bool(value["text"].strip())
            and len(value["text"].encode("utf-8")) <= 262144,
        )
        return result["text"]

    def match_keywords(self, content: str, keywords: list, prompt: str, user: dict, compute):
        identity = json.dumps([hashlib.sha256(content.encode("utf-8")).hexdigest(),
                               keywords, hashlib.sha256(prompt.encode("utf-8")).hexdigest()],
                              ensure_ascii=True)
        key = PreparationCache.key("candidate-keywords-v1", identity, user)

        def reusable(value):
            if not isinstance(value, dict) or value.get("analysis_method") != "llm_primary":
                return False
            matched, missing = value.get("matched_keywords"), value.get("missing_keywords")
            if not isinstance(matched, list) or not isinstance(missing, list):
                return False
            if not all(isinstance(item, str) for item in matched + missing):
                return False
            return (value.get("confidence") == "high"
                    and not set(matched).intersection(missing)
                    and set(matched + missing) == set(keywords)
                    and value.get("jd_keywords_matched") == len(matched)
                    and value.get("total_jd_keywords") == len(keywords)
                    and len(json.dumps(value, ensure_ascii=True).encode()) <= 131072)

        return self.keywords.get_or_compute(key, compute, reusable)
