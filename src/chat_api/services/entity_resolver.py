import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction_service.services.entity_normalizer import canonicalize
from src.shared.config import settings

logger = logging.getLogger(__name__)

UNRESOLVED = "unresolved"
UNIQUE = "unique"
AMBIGUOUS = "ambiguous"
OVER_CAP = "over_cap"

# Heuristic entity_type groupings used only for candidate-card field selection.
# document_entities.entity_type is the tenant's raw extraction label (e.g. "PER",
# "ORG"); these sets recognise the common label spellings tenants use for the
# card's optional fields. They are not a configuration surface — a type that
# doesn't match any group simply doesn't appear on the card.
_ORGANIZATION_TYPES = {"ORG", "ORGANIZATION", "ORGANISATION", "COMPANY", "EMPLOYER"}
_EXPERIENCE_TYPES = {"EXPERIENCE", "YEARS_EXPERIENCE", "YOE", "DURATION", "TENURE"}
_SKILL_TYPES = {"SKILL", "SKILLS", "TECHNOLOGY", "TECH"}

_WORD_RE = re.compile(r"[A-Za-z0-9']+")


@dataclass
class Candidate:
    document_id: str
    name: str
    organization: str | None = None
    experience: str | None = None
    skills: list[str] = field(default_factory=list)
    filename: str | None = None


# A stored name can contain a single-letter token ("zanith kumar r"), and word-level
# matching would then let any message containing a standalone "r" resolve to that
# person. Widening a turn's document scope on that evidence is worse than not
# resolving it, so single-character mentions never contribute.
MIN_MENTION_CHARS = 2


@dataclass
class ResolutionResult:
    outcome: str
    mention: str | None = None
    mentions_checked: int = 0
    resolved_document_id: str | None = None
    resolved_entity_value: str | None = None
    candidates: list[Candidate] = field(default_factory=list)
    # Every document the message's mentions resolved to, not just the first mention's.
    # "Compare Hannah and Girish" used to collapse to Girish alone, so the prompt
    # carried evidence for one of the two subjects the user named.
    resolved_document_ids: list[str] = field(default_factory=list)
    # Which mention contributed which documents, for tracing why a turn widened.
    mention_documents: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        # `resolved_document_id` predates the set and is still the shape most callers
        # and tests speak in. The two are kept consistent here rather than at every
        # construction site: a single-document resolution reads either way, and a
        # multi-document one exposes no single id to be mistaken for the whole answer.
        if not self.resolved_document_ids and self.resolved_document_id:
            self.resolved_document_ids = [self.resolved_document_id]
        elif self.resolved_document_id is None and len(self.resolved_document_ids) == 1:
            self.resolved_document_id = self.resolved_document_ids[0]


def _extract_mentions(message: str) -> list[tuple[str, str, int]]:
    """Returns (raw_ngram, canonical_ngram, word_count) for every contiguous 1-3 word
    n-gram in `message`, ordered longest-first and deduplicated by canonical value
    (keeping the first raw occurrence of each). Pure function: no I/O, no LLM call."""
    words = _WORD_RE.findall(message)
    seen: set[str] = set()
    ordered: list[tuple[str, str, int]] = []
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            raw = " ".join(words[i:i + n])
            canon = canonicalize(raw)
            if not canon or canon in seen:
                continue
            seen.add(canon)
            ordered.append((raw, canon, n))
    return ordered


_POSSESSIVE_RE = re.compile(r"['’]s$", re.IGNORECASE)


def _depossessive(canon: str) -> str | None:
    """Strips a trailing possessive from a canonical mention, or None if there is none.

    "arjun's resume" canonicalises to "arjun's", and "arjuns resume" — the apostrophe
    dropped, as people type it — to "arjuns". Neither equals the stored name, so the
    reference goes unresolved. The bare-s form is stripped too, which would also
    shorten a genuine name ending in s ("james" -> "jame"); that is why these are
    only ever tried as a *second pass*, after the unmodified mentions have failed to
    match anything. A real James matches on the first pass and never reaches here."""
    stripped = _POSSESSIVE_RE.sub("", canon)
    if stripped == canon and canon.endswith("s") and len(canon) > 2:
        stripped = canon[:-1]
    stripped = stripped.strip()
    return stripped if stripped and stripped != canon else None


