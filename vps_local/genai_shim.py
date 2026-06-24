"""
genai_shim — drop-in for `google.genai` (the new client SDK).

Re-implements the small surface main.py uses:
    from google.genai import types
    client = ... (provided by main.py via genai.Client(...))
    client.models.generate_content(model=..., contents=..., config=GenerateContentConfig(...))
    response.text
    response.candidates[0].content.parts[0].text

Backend selection (in priority order):
  1. Real Gemini (Google AI Studio) when GEMINI_API_KEY is set — uses real google.genai SDK
  2. OpenAI gpt-4o-mini when OPENAI_API_KEY is set
  3. Stub responses (returns "{}" for json mode) so the app still boots
"""
from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

# ----- Lazy real-Gemini client (preferred when GEMINI_API_KEY is set) -----
_gemini_client = None
_gemini_disabled = False


def _get_gemini():
    """Return a real google.genai.Client(api_key=GEMINI_API_KEY) or None."""
    global _gemini_client, _gemini_disabled
    if _gemini_disabled:
        return None
    if _gemini_client is not None:
        return _gemini_client
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        _gemini_disabled = True
        return None
    try:
        # Use the REAL google.genai we stashed before sys.modules was patched.
        from . import REAL_GENAI
        if REAL_GENAI is None:
            _gemini_disabled = True
            print("⚠️  google.genai SDK not importable — Gemini path disabled.")
            return None
        _gemini_client = REAL_GENAI.Client(api_key=api_key)
        print(f"🤖 Gemini AI Studio client ready (key …{api_key[-4:]}).")
        return _gemini_client
    except Exception as e:
        print(f"⚠️  Gemini client init failed: {e}")
        _gemini_disabled = True
        return None


# ----- Lazy OpenAI client (fallback) -----
_openai_client = None
_openai_disabled = False


def _get_openai():
    global _openai_client, _openai_disabled
    if _openai_disabled:
        return None
    if _openai_client is not None:
        return _openai_client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _openai_disabled = True
        print("⚠️  OPENAI_API_KEY not set — LLM calls will return stub responses.")
        return None
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=api_key,
                                base_url=os.environ.get("OPENAI_BASE_URL") or None)
        return _openai_client
    except Exception as e:
        print(f"⚠️  OpenAI client init failed: {e}")
        _openai_disabled = True
        return None


# ----- types submodule (compatible with google.genai.types) -----
class _TypesModule:
    """Minimal substitute for google.genai.types."""

    @dataclass
    class ThinkingConfig:
        thinking_budget: int = 0
        include_thoughts: bool = False

    @dataclass
    class GenerateContentConfig:
        thinking_config: Any = None
        temperature: float = 0.7
        top_p: float = 0.95
        top_k: int = 40
        max_output_tokens: int = 8192
        response_mime_type: Optional[str] = None
        response_schema: Optional[Any] = None
        system_instruction: Optional[str] = None
        candidate_count: int = 1
        stop_sequences: Optional[List[str]] = None
        seed: Optional[int] = None
        safety_settings: Optional[List[Any]] = None
        tools: Optional[List[Any]] = None

    @dataclass
    class Part:
        text: str = ""

        @classmethod
        def from_text(cls, text: str):
            return cls(text=text)

        @classmethod
        def from_uri(cls, file_uri: str, mime_type: str):
            return cls(text=f"[file: {file_uri}]")

    @dataclass
    class Content:
        role: str = "user"
        parts: List["_TypesModule.Part"] = field(default_factory=list)


types = _TypesModule()


# ----- Response shape -----
@dataclass
class _UsageMetadata:
    prompt_token_count: int = 0
    candidates_token_count: int = 0
    total_token_count: int = 0


@dataclass
class _PartShape:
    text: str = ""


@dataclass
class _ContentShape:
    role: str = "model"
    parts: List[_PartShape] = field(default_factory=list)


@dataclass
class _Candidate:
    content: _ContentShape = field(default_factory=_ContentShape)
    finish_reason: str = "STOP"
    index: int = 0


