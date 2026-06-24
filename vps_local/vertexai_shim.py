"""
vertexai_shim — drop-in for `vertexai`, `vertexai.generative_models`,
and `vertexai.language_models`.

Maps:
  - vertexai.init(...)                                    -> no-op
  - vertexai.generative_models.GenerativeModel            -> OpenAI-backed
  - vertexai.generative_models.GenerationConfig            -> dataclass
  - vertexai.language_models.TextEmbeddingModel           -> sentence-transformers
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from . import genai_shim


def init(project: Optional[str] = None, location: Optional[str] = None, **kwargs):
    """No-op stub for vertexai.init()."""
    return None


# ===== generative_models submodule =====
class _GenerativeModelsModule:

    @dataclass
    class GenerationConfig:
        temperature: float = 0.7
        top_p: float = 0.95
        top_k: int = 40
        max_output_tokens: int = 8192
        candidate_count: int = 1
        stop_sequences: Optional[List[str]] = None
        response_mime_type: Optional[str] = None
        response_schema: Optional[Any] = None

    @dataclass
    class GenerativeModel:
        model_name: str = "gemini-2.5-flash"
        system_instruction: Optional[str] = None
        generation_config: Optional[Any] = None

        def __init__(self, model_name: str = "gemini-2.5-flash",
                     system_instruction: Optional[str] = None,
                     generation_config: Optional[Any] = None,
                     **kwargs):
            self.model_name = model_name
            self.system_instruction = system_instruction
            self.generation_config = generation_config

        def generate_content(self, contents, generation_config=None, **kwargs):
            cfg = generation_config or self.generation_config
            # Bridge through the genai_shim path for consistency
            if cfg is not None:
                # Re-map vertexai.GenerationConfig to genai_shim types config
                bridged = genai_shim.types.GenerateContentConfig(
                    temperature=getattr(cfg, "temperature", 0.7) or 0.7,
                    top_p=getattr(cfg, "top_p", 0.95) or 0.95,
                    max_output_tokens=getattr(cfg, "max_output_tokens", 8192) or 8192,
                    response_mime_type=getattr(cfg, "response_mime_type", None),
                    stop_sequences=getattr(cfg, "stop_sequences", None),
                    system_instruction=self.system_instruction,
                )
            else:
                bridged = None
            client = genai_shim.Client()
            return client.models.generate_content(
                model=self.model_name, contents=contents, config=bridged
            )


generative_models = _GenerativeModelsModule()


# ===== language_models submodule (embeddings) =====
_embed_model_singleton = None


def _get_embedder():
    global _embed_model_singleton
    if _embed_model_singleton is not None:
        return _embed_model_singleton
    try:
        from sentence_transformers import SentenceTransformer
        model_name = os.environ.get("SMARTHR_EMBED_MODEL", "all-MiniLM-L6-v2")
        # Cache dir helps Docker layer caching.
        cache = os.environ.get("SENTENCE_TRANSFORMERS_HOME") or "/app/.st_cache"
        os.makedirs(cache, exist_ok=True)
        _embed_model_singleton = SentenceTransformer(model_name, cache_folder=cache)
        return _embed_model_singleton
    except Exception as e:
        print(f"❌ Failed to load sentence-transformers: {e}")
        raise


@dataclass
class _Embedding:
    values: List[float] = field(default_factory=list)
    statistics: Any = None


class _LanguageModelsModule:

    class TextEmbeddingModel:
        def __init__(self, model_id: str = "all-MiniLM-L6-v2"):
            self.model_id = model_id

        @classmethod
        def from_pretrained(cls, name: str):
            return cls(model_id=name)

        def get_embeddings(self, texts: List[str], **kwargs) -> List[_Embedding]:
            if isinstance(texts, str):
                texts = [texts]
            model = _get_embedder()
            vecs = model.encode(texts, normalize_embeddings=True,
                                show_progress_bar=False, batch_size=32)
            return [_Embedding(values=v.tolist()) for v in vecs]


language_models = _LanguageModelsModule()
