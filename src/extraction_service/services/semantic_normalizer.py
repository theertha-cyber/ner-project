import json
import re
from dataclasses import dataclass
from datetime import date as _date
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.shared.entity_views import CARDINALITY_MULTI, EntityDefinitionSpec

SUPPORTED_KINDS = {"text", "number", "duration", "money", "date", "boolean"}

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_FRACTIONS = {"half": 0.5, "quarter": 0.25}
_SKIP_WORDS = {"and", "a"}

_MAGNITUDE_SUFFIXES = {
    "k": 1_000, "thousand": 1_000,
    "lakh": 100_000, "lac": 100_000,
    "million": 1_000_000, "mn": 1_000_000,
    "crore": 10_000_000, "cr": 10_000_000,
    "billion": 1_000_000_000,
}

_DURATION_UNIT_DAYS = {
    "day": 1, "days": 1,
    "week": 7, "weeks": 7,
    "month": 30, "months": 30, "mo": 30, "mos": 30,
    "year": 365, "years": 365, "yr": 365, "yrs": 365,
}

_OPEN_BOUND_PHRASES = ["more than", "at least", "over", "greater than"]

_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_AFFIRMATIVE = {"yes", "true", "y"}
_NEGATIVE = {"no", "false", "n"}


@dataclass
class StructuredValue:
    value_kind: str
    number: float | None = None
    number_high: float | None = None
    unit: str | None = None
    date: _date | None = None
    date_high: _date | None = None


Parser = Callable[[str, "str | None"], "StructuredValue | None"]


def _words_to_number(phrase: str) -> float | None:
    tokens = [t for t in re.findall(r"[a-zA-Z]+", phrase.lower()) if t not in _SKIP_WORDS]
    if not tokens:
        return None
    total = 0.0
    matched = False
    for tok in tokens:
        if tok in _ONES:
            total += _ONES[tok]
            matched = True
        elif tok in _TENS:
            total += _TENS[tok]
            matched = True
        elif tok in _FRACTIONS:
            total += _FRACTIONS[tok]
            matched = True
    return total if matched else None


def _digits_to_number(phrase: str) -> float | None:
    phrase = phrase.strip()
    m = re.match(r"^(\d[\d,]*(?:\.\d+)?)\s*([a-zA-Z]*)$", phrase)
    if not m:
        return None
    raw_number, suffix = m.groups()
    try:
        value = float(raw_number.replace(",", ""))
    except ValueError:
        return None
    suffix = suffix.lower()
    if suffix and suffix in _MAGNITUDE_SUFFIXES:
        value *= _MAGNITUDE_SUFFIXES[suffix]
    return value


_LEADING_NUMERAL_RE = re.compile(r"^(\d[\d,]*(?:\.\d+)?)\s*([a-zA-Z]*)\b")


def _leading_numeral_to_number(phrase: str) -> float | None:
    """A numeral at the start of a phrase, with arbitrary words after it.

    `_digits_to_number` anchors on `$`, so it only reads a value that is *entirely* a
    numeral and an optional suffix. `_words_to_number` then sees "2 years of experience",
    collects only the alphabetic tokens, finds no number word, and returns None — the
    digit is never consulted. The result was that "2+ years of experience" typed as 2.0
    while "2 years of experience," typed as nothing at all, for values meaning the same
    thing."""
    match = _LEADING_NUMERAL_RE.match(phrase.strip())
    if not match:
        return None
    raw_number, suffix = match.groups()
    try:
        value = float(raw_number.replace(",", ""))
    except ValueError:
        return None
    suffix = suffix.lower()
    if suffix and suffix in _MAGNITUDE_SUFFIXES:
        value *= _MAGNITUDE_SUFFIXES[suffix]
    return value


def _read_number(phrase: str) -> float | None:
    phrase = phrase.strip()
    if not phrase:
        return None
    value = _digits_to_number(phrase)
    if value is not None:
        return value
    # Word forms are tried before the leading-numeral fallback so a phrase mixing both
    # ("two and a half years") still sums its words rather than stopping at a stray digit.
    value = _words_to_number(phrase)
    if value is not None:
        return value
    return _leading_numeral_to_number(phrase)


