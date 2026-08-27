import unicodedata
import re
from datetime import date, datetime
from dataclasses import dataclass

from src.shared.config import settings


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
    # Word indices of the entity's first and last token in the caller's token list.
    # Carried so post-processing can test same-page gap adjacency between two
    # reconstructed entities without re-deriving it from character offsets.
    word_index_start: int | None = None
    word_index_end: int | None = None
    # Provenance. `source_*` hold what the deterministic pipeline produced and stay
    # None unless post-processing actually changed the value or type — see the
    # entity-extraction-provenance spec.
    source_entity_value: str | None = None
    source_entity_type: str | None = None
    postprocess_status: str = "not_applied"
    postprocess_model: str | None = None
    postprocess_prompt_version: str | None = None
    postprocess_at: "datetime | None" = None
    occurrence_count: int = 1


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


TRIM_PUNCTUATION = ".,;:!?'\"()[]{}"

# Typographic characters that a PDF extractor emits and a person typing a query never
# does. Folded to their ASCII equivalents so a stored value stays reachable by an
# equality comparison against the literal a SQL generator would write.
_TYPOGRAPHIC_FOLD = {
    0x2018: "'", 0x2019: "'",
    0x201C: '"', 0x201D: '"',
    0x2013: "-", 0x2014: "-",
}


def fold_text(value: str) -> str:
    """Removes Unicode format characters (general category `Cf`) and folds typographic
    punctuation to ASCII.

    `Cf` covers the zero-width space (U+200B) and byte-order mark (U+FEFF), which PDF
    text extraction leaves inside words. Neither NFKC nor `\\s` touches them — `\\s`
    matches `Zs`, and U+200B is `Cf` despite the name — so a value that reads as
    "software engineer" carried an invisible prefix and was unreachable by
    `normalized_value = 'software engineer'`. On the development tenant that made 5 of
    7 matching rows invisible to exact-match SQL.

    Shared by `canonicalize` and by the post-processor's evidence check, so both compare
    strings on the same footing."""
    folded = []
    for char in value:
        replacement = _TYPOGRAPHIC_FOLD.get(ord(char))
        if replacement is not None:
            folded.append(replacement)
        elif unicodedata.category(char) == "Cf":
            continue
        else:
            folded.append(char)
    return "".join(folded)


def canonicalize(value: str) -> str:
    """Deterministic fallback (format-character removal, typographic folding, NFKC,
    casefold, collapse whitespace, strip surrounding punctuation) followed by a static
    alias-map lookup keyed on that deterministic form.
    Pure function: no network or model calls."""
    normalized = unicodedata.normalize("NFKC", fold_text(value)).casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = normalized.strip(TRIM_PUNCTUATION)
    return ALIAS_MAP.get(normalized, normalized)


def trim_span(value: str) -> tuple[str, int, int]:
    """Strips leading and trailing punctuation, returning `(trimmed, left, right)` where
    `left`/`right` are the character counts removed from each end.

    The worker tokenizes on `\\S+`, so punctuation binds to the word before the model
    ever sees it — 181 of 364 stored values on the development tenant ended in `.,;:)`.
    Returning the removed counts lets the caller move `char_start`/`char_end` by the
    same amount, so the offsets keep delimiting exactly the text the stored value names
    instead of over-reaching by the characters that were dropped. Interior punctuation
    is untouched: "Uniqlo Co., Ltd." keeps its inner comma and period."""
    trimmed = value.lstrip(TRIM_PUNCTUATION)
    left = len(value) - len(trimmed)
    stripped = trimmed.rstrip(TRIM_PUNCTUATION)
    right = len(trimmed) - len(stripped)
    return stripped, left, right


def _is_adjacent(prev: dict | None, current: dict) -> bool:
    """Whether `current` continues the entity `prev` belongs to.

    Model serving filters out every `O` prediction before responding, so two labelled
    words that are pages apart arrive next to each other in this list and look adjacent.
    Continuing an entity across such a gap produces a value stitched from unrelated
    words carrying a character range far wider than the text it names. `word_index` (the
    fine-tuned path) settles it exactly.

    Requiring strictly consecutive indices was too strict in the other direction: BERT
    tagged "Having **two** and a **half years** of experience" as one entity
    (`B-YEARS_OF_EXP`, `I-`, `I-`) but the two `O` words between them were filtered out,
    so the entity split and typed as 2.0 and 0.5 years instead of 2.5. A gap of up to
    `settings.max_entity_word_gap` words on the *same page* is therefore allowed.

    The page condition is what keeps the original bug fixed, and it fails closed: a
    differing page splits at any gap, and an unknown page splits anything wider than a
    single step. Consecutive words are joined without consulting the page at all, which
    is the pre-existing behaviour.

    Predictions without `word_index` — the base-model pipeline path, whose outputs are
    WordPieces with no word alignment — keep the original permissive behaviour, since
    there is nothing to measure adjacency with."""
    if prev is None:
        return False
    prev_index = prev.get("word_index")
    current_index = current.get("word_index")
    if prev_index is None or current_index is None:
        return True

    if prev.get("page_number") != current.get("page_number"):
        return False

    stride = current_index - prev_index
    if stride <= 0:
        return False
    if stride == 1:
        return True
    if prev.get("page_number") is None:
        return False
    # `max_entity_word_gap` counts the *intervening* words, so a stride of one more
    # than the bound is still inside it: "two _and_ _a_ half" is a gap of two.
    return stride - 1 <= settings.max_entity_word_gap