@dataclass
class GenerateContentResponse:
    text: str = ""
    candidates: List[_Candidate] = field(default_factory=list)
    usage_metadata: _UsageMetadata = field(default_factory=_UsageMetadata)
    prompt_feedback: Any = None


# ----- Models endpoint -----
class _Models:
    def generate_content(self, model: str, contents: Any,
                         config: Optional[Any] = None, **kwargs) -> GenerateContentResponse:
        # 1. Try real Gemini (Google AI Studio) if GEMINI_API_KEY is set.
        gem = _get_gemini()
        if gem is not None:
            try:
                return _gemini_generate(gem, model, contents, config)
            except Exception as e:
                print(f"⚠️  Gemini generate_content failed, falling back: {e}")
                # fall through to OpenAI / stub

        # 2. Normalize contents → a single user message string.
        prompt = _flatten_contents(contents)

        client = _get_openai()
        if client is None:
            return _stub_response(prompt, config)

        # Map Gemini config → OpenAI ChatCompletion params
        openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        kw = {"model": openai_model}
        if config is not None:
            if getattr(config, "temperature", None) is not None:
                kw["temperature"] = float(config.temperature)
            if getattr(config, "top_p", None) is not None:
                kw["top_p"] = float(config.top_p)
            if getattr(config, "max_output_tokens", None):
                # OpenAI uses max_tokens; gpt-4o-mini supports up to 16k.
                kw["max_tokens"] = min(int(config.max_output_tokens), 16384)
            if getattr(config, "stop_sequences", None):
                kw["stop"] = list(config.stop_sequences)[:4]
            if getattr(config, "seed", None) is not None:
                kw["seed"] = int(config.seed)
            if getattr(config, "response_mime_type", None) == "application/json":
                kw["response_format"] = {"type": "json_object"}
                if "json" not in prompt.lower():
                    prompt += "\n\nRespond ONLY with valid JSON."

        messages = []
        if config and getattr(config, "system_instruction", None):
            sys_msg = config.system_instruction
            if hasattr(sys_msg, "parts"):
                sys_msg = "\n".join(p.text for p in sys_msg.parts)
            messages.append({"role": "system", "content": str(sys_msg)})
        messages.append({"role": "user", "content": prompt})
        kw["messages"] = messages

        t0 = time.time()
        try:
            r = client.chat.completions.create(**kw)
        except Exception as e:
            print(f"❌ OpenAI generate_content failed: {e}")
            return _stub_response(prompt, config)

        choice = r.choices[0]
        text = choice.message.content or ""
        usage = r.usage

        return GenerateContentResponse(
            text=text,
            candidates=[_Candidate(
                content=_ContentShape(role="model", parts=[_PartShape(text=text)]),
                finish_reason=str(choice.finish_reason or "STOP").upper(),
                index=0,
            )],
            usage_metadata=_UsageMetadata(
                prompt_token_count=getattr(usage, "prompt_tokens", 0) or 0,
                candidates_token_count=getattr(usage, "completion_tokens", 0) or 0,
                total_token_count=getattr(usage, "total_tokens", 0) or 0,
            ),
        )


def _flatten_contents(contents) -> str:
    """Normalize Gemini contents (str | list of str/Content/Part) → a single string."""
    if contents is None:
        return ""
    if isinstance(contents, str):
        return contents
    if isinstance(contents, list):
        out = []
        for item in contents:
            if isinstance(item, str):
                out.append(item)
            elif hasattr(item, "parts"):
                out.append("\n".join((p.text or "") for p in item.parts if hasattr(p, "text")))
            elif hasattr(item, "text"):
                out.append(item.text or "")
            else:
                out.append(str(item))
        return "\n".join(out)
    if hasattr(contents, "text"):
        return contents.text or ""
    return str(contents)