def _mention_matches(canon: str, normalized_value: str) -> bool:
    """Whether a mention identifies the person whose stored name is `normalized_value`.

    Names are stored whole ("arjun jayakumar") but referred to in part ("arjun"), so
    an equality test alone resolves only the rare message that repeats someone's full
    name. A mention matching any single word of the stored name counts."""
    if canon == normalized_value:
        return True
    return canon in normalized_value.split()


def _person_types() -> set[str]:
    return {t.strip().upper() for t in settings.entity_resolution_person_types.split(",") if t.strip()}


async def _resolve_tenant_person_types(session: AsyncSession, tenant_id: str) -> set[str]:
    """Extends the static person-type set with any tenant-configured entity type
    whose `base_label_mapping` maps to the raw `PER` label, so tenant-defined
    schemas (e.g. a resume-specific "Candidate Name" type) are recognised too."""
    types = _person_types()
    result = await session.execute(
        text("SELECT name, base_label_mapping FROM public.entity_definitions WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    for row in result.fetchall():
        mapping = row[1]
        if isinstance(mapping, str):
            import json
            try:
                mapping = json.loads(mapping)
            except (json.JSONDecodeError, TypeError):
                mapping = None
        if isinstance(mapping, dict) and "PER" in mapping:
            types.add(row[0].strip().upper())
    return types


async def _lookup_candidate_rows(
    session: AsyncSession, schema: str, canonical_values: list[str], person_types: set[str],
) -> list[dict]:
    if not canonical_values or not person_types:
        return []
    # A mention matches the whole stored name or any single word of it — people say
    # "arjun", the extractor stored "arjun jayakumar". `string_to_array(...) && :values`
    # is the word-level half; keeping the equality test as well means a stored
    # single-word name still matches without relying on the array overlap.
    result = await session.execute(
        text(f"""
            SELECT document_id, entity_type, entity_value, normalized_value
            FROM {schema}.document_entities
            WHERE upper(entity_type) = ANY(:types)
              AND (
                normalized_value = ANY(:values)
                OR string_to_array(normalized_value, ' ') && CAST(:values AS text[])
              )
        """),
        {"values": canonical_values, "types": sorted(person_types)},
    )
    return [dict(r._mapping) for r in result.fetchall()]


async def _build_candidates(session: AsyncSession, schema: str, doc_ids: list[str], winning_rows: list[dict]) -> list[Candidate]:
    name_by_doc: dict[str, str] = {}
    for row in winning_rows:
        name_by_doc.setdefault(row["document_id"], row["entity_value"])

    field_rows = await session.execute(
        text(f"""
            SELECT document_id, entity_type, entity_value
            FROM {schema}.document_entities
            WHERE document_id = ANY(:doc_ids)
        """),
        {"doc_ids": doc_ids},
    )

    org_by_doc: dict[str, str] = {}
    exp_by_doc: dict[str, str] = {}
    skills_by_doc: dict[str, list[str]] = {}
    for row in field_rows.fetchall():
        doc_id, entity_type, entity_value = row.document_id, (row.entity_type or "").strip().upper(), row.entity_value
        if entity_type in _ORGANIZATION_TYPES and doc_id not in org_by_doc:
            org_by_doc[doc_id] = entity_value
        elif entity_type in _EXPERIENCE_TYPES and doc_id not in exp_by_doc:
            exp_by_doc[doc_id] = entity_value
        elif entity_type in _SKILL_TYPES:
            skills = skills_by_doc.setdefault(doc_id, [])
            if entity_value not in skills and len(skills) < settings.entity_resolution_max_skills:
                skills.append(entity_value)

    candidates = [
        Candidate(
            document_id=doc_id,
            name=name_by_doc[doc_id],
            organization=org_by_doc.get(doc_id),
            experience=exp_by_doc.get(doc_id),
            skills=skills_by_doc.get(doc_id, []),
        )
        for doc_id in doc_ids
    ]

    def _render_key(c: Candidate) -> tuple:
        return (c.name, c.organization, c.experience, tuple(c.skills))

    keys = [_render_key(c) for c in candidates]
    if len(set(keys)) < len(keys):
        filenames = await session.execute(
            text(f"SELECT id, filename FROM {schema}.documents WHERE id = ANY(:ids)"),
            {"ids": doc_ids},
        )
        filename_by_doc = {row.id: row.filename for row in filenames.fetchall()}
        for c in candidates:
            c.filename = filename_by_doc.get(c.document_id)

    return candidates


@dataclass
class _MentionMatch:
    raw: str
    canon: str
    words: frozenset[str]
    rows: list[dict]
    document_ids: list[str]


def _accept_matching_mentions(
    mentions: list[tuple[str, str, int]], rows: list[dict]
) -> list[_MentionMatch]:
    """Every distinct subject the message named, longest mention first.

    Mentions arrive longest-first and overlap heavily — "arjun jayakumar" is followed
    by "arjun" and "jayakumar", all naming the same person. A shorter mention whose
    words are already covered by an accepted longer one is skipped, which is what
    keeps the longer, more specific mention deciding the match; a mention naming a
    *different* person shares no words and is accepted alongside it.

    The previous implementation stopped at the first match entirely, so the second
    subject of a comparison was silently dropped."""
    accepted: list[_MentionMatch] = []
    covered_words: set[str] = set()

    for raw, canon, _n in mentions:
        if len(canon) < MIN_MENTION_CHARS:
            continue
        words = frozenset(canon.split())
        if words and words <= covered_words:
            continue
        matching_rows = [r for r in rows if _mention_matches(canon, r["normalized_value"])]
        if not matching_rows:
            continue

        document_ids: list[str] = []
        for row in matching_rows:
            if row["document_id"] not in document_ids:
                document_ids.append(row["document_id"])

        accepted.append(_MentionMatch(raw=raw, canon=canon, words=words, rows=matching_rows, document_ids=document_ids))
        covered_words |= words

    return accepted


async def resolve_entity(message: str, session: AsyncSession, schema: str, tenant_id: str) -> ResolutionResult:
    """Resolves person-entity references in `message` against `document_entities`.
    Tenant-scoped by `schema` (caller-supplied, never derived from `message`).
    Issues no LLM call."""
    mentions = _extract_mentions(message)
    if not mentions:
        logger.info("entity_resolution outcome=%s tenant_id=%s mentions_checked=0", UNRESOLVED, tenant_id)
        return ResolutionResult(outcome=UNRESOLVED, mentions_checked=0)

    person_types = await _resolve_tenant_person_types(session, tenant_id)
    canonical_values = [c for _, c, _ in mentions]
    rows = await _lookup_candidate_rows(session, schema, canonical_values, person_types)

    if not rows:
        # Second pass with possessives stripped. Deliberately only reached when the
        # mentions as written matched nothing, so a real name is never shortened out
        # from under a match it already had.
        depossessed = [(raw, _depossessive(canon), n) for raw, canon, n in mentions]
        mentions = [(raw, canon, n) for raw, canon, n in depossessed if canon]
        if mentions:
            rows = await _lookup_candidate_rows(
                session, schema, [c for _, c, _ in mentions], person_types,
            )

    if not rows:
        logger.info("entity_resolution outcome=%s tenant_id=%s mentions_checked=%d", UNRESOLVED, tenant_id, len(mentions))
        return ResolutionResult(outcome=UNRESOLVED, mentions_checked=len(mentions))

    matches = _accept_matching_mentions(mentions, rows)
    if not matches:
        logger.info("entity_resolution outcome=%s tenant_id=%s mentions_checked=%d", UNRESOLVED, tenant_id, len(mentions))
        return ResolutionResult(outcome=UNRESOLVED, mentions_checked=len(mentions))

    union: list[str] = []
    mention_documents: dict[str, list[str]] = {}
    for match in matches:
        mention_documents[match.raw] = list(match.document_ids)
        for doc_id in match.document_ids:
            if doc_id not in union:
                union.append(doc_id)

    first = matches[0]
    # Ambiguity is still a property of ONE mention matching several people — two
    # mentions matching one person each is a comparison, not an ambiguity.
    ambiguous = next((m for m in matches if len(m.document_ids) > 1), None)

    if len(union) > settings.entity_resolution_max_candidates:
        logger.info(
            "entity_resolution outcome=%s tenant_id=%s mentions_checked=%d candidate_documents=%d",
            OVER_CAP, tenant_id, len(mentions), len(union),
        )
        return ResolutionResult(
            outcome=OVER_CAP, mention=(ambiguous or first).raw, mentions_checked=len(mentions),
            mention_documents=mention_documents,
        )

    if ambiguous is not None:
        candidates = await _build_candidates(session, schema, list(ambiguous.document_ids), ambiguous.rows)
        logger.info(
            "entity_resolution outcome=%s tenant_id=%s mentions_checked=%d candidate_documents=%d",
            AMBIGUOUS, tenant_id, len(mentions), len(ambiguous.document_ids),
        )
        return ResolutionResult(
            outcome=AMBIGUOUS, mention=ambiguous.raw, mentions_checked=len(mentions),
            candidates=candidates, mention_documents=mention_documents,
        )

    logger.info(
        "entity_resolution outcome=%s tenant_id=%s mentions_checked=%d candidate_documents=%d subjects=%d",
        UNIQUE, tenant_id, len(mentions), len(union), len(matches),
    )
    return ResolutionResult(
        outcome=UNIQUE, mention=first.raw, mentions_checked=len(mentions),
        resolved_document_ids=union,
        resolved_entity_value=", ".join(m.rows[0]["entity_value"] for m in matches),
        mention_documents=mention_documents,
    )


def render_clarification(mention: str, candidates: list[Candidate]) -> str:
    """Deterministic clarification text — no LLM call."""
    lines = [f'I found multiple candidates named "{mention}". Which one did you mean?', ""]
    for i, c in enumerate(candidates, start=1):
        parts = [c.name]
        if c.organization:
            parts.append(c.organization)
        if c.experience:
            parts.append(c.experience)
        if c.skills:
            parts.append(", ".join(c.skills))
        if c.filename:
            parts.append(c.filename)
        lines.append(f"{i}. " + " — ".join(parts))
    return "\n".join(lines)


def render_narrowing_message(mention: str) -> str:
    return (
        f'I found too many candidates named "{mention}" to list. '
        "Could you narrow your question — e.g. by company, role, or another detail?"
    )


_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
}
_ORDINAL_RE = re.compile(r"\b(?:candidate\s*)?#?(\d+)\b", re.IGNORECASE)
_ORDINAL_WORD_RE = re.compile(r"\b(first|second|third|fourth|fifth)\b", re.IGNORECASE)


def parse_ordinal_selection(answer: str, candidate_count: int) -> int | None:
    """Returns a 0-based candidate index parsed deterministically from an ordinal or
    numeric reference, or None if the answer contains none. Does not validate range
    beyond what's structurally implied — callers still range-check."""
    word_match = _ORDINAL_WORD_RE.search(answer)
    if word_match:
        idx = _ORDINAL_WORDS[word_match.group(1).lower()]
        return idx - 1 if 1 <= idx <= candidate_count else None

    num_match = _ORDINAL_RE.search(answer)
    if num_match:
        idx = int(num_match.group(1))
        return idx - 1 if 1 <= idx <= candidate_count else None

    return None


SELECTION_SYSTEM_PROMPT = (
    "You are selecting which candidate the user meant from a fixed, numbered list. "
    "You may ONLY return the number of one candidate from the list below, or the "
    "word 'none' if the user's answer does not clearly identify any of them. "
    "Do not invent a candidate, name, or number that is not in the list. "
    "Respond with exactly one token: a number or 'none'."
)


def _render_candidates_for_prompt(candidates: list[Candidate]) -> str:
    lines = []
    for i, c in enumerate(candidates, start=1):
        parts = [c.name]
        if c.organization:
            parts.append(c.organization)
        if c.experience:
            parts.append(c.experience)
        if c.skills:
            parts.append(", ".join(c.skills))
        lines.append(f"{i}. " + " — ".join(parts))
    return "\n".join(lines)


async def interpret_selection(answer: str, candidates: list[Candidate], llm_client, llm_model: str) -> int | None:
    """Returns a 0-based candidate index, or None if no candidate was identified.
    Tries deterministic ordinal parsing first; falls back to one constrained LLM
    call whose only legal outputs are an in-range index or 'none'."""
    ordinal = parse_ordinal_selection(answer, len(candidates))
    if ordinal is not None:
        return ordinal

    messages = [
        {"role": "system", "content": SELECTION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Candidates:\n{_render_candidates_for_prompt(candidates)}\n\nUser's answer: {answer}"},
    ]
    try:
        response = await llm_client.chat.completions.create(
            model=llm_model, messages=messages, temperature=0, max_tokens=5,
        )
        content = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("entity_resolution selection call failed: %s", e)
        return None

    match = re.search(r"\d+", content)
    if not match:
        return None
    idx = int(match.group(0)) - 1
    if 0 <= idx < len(candidates):
        return idx
    return None