def _span_value(current_tokens: list[dict], token_records: list[dict] | None) -> str:
    """The entity's surface text.

    When the caller supplies the full ordered token list, a bridged gap is filled from
    the document's own words, so "two … half years" reads back as "two and a half
    years" — the text the character range actually delimits, and the text a duration
    parser needs to reach 2.5 rather than 2.0 plus 0.5. Without that list (unit tests,
    and the base-model path, which carries no word alignment) the labelled tokens are
    joined as before."""
    if token_records:
        indices = [t.get("word_index") for t in current_tokens if t.get("word_index") is not None]
        if len(indices) == len(current_tokens) and indices:
            first, last = indices[0], indices[-1]
            if 0 <= first <= last < len(token_records):
                return " ".join(record["token"] for record in token_records[first:last + 1])
    return " ".join(t["token"] for t in current_tokens)


def reconstruct_entities(
    predictions: list[dict], token_records: list[dict] | None = None
) -> list[NormalizedEntity]:
    """Reconstructs complete logical entities from an ordered, WordPiece-merged
    prediction sequence. A `B-<TYPE>` opens a new entity; a following `I-<TYPE>` of
    the same type extends it *when the two words are adjacent in the document*;
    anything else closes it. A dangling `I-<TYPE>` with no preceding `B-<TYPE>`
    opens an entity rather than raising. Predictions must be processed in order —
    this function never keys on token text.

    `token_records` is the caller's full ordered token list (including the `O` words
    model serving filtered out). Supplying it lets a bridged gap be filled from the
    source text; omitting it falls back to joining the labelled tokens."""
    entities: list[NormalizedEntity] = []
    current_tokens: list[dict] = []
    current_type: str | None = None

    def _flush():
        if not current_tokens:
            return
        raw_value = _span_value(current_tokens, token_records)
        value, left_trimmed, right_trimmed = trim_span(raw_value)
        confidence = aggregate_confidence([t.get("confidence", 0.0) for t in current_tokens])
        page_numbers = [t.get("page_number") for t in current_tokens if t.get("page_number") is not None]
        char_starts = [t.get("char_start") for t in current_tokens if t.get("char_start") is not None]
        char_ends = [t.get("char_end") for t in current_tokens if t.get("char_end") is not None]
        # Offsets move with the trim so they keep delimiting exactly the stored value.
        char_start = char_starts[0] + left_trimmed if char_starts else None
        char_end = char_ends[-1] - right_trimmed if char_ends else None
        word_indices = [t.get("word_index") for t in current_tokens if t.get("word_index") is not None]
        entities.append(NormalizedEntity(
            entity_type=current_type,
            entity_value=value,
            normalized_value=canonicalize(value),
            confidence=confidence,
            page_number=page_numbers[0] if page_numbers else None,
            char_start=char_start,
            char_end=char_end,
            word_index_start=word_indices[0] if word_indices else None,
            word_index_end=word_indices[-1] if word_indices else None,
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


def _short_value_types() -> set[str]:
    return {
        t.strip().upper()
        for t in (settings.entity_short_value_types or "").split(",")
        if t.strip()
    }


def is_valid_entity(entity: NormalizedEntity) -> bool:
    """Whether an entity is a fact worth storing.

    `NOT NULL` does not catch an empty string, so `entity_value = ','` reached
    `document_entities` as a row whose `normalized_value` was `''`; sixteen more rows
    held values of two characters or fewer. None of them can answer a question, and all
    of them appear in the entity-value samples the SQL prompt shows the generation model.

    Length is judged per entity type rather than by a character rule: `C` and `R` are
    real programming languages, so "short and meaningful" is a property of the type. The
    exempt types are named in `settings.entity_short_value_types`."""
    value = (entity.normalized_value or "").strip()
    if not value:
        return False
    if (entity.entity_type or "").strip().upper() in _short_value_types():
        return True
    return len(value) >= settings.min_entity_value_length


def filter_valid_entities(entities: list[NormalizedEntity]) -> tuple[list[NormalizedEntity], int]:
    """Partitions entities into those worth persisting and a count of those dropped.
    The count is reported on the extraction run rather than swallowed, so a model or
    tokenizer change that starts producing junk is visible."""
    kept = [e for e in entities if is_valid_entity(e)]
    return kept, len(entities) - len(kept)


def collapse_duplicates(entities: list[NormalizedEntity]) -> list[NormalizedEntity]:
    """Collapses repeated mentions of the same fact within one document into a single
    row carrying `occurrence_count`.

    364 rows on the development tenant held 289 distinct
    `(document_id, entity_type, normalized_value)` triples — `node.js` appeared eight
    times in one document and `react` six. `COUNT(*)` therefore read repetition as
    evidence weight, ranking a document that mentions React six times above one that
    mentions it once. The count is kept because mention frequency is genuinely useful
    for ranking; it just must not be the thing a counting query counts.

    The *first* mention's page and character offsets are retained, in document order, so
    a citation pointing at this row still resolves to real text."""
    collapsed: dict[tuple[str, str], NormalizedEntity] = {}
    order: list[tuple[str, str]] = []
    for entity in entities:
        key = ((entity.entity_type or "").strip().upper(), entity.normalized_value)
        existing = collapsed.get(key)
        if existing is None:
            collapsed[key] = entity
            order.append(key)
            continue
        existing.occurrence_count += 1
        # A later mention may carry a higher confidence; the stored score stays the
        # conservative one, matching `aggregate_confidence`'s weakest-token rule.
        existing.confidence = min(existing.confidence, entity.confidence)
    return [collapsed[key] for key in order]