def _gemini_generate(gem_client, model: str, contents: Any,
                     config: Optional[Any]) -> GenerateContentResponse:
    """Call the REAL google.genai SDK with AI Studio and adapt the response."""
    from . import REAL_GENAI_TYPES as RT  # real types module

    # Translate our shim's GenerateContentConfig to the real one.
    real_cfg_kwargs = {}
    if config is not None:
        for attr in ("temperature", "top_p", "top_k", "max_output_tokens",
                     "response_mime_type", "response_schema",
                     "candidate_count", "stop_sequences", "seed",
                     "system_instruction"):
            v = getattr(config, attr, None)
            if v is not None:
                real_cfg_kwargs[attr] = v
        # ThinkingConfig — real types may differ. Skip if unsupported.
        try:
            tcfg = getattr(config, "thinking_config", None)
            if tcfg is not None and hasattr(RT, "ThinkingConfig"):
                real_cfg_kwargs["thinking_config"] = RT.ThinkingConfig(
                    thinking_budget=getattr(tcfg, "thinking_budget", 0)
                )
        except Exception:
            pass

    real_config = None
    if real_cfg_kwargs and hasattr(RT, "GenerateContentConfig"):
        try:
            real_config = RT.GenerateContentConfig(**real_cfg_kwargs)
        except Exception:
            # Drop unknown kwargs and retry with safe subset.
            safe = {k: v for k, v in real_cfg_kwargs.items()
                    if k in ("temperature", "top_p", "max_output_tokens",
                             "response_mime_type", "system_instruction")}
            try:
                real_config = RT.GenerateContentConfig(**safe)
            except Exception:
                real_config = None

    # AI Studio expects "gemini-..." model names. Strip "models/" prefix if present.
    if model and model.startswith("models/"):
        model = model[len("models/"):]
    # Map any *-vertex suffix or unsupported names back to a known one.
    if not model or model == "gemini-2.5-flash":
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Real SDK accepts contents as str | list | Content. Pass through.
    real_resp = gem_client.models.generate_content(
        model=model, contents=contents, config=real_config
    )

    # Adapt back to our shim's response shape so callers see same attrs.
    text = getattr(real_resp, "text", "") or ""
    cands = []
    for c in (getattr(real_resp, "candidates", None) or []):
        parts = []
        try:
            for p in c.content.parts:
                parts.append(_PartShape(text=getattr(p, "text", "") or ""))
        except Exception:
            pass
        cands.append(_Candidate(
            content=_ContentShape(role="model", parts=parts or [_PartShape(text=text)]),
            finish_reason=str(getattr(c, "finish_reason", "STOP")).upper(),
            index=getattr(c, "index", 0) or 0,
        ))
    if not cands:
        cands = [_Candidate(content=_ContentShape(parts=[_PartShape(text=text)]))]

    um = getattr(real_resp, "usage_metadata", None)
    usage = _UsageMetadata(
        prompt_token_count=getattr(um, "prompt_token_count", 0) or 0,
        candidates_token_count=getattr(um, "candidates_token_count", 0) or 0,
        total_token_count=getattr(um, "total_token_count", 0) or 0,
    )
    return GenerateContentResponse(text=text, candidates=cands, usage_metadata=usage,
                                   prompt_feedback=getattr(real_resp, "prompt_feedback", None))


def _stub_response(prompt: str, config) -> GenerateContentResponse:
    """Return a minimally-valid response when no LLM is available."""
    is_json = config is not None and getattr(config, "response_mime_type", None) == "application/json"
    text = "{}" if is_json else "[LLM disabled — set OPENAI_API_KEY]"
    return GenerateContentResponse(
        text=text,
        candidates=[_Candidate(content=_ContentShape(parts=[_PartShape(text=text)]))],
        usage_metadata=_UsageMetadata(),
    )


# ----- Top-level Client (matches google.genai.Client) -----
class Client:
    def __init__(self, *args, **kwargs):
        self.models = _Models()


# When code does `from google.genai import types`, our types submodule is published.
def get_default_generative_client():
    return Client()
