import unicodedata
import re
from datetime import date
from dataclasses import dataclass


@dataclass
class NormalizedEntity:
    entity_type: str
    entity_value: str
    normalized_value: str
    confidence: float
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    # Semantic normalization fields (populated by semantic_normalizer.apply_semantic_normalization,
    # never by this module) — see structured-entity-value-normalization design.md Decision 1.
    value_kind: str | None = None
    value_number: float | None = None
    value_number_high: float | None = None
    value_unit: str | None = None
    value_date: date | None = None
    value_date_high: date | None = None


# Static alias map keyed on the *already deterministically-normalized* form of a
# surface variant (casefolded, whitespace-collapsed, punctuation-stripped) so one
# entry covers every casing/spacing variant of that surface form.
ALIAS_MAP: dict[str, str] = {
    "reactjs": "react",
    "react js": "react",
    "react.js": "react",
    "amazon web services": "aws",
    "aws": "aws",
}


def _split_bio(label: str) -> tuple[str | None, str]:
    """Splits a `B-TYPE`/`I-TYPE` label into (prefix, type). Labels with no
    recognized BIO prefix (e.g. bare `O` or an unprefixed type) yield (None, label)."""
    if label.startswith("B-") or label.startswith("I-"):
        return label[0], label[2:]
    return None, label


def merge_wordpieces(predictions: list[dict]) -> list[dict]:
    """Merges `##`-prefixed WordPiece continuation tokens into the preceding
    token's text, regardless of the continuation token's own BIO label. Confidence
    of a merged token is the minimum of its constituent pieces, consistent with
    the entity-level aggregation strategy."""
    merged: list[dict] = []
    for pred in predictions:
        token = pred.get("token", "")
        if token.startswith("##") and merged:
            prev = merged[-1]
            prev["token"] = prev["token"] + token[2:]
            prev["confidence"] = min(prev["confidence"], pred.get("confidence", 0.0))
            if pred.get("char_end") is not None:
                prev["char_end"] = pred["char_end"]
            continue
        merged.append(dict(pred))
    return merged


def aggregate_confidence(scores: list[float]) -> float:
    """Entity-level confidence is the minimum of its constituent tokens' confidences —
    an entity is only as trustworthy as its weakest token, which keeps the score
    conservative rather than letting confident neighbours mask a weak boundary token."""
    return min(scores)


def canonicalize(value: str) -> str:
    """Deterministic fallback (NFKC, casefold, collapse whitespace, strip surrounding
    punctuation) followed by a static alias-map lookup keyed on that deterministic form.
    Pure function: no network or model calls."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = normalized.strip(".,;:!?'\"()[]{}")
    return ALIAS_MAP.get(normalized, normalized)


def _is_adjacent(prev: dict | None, current: dict) -> bool:
    """Whether `current` directly follows `prev` in the source document.

    Model serving filters out every `O` prediction before responding, so two
    labelled words that are pages apart arrive next to each other in this list and
    look adjacent. Continuing an entity across such a gap produces a value stitched
    from unrelated words carrying a character range far wider than the text it
    names. `word_index` (the fine-tuned path) settles it exactly.

    Predictions without `word_index` — the base-model pipeline path, whose outputs
    are WordPieces with no word alignment — keep the original permissive behaviour,
    since there is nothing to measure adjacency with."""
    if prev is None:
        return False
    prev_index = prev.get("word_index")
    current_index = current.get("word_index")
    if prev_index is None or current_index is None:
        return True
    return current_index == prev_index + 1


def reconstruct_entities(predictions: list[dict]) -> list[NormalizedEntity]:
    """Reconstructs complete logical entities from an ordered, WordPiece-merged
    prediction sequence. A `B-<TYPE>` opens a new entity; a following `I-<TYPE>` of
    the same type extends it *when the two words are adjacent in the document*;
    anything else closes it. A dangling `I-<TYPE>` with no preceding `B-<TYPE>`
    opens an entity rather than raising. Predictions must be processed in order —
    this function never keys on token text."""
    entities: list[NormalizedEntity] = []
    current_tokens: list[dict] = []
    current_type: str | None = None

    def _flush():
        if not current_tokens:
            return
        value = " ".join(t["token"] for t in current_tokens)
        confidence = aggregate_confidence([t.get("confidence", 0.0) for t in current_tokens])
        page_numbers = [t.get("page_number") for t in current_tokens if t.get("page_number") is not None]
        char_starts = [t.get("char_start") for t in current_tokens if t.get("char_start") is not None]
        char_ends = [t.get("char_end") for t in current_tokens if t.get("char_end") is not None]
        entities.append(NormalizedEntity(
            entity_type=current_type,
            entity_value=value,
            normalized_value=canonicalize(value),
            confidence=confidence,
            page_number=page_numbers[0] if page_numbers else None,
            char_start=char_starts[0] if char_starts else None,
            char_end=char_ends[-1] if char_ends else None,
        ))

    for pred in predictions:
        prefix, ent_type = _split_bio(pred.get("label", "O"))

        if prefix == "B":
            _flush()
            current_tokens = [pred]
            current_type = ent_type
        elif prefix == "I":
            if current_tokens and current_type == ent_type and _is_adjacent(current_tokens[-1], pred):
                current_tokens.append(pred)
            else:
                # Either a dangling I- tag with no matching open entity, or one that
                # continues the right type but from somewhere else in the document.
                # Both open a fresh entity rather than raising or stitching a gap.
                _flush()
                current_tokens = [pred]
                current_type = ent_type
        else:
            _flush()
            current_tokens = []
            current_type = None

    _flush()
    return entities
