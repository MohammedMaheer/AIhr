"""DeepSeek transport for the existing text-based Gemini-compatible call surface."""
from __future__ import annotations

import json
import os
import threading
import logging
import time


BASE_URL = "https://api.deepseek.com"
_client = None
_client_key = None
_lock = threading.Lock()
_requests = threading.BoundedSemaphore(max(1, int(os.getenv("AI_MAX_CONCURRENT", "4"))))
log = logging.getLogger(__name__)


def enabled() -> bool:
    return os.getenv("LLM_PROVIDER", "auto").strip().lower() == "deepseek"


def model_name() -> str:
    return os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip() or "deepseek-flash"


def display_name(suffix: str = "") -> str:
    name = f"DeepSeek ({model_name()})" if enabled() else "Gemini 2.5 Flash"
    return name + (" " + suffix if suffix else "")


def get_client():
    global _client, _client_key
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
    with _lock:
        if _client is None or _client_key != key:
            from openai import OpenAI
            _client = OpenAI(api_key=key, base_url=BASE_URL, timeout=120.0, max_retries=0)
            _client_key = key
    return _client


def _field(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _text(value) -> str:
    if isinstance(value, str):
        return value
    parts = _field(value, "parts")
    if parts is not None:
        return "\n".join(_text(part) for part in parts)
    if _field(value, "inline_data") is not None or _field(value, "file_data") is not None:
        raise ValueError("DeepSeek analysis requires extracted document text. This file needs OCR or a supported text extraction step.")
    text = _field(value, "text")
    if text is not None:
        return str(text)
    raise ValueError("Unsupported non-text content for DeepSeek analysis.")


def generate_completion(contents, config=None):
    items = [contents] if isinstance(contents, str) else list(contents or [])
    messages = []
    instruction = _field(config, "system_instruction")
    if instruction:
        messages.append({"role": "system", "content": _text(instruction)})
    for item in items:
        role = _field(item, "role", "user")
        role = "assistant" if role == "model" else role
        if role not in ("user", "assistant", "system"):
            raise ValueError("Unsupported message role for DeepSeek analysis.")
        messages.append({"role": role, "content": _text(item)})
    if not messages or not any(m["content"].strip() for m in messages if m["role"] == "user"):
        raise ValueError("DeepSeek analysis requires non-empty user text.")

    thinking = _field(config, "thinking_config")
    thinking_enabled = (_field(thinking, "thinking_budget", 0) or 0) > 0
    kwargs = {"model": model_name(), "messages": messages,
              "extra_body": {"thinking": {"type": "enabled" if thinking_enabled else "disabled"}}}
    for attr in ("temperature", "top_p"):
        value = _field(config, attr)
        if value is not None:
            kwargs[attr] = float(value)
    limit = _field(config, "max_output_tokens")
    if limit is not None:
        kwargs["max_tokens"] = int(limit)
    stops = _field(config, "stop_sequences")
    if stops:
        kwargs["stop"] = list(stops)
    json_output = _field(config, "response_mime_type") == "application/json"
    if json_output:
        kwargs["response_format"] = {"type": "json_object"}
        if not any("json" in m["content"].lower() for m in messages):
            messages.append({"role": "user", "content": "Respond only with a valid JSON object."})
    if not _requests.acquire(timeout=120):
        raise RuntimeError("AI capacity is busy; retry this search shortly.")
    started = time.monotonic()
    try:
        # Thread cancellation cannot recall an HTTP request already in flight.
        # Fence subsequent paid calls, including retries, after ownership expires.
        from services.task_lease import TaskLeaseLost, current_lease
        lease = current_lease.get()
        if lease:
            from database import get_db_manager
            database = get_db_manager()
            if database is None or not database.get_owned_hr_task(*lease):
                raise TaskLeaseLost("Search ownership expired before the provider call")
        try:
            response = get_client().chat.completions.create(**kwargs)
        except Exception as exc:
            _record_usage(None, started, success=False, error=type(exc).__name__)
            raise
    finally:
        _requests.release()
    _record_usage(response, started, success=True)
    if not response.choices or not (response.choices[0].message.content or "").strip():
        raise RuntimeError("DeepSeek returned an empty answer; no analysis was accepted.")
    if response.choices[0].finish_reason != "stop":
        raise RuntimeError("DeepSeek did not complete its answer; no incomplete analysis was accepted.")
    if json_output:
        result = json.loads(response.choices[0].message.content)
        if not isinstance(result, dict):
            raise ValueError("DeepSeek did not return the requested JSON object.")
    return response


def _record_usage(response, started, *, success, error=None):
    usage = getattr(response, "usage", None)
    data = {"provider": "deepseek", "model": model_name(), "operation": "text_generation",
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "success": success, "error_message": error}
    log.info("llm_usage %s", json.dumps(data, separators=(",", ":")))
    if os.getenv("SMARTHR_LOCAL_MODE", "").lower() not in {"1", "true", "yes", "on"}:
        return
    if os.getenv("LLM_USAGE_DB_LOG", "1") == "0":
        return
    try:
        from database import get_db_manager
        get_db_manager().log_llm_call(**data)
    except Exception:
        log.warning("AI usage database logging unavailable; usage retained in application logs.")