def _extract_range(text: str) -> tuple[str, str] | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", text)
    if m:
        return m.group(1), m.group(2)
    return None


def _extract_open_bound_phrase(text: str) -> str | None:
    lowered = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+", lowered)
    if m:
        return m.group(1)
    for phrase in _OPEN_BOUND_PHRASES:
        idx = lowered.find(phrase)
        if idx != -1:
            remainder = lowered[idx + len(phrase):].strip()
            tokens = remainder.split()
            if tokens:
                return tokens[0]
    return None


def _extract_source_unit(text: str) -> str | None:
    lowered = text.lower()
    for unit in sorted(_DURATION_UNIT_DAYS, key=len, reverse=True):
        if re.search(rf"\b{unit}\b", lowered):
            return unit
    return None


def _convert_duration(value: float, source_unit: str, canonical_unit: str) -> float:
    source_days = _DURATION_UNIT_DAYS.get(source_unit, _DURATION_UNIT_DAYS.get(canonical_unit, 1))
    canonical_days = _DURATION_UNIT_DAYS.get(canonical_unit, 1)
    return value * source_days / canonical_days


def _parse_number_kind(text: str, unit: str | None) -> StructuredValue | None:
    range_match = _extract_range(text)
    if range_match:
        low = _read_number(range_match[0])
        high = _read_number(range_match[1])
        if low is None or high is None:
            return None
        return StructuredValue(value_kind="number", number=low, number_high=high, unit=unit)

    bound_phrase = _extract_open_bound_phrase(text)
    if bound_phrase is not None:
        value = _read_number(bound_phrase)
        if value is None:
            return None
        return StructuredValue(value_kind="number", number=value, unit=unit)

    value = _read_number(text)
    if value is None:
        return None
    return StructuredValue(value_kind="number", number=value, unit=unit)


def _parse_money_kind(text: str, unit: str | None) -> StructuredValue | None:
    result = _parse_number_kind(text, unit)
    if result is None:
        return None
    result.value_kind = "money"
    return result


def _parse_duration_kind(text: str, unit: str | None) -> StructuredValue | None:
    canonical_unit = unit or "years"
    source_unit = _extract_source_unit(text) or canonical_unit

    range_match = _extract_range(text)
    if range_match:
        low = _read_number(range_match[0])
        high = _read_number(range_match[1])
        if low is None or high is None:
            return None
        return StructuredValue(
            value_kind="duration",
            number=_convert_duration(low, source_unit, canonical_unit),
            number_high=_convert_duration(high, source_unit, canonical_unit),
            unit=canonical_unit,
        )

    bound_phrase = _extract_open_bound_phrase(text)
    value = _read_number(bound_phrase) if bound_phrase is not None else _read_number(text)
    if value is None:
        return None
    return StructuredValue(
        value_kind="duration",
        number=_convert_duration(value, source_unit, canonical_unit),
        unit=canonical_unit,
    )


def _parse_date_kind(text: str, unit: str | None) -> StructuredValue | None:
    cleaned = text.strip()

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", cleaned)
    if m:
        try:
            parsed = _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return StructuredValue(value_kind="date", date=parsed)

    m = re.match(r"^(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})$", cleaned)
    if m:
        day, month_name, year = m.groups()
        month = _MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        try:
            parsed = _date(int(year), month, int(day))
        except ValueError:
            return None
        return StructuredValue(value_kind="date", date=parsed)

    m = re.match(r"^([a-zA-Z]+)\s+(\d{4})$", cleaned)
    if m:
        month_name, year = m.groups()
        month = _MONTH_NAMES.get(month_name.lower())
        if month is None:
            return None
        return StructuredValue(value_kind="date", date=_date(int(year), month, 1))

    return None


def _parse_boolean_kind(text: str, unit: str | None) -> StructuredValue | None:
    lowered = text.strip().lower()
    if lowered in _AFFIRMATIVE:
        return StructuredValue(value_kind="boolean", number=1.0)
    if lowered in _NEGATIVE:
        return StructuredValue(value_kind="boolean", number=0.0)
    return None


