# SmartHR — VPS local-mode (100% GCP-free)
#
# When SMARTHR_LOCAL_MODE=1, this package monkey-patches sys.modules to replace
# google.cloud.storage, google.cloud.discoveryengine_v1, google.genai,
# vertexai, and vertexai.generative_models / vertexai.language_models with
# local equivalents backed by:
#   - filesystem (/app/storage/resumes) for object storage
#   - pgvector (resume_embeddings table) for vector search
#   - sentence-transformers (all-MiniLM-L6-v2) for embeddings
#   - OpenAI gpt-4o-mini for LLM (or stub if no OPENAI_API_KEY)
#
# Activation: import this package BEFORE any google.cloud imports in main.py.

from __future__ import annotations
import os
import sys

ENABLED = os.environ.get("SMARTHR_LOCAL_MODE", "").lower() in ("1", "true", "yes", "on")


# Real google.genai SDK (preserved for AI Studio API-key mode if available).
# Imported BEFORE we shadow `google.genai` in sys.modules.
REAL_GENAI = None
REAL_GENAI_TYPES = None
try:  # pragma: no cover — optional dep
    import google.genai as _real_genai_mod  # type: ignore
    import google.genai.types as _real_genai_types_mod  # type: ignore
    REAL_GENAI = _real_genai_mod
    REAL_GENAI_TYPES = _real_genai_types_mod
except Exception:
    pass


def _core_shims_active(storage_shim, discovery_shim, vertexai_shim) -> bool:
    """Return True only when the active module table still points at shims."""
    return (
        sys.modules.get("google.cloud.storage") is storage_shim
        and sys.modules.get("google.cloud.discoveryengine_v1") is discovery_shim
        and sys.modules.get("vertexai") is vertexai_shim
    )


def _set_parent_attr(parent_name: str, attr: str, module) -> None:
    """Keep `from parent import attr` from returning a stale real SDK attr."""
    parent = sys.modules.get(parent_name)
    if parent is not None:
        try:
            setattr(parent, attr, module)
        except Exception:
            pass


def install():
    """Install all GCP shims into sys.modules. Idempotent."""
    if not ENABLED:
        return False

    from . import storage_shim, discovery_shim, genai_shim, vertexai_shim

    if sys.modules.get("__smarthr_local_installed__") and _core_shims_active(
        storage_shim, discovery_shim, vertexai_shim
    ):
        return True

    # Patch google.cloud.storage
    sys.modules["google.cloud.storage"] = storage_shim
    sys.modules["google.cloud.storage.client"] = storage_shim
    _set_parent_attr("google.cloud", "storage", storage_shim)
    # Patch google.cloud.discoveryengine_v1
    sys.modules["google.cloud.discoveryengine_v1"] = discovery_shim
    sys.modules["google.cloud.discoveryengine"] = discovery_shim
    _set_parent_attr("google.cloud", "discoveryengine_v1", discovery_shim)
    _set_parent_attr("google.cloud", "discoveryengine", discovery_shim)

    # google.genai handling:
    #   - If REAL_GENAI is importable AND GEMINI_API_KEY is set, KEEP the real
    #     SDK in sys.modules and only monkey-patch Client.__init__ to force
    #     AI Studio mode (ignore vertexai/project/location passed by main.py).
    #   - Otherwise install our stub/OpenAI-backed shim.
    have_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    if REAL_GENAI is not None and have_key:
        _patch_real_genai_for_ai_studio()
        sys.modules["google.genai"] = REAL_GENAI
        if REAL_GENAI_TYPES is not None:
            sys.modules["google.genai.types"] = REAL_GENAI_TYPES
        _set_parent_attr("google", "genai", REAL_GENAI)
        print("🤖 google.genai → real Gemini AI Studio (api_key mode).")
    else:
        sys.modules["google.genai"] = genai_shim
        sys.modules["google.genai.types"] = genai_shim.types
        _set_parent_attr("google", "genai", genai_shim)

    # Patch vertexai
    sys.modules["vertexai"] = vertexai_shim
    sys.modules["vertexai.generative_models"] = vertexai_shim.generative_models
    sys.modules["vertexai.language_models"] = vertexai_shim.language_models

    sys.modules["__smarthr_local_installed__"] = True  # type: ignore
    print("✅ SmartHR local-mode shims installed (GCP-free).")
    return True


def _patch_real_genai_for_ai_studio():
    """Wrap real google.genai.Client so callers passing vertexai=True with a
    project/location get redirected to AI Studio (api_key) mode instead.
    """
    if REAL_GENAI is None:
        return
    Client = REAL_GENAI.Client
    if getattr(Client.__init__, "_smarthr_patched", False):
        return
    _orig_init = Client.__init__
    api_key_env = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def _patched_init(self, *args, **kwargs):  # type: ignore
        # Force AI Studio: drop vertexai/project/location/credentials, set api_key
        kwargs.pop("vertexai", None)
        kwargs.pop("enterprise", None)
        kwargs.pop("project", None)
        kwargs.pop("location", None)
        kwargs.pop("credentials", None)
        if not kwargs.get("api_key"):
            kwargs["api_key"] = api_key_env
        return _orig_init(self, *args, **kwargs)

    _patched_init._smarthr_patched = True  # type: ignore[attr-defined]
    Client.__init__ = _patched_init


# Auto-install on import when env var is set.
install()
