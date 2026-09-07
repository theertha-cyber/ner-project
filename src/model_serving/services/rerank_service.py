import time
import logging
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from src.shared.config import settings
from src.shared.observability.domain_metrics import record_rerank_duration

logger = logging.getLogger(__name__)

_reranker_tokenizer = None
_reranker_model = None


def _get_reranker():
    global _reranker_tokenizer, _reranker_model
    if _reranker_model is None:
        _reranker_tokenizer = AutoTokenizer.from_pretrained(settings.reranker_model)
        _reranker_model = AutoModelForSequenceClassification.from_pretrained(settings.reranker_model)
        _reranker_model.eval()
    return _reranker_tokenizer, _reranker_model


def rerank(query: str, documents: list[str], top_k: int | None = None) -> list[dict]:
    if not documents:
        return []

    # Measured on the serving side as well as at the caller in
    # `shared/retrieval/reranker.py`: the two numbers differ by the network hop, and the
    # gap between them is what says whether a slow rerank is the model or the wire.
    started = time.monotonic()
    tokenizer, model = _get_reranker()
    pairs = [[query, doc] for doc in documents]
    inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors="pt")

    with torch.no_grad():
        logits = model(**inputs).logits.squeeze(-1)
        scores = logits.tolist()
    if isinstance(scores, float):
        scores = [scores]

    ranked = sorted(
        ({"index": i, "score": float(s)} for i, s in enumerate(scores)),
        key=lambda r: r["score"],
        reverse=True,
    )
    if top_k is not None:
        ranked = ranked[:top_k]
    record_rerank_duration(time.monotonic() - started)
    return ranked
