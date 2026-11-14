"""Bounded, process-local reuse of successful job-description preparation."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future
from typing import Callable


class PreparationCache:
    def __init__(self, max_entries: int = 128, ttl_seconds: float = 900,
                 clock: Callable[[], float] = time.monotonic):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._pending: dict[str, Future] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(operation: str, query: str, user: dict, *, company_preparation: bool = False) -> str | None:
        if not user or user.get("id") is None:
            return None
        company = user.get("company")
        if isinstance(company, dict):
            company_id = company.get("company_id") or company.get("id")
            company_code = company.get("company_code")
        else:
            company_id = getattr(company, "company_id", None) or getattr(company, "id", None)
            company_code = getattr(company, "company_code", None)
        if user.get("user_type") != "super_admin" and company_id is None and not company_code:
            return None
        provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-flash") if provider == "deepseek" else os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        payload = [provider, model, operation, user["id"], user.get("user_type"),
                   company_id, company_code, query]
        # These operations depend only on the exact JD, never on recruiter data.
        # Other caches (including CV text) retain their existing per-user keys.
        if (company_preparation and operation in {"query", "keywords"}
                and user.get("user_type") in {"tenant_admin", "tenant_user"}
                and isinstance(company_id, int) and not isinstance(company_id, bool) and company_id > 0):
            payload[3:5] = ["company-preparation-v1", "tenant"]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()

    def get_or_compute(self, key: str | None, compute: Callable[[], dict],
                       cacheable: Callable[[dict], bool]) -> dict:
        if key is None or self.max_entries <= 0 or self.ttl_seconds <= 0:
            return compute()
        with self._lock:
            now = self._clock()
            expired = [k for k, (deadline, _) in self._entries.items() if deadline <= now]
            for k in expired:
                self._entries.pop(k, None)
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                return copy.deepcopy(entry[1])
            future = self._pending.get(key)
            leader = future is None
            if leader:
                future = Future()
                self._pending[key] = future
        if not leader:
            return copy.deepcopy(future.result())

        try:
            result = compute()
            snapshot = copy.deepcopy(result)
            with self._lock:
                if cacheable(result):
                    self._entries[key] = (self._clock() + self.ttl_seconds, snapshot)
                    self._entries.move_to_end(key)
                    while len(self._entries) > self.max_entries:
                        self._entries.popitem(last=False)
                self._pending.pop(key, None)
            future.set_result(snapshot)
            return result
        except BaseException as exc:
            with self._lock:
                self._pending.pop(key, None)
            future.set_exception(exc)
            raise
