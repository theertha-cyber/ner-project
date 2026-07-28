from dataclasses import dataclass
from typing import Any

from src.shared.config import settings as _default_settings


@dataclass(frozen=True)
class RetrievalConfig:
    """Per-instance/per-call override for retrieval behaviour settings.

    Any field left None falls back to the global `settings` object at
    resolution time. Never mutates `settings`."""

    top_k: int | None = None
    reranker_enabled: bool | None = None
    rerank_candidate_count: int | None = None


def resolve_top_k(explicit: int | None, config: RetrievalConfig | None, settings: Any = _default_settings) -> int:
    if explicit is not None:
        return explicit
    if config is not None and config.top_k is not None:
        return config.top_k
    return settings.retrieval_top_k


def resolve_reranker_enabled(config: RetrievalConfig | None, settings: Any = _default_settings) -> bool:
    if config is not None and config.reranker_enabled is not None:
        return config.reranker_enabled
    return settings.reranker_enabled


def resolve_rerank_candidate_count(config: RetrievalConfig | None, settings: Any = _default_settings) -> int:
    if config is not None and config.rerank_candidate_count is not None:
        return config.rerank_candidate_count
    return settings.rerank_candidate_count