PARSERS: dict[str, Parser] = {
    "number": _parse_number_kind,
    "money": _parse_money_kind,
    "duration": _parse_duration_kind,
    "date": _parse_date_kind,
    "boolean": _parse_boolean_kind,
}


def normalize_value(text: str, kind: str | None, unit: str | None) -> StructuredValue | None:
    """Pure, deterministic dispatch by declared value kind. No network, database, or LLM calls.
    Returns None for `text`/unknown kinds and for values a parser cannot confidently parse —
    never raises on unparseable input."""
    if not kind or kind not in PARSERS:
        return None
    try:
        return PARSERS[kind](text, unit)
    except Exception:
        return None


@dataclass
class EntityTypeConfig:
    value_kind: str | None = None
    value_unit: str | None = None


def load_entity_type_config(conn: Connection, tenant_id: str) -> dict[str, EntityTypeConfig]:
    """Reads `value_kind`/`value_unit` from `public.entity_definitions` for the tenant,
    keyed by lowercased entity type name so lookup matches BIO-reconstructed entity types
    case-insensitively."""
    rows = conn.execute(
        text("SELECT name, value_kind, value_unit FROM public.entity_definitions WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    return {
        row.name.lower(): EntityTypeConfig(value_kind=row.value_kind, value_unit=row.value_unit)
        for row in rows.fetchall()
    }


def load_entity_definition_specs(conn: Connection, tenant_id: str) -> list[EntityDefinitionSpec]:
    """The same catalog, as the value object the relational layer needs.

    A sibling of `load_entity_type_config`, deliberately not an extension of it:
    `apply_semantic_normalization` and `postprocess_document` both consume that function's
    `dict[str, EntityTypeConfig]` return type, and widening it to carry the projection's fields
    would change two call sites that have no interest in them.

    A definition whose `sql_identifier` is NULL is omitted. It is not slugged here: a read-time
    slug is not stable across processes, so two workers could disagree about a table's name.
    The identifier is assigned once, at create, by `EntityService.create_entity_type`. A NULL
    therefore means "no relation exists for this type", and the entity still reaches
    `document_entities` — it is only absent from the relational surface.

    Ordered by `sql_identifier` so the collision tie-break in `relational_projection` (first by
    identifier sort order) is decided by the catalog rather than by row order."""
    rows = conn.execute(
        text(
            "SELECT name, sql_identifier, cardinality, value_kind, is_active, base_label_mapping "
            "FROM public.entity_definitions "
            "WHERE tenant_id = :tid AND sql_identifier IS NOT NULL "
            "ORDER BY sql_identifier"
        ),
        {"tid": tenant_id},
    )
    return [
        EntityDefinitionSpec(
            name=row.name,
            sql_identifier=row.sql_identifier,
            cardinality=row.cardinality or CARDINALITY_MULTI,
            value_kind=row.value_kind,
            is_active=bool(row.is_active),
            base_label_mapping=_as_mapping(row.base_label_mapping),
        )
        for row in rows.fetchall()
    ]


def _as_mapping(value) -> dict | None:
    """`base_label_mapping` reads back as a dict on JSONB and as text on a TEXT column."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def apply_semantic_normalization(entities: list, type_config: dict) -> tuple[list, int]:
    """Populates the six semantic value fields on each entity in place, dispatched by the
    entity type's declared kind in `type_config` (keyed by lowercased entity type name).
    Returns (entities, unparseable_count) where unparseable_count is the number of entities
    whose declared kind was non-text but yielded no typed value."""
    unparseable = 0
    for entity in entities:
        cfg = type_config.get(entity.entity_type.lower()) if type_config else None
        if cfg is None or not cfg.value_kind or cfg.value_kind == "text":
            continue
        structured = normalize_value(entity.entity_value, cfg.value_kind, cfg.value_unit)
        if structured is None:
            unparseable += 1
            continue
        entity.value_kind = structured.value_kind
        entity.value_number = structured.number
        entity.value_number_high = structured.number_high
        entity.value_unit = structured.unit
        entity.value_date = structured.date
        entity.value_date_high = structured.date_high
    return entities, unparseable
