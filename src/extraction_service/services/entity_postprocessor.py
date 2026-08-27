"""Optional LLM post-processing over the deterministic BERT extraction result.

The fine-tuned model stays the primary extraction mechanism. This stage looks only at
*selected* entities — those the deterministic pipeline has a reason to doubt — and may
only correct them within an explicit contract. It never reads a document looking for
entities BERT missed, and it never emits a value the document does not contain.

The boundary between an evidence-supported correction and a model invention is enforced
structurally, not by prompt instruction: every emitted value is checked for containment
in the exact text window the server supplied, and an emission that fails is discarded
while the deterministic row is persisted unchanged.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.extraction_service.services.entity_normalizer import (
    NormalizedEntity,
    canonicalize,
    fold_text,
    trim_span,
)
from src.extraction_service.services.semantic_normalizer import apply_semantic_normalization
from src.shared.config import settings

logger = logging.getLogger(__name__)

KEEP = "keep"
MODIFY = "modify"
MERGE = "merge"
REJECT = "reject"
DECISIONS = {KEEP, MODIFY, MERGE, REJECT}

STATUS_NOT_APPLIED = "not_applied"
STATUS_KEPT = "kept"
STATUS_MODIFIED = "modified"
STATUS_MERGED = "merged"
STATUS_FAILED = "failed"


class PostprocessUnavailable(Exception):
    """The stage could not run. Never propagated past `postprocess_document`, which
    fails open — a successful BERT extraction is not lost because an optional
    enhancement was unavailable."""


@dataclass
class Candidate:
    """One entity offered to the post-processor.

    `candidate_id` is assigned by the server, per request, and is not a database
    identifier: a model that invents an id addresses nothing, and one that echoes an id
    cannot reach a row it was not shown."""

    candidate_id: int
    entity: NormalizedEntity
    window: str


@dataclass
class PostprocessOutcome:
    entities: list[NormalizedEntity]
    degraded: bool = False
    discarded: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# Candidate selection
# --------------------------------------------------------------------------------------


def _multi_token_types() -> set[str]:
    return {
        t.strip().upper()
        for t in (settings.postprocess_multi_token_types or "").split(",")
        if t.strip()
    }


def _is_typed_kind(entity: NormalizedEntity, type_config: dict) -> bool:
    config = type_config.get((entity.entity_type or "").lower()) if type_config else None
    return bool(config and config.value_kind and config.value_kind != "text")


def _has_near_neighbour(entity: NormalizedEntity, entities: list[NormalizedEntity]) -> bool:
    """Adjacency is symmetric: a merge needs *both* fragments in the request, so the
    later one must be selected on the strength of the earlier one too."""
    for other in entities:
        if other is entity:
            continue
        if _mergeable(entity, other):
            return True
    return False


def select_candidates(
    entities: list[NormalizedEntity],
    type_config: dict | None = None,
    extraction_schema_version: int | None = None,
) -> list[int]:
    """Indices of the entities worth showing the post-processor.

    Post-processing every entity was measured against and rejected: on the development
    tenant, 364 rows across 8 documents held four confirmed type errors, one split
    entity and roughly sixteen junk rows — under 6% once the deterministic repairs land.
    Sending the other 94% costs sixteen times as much for no reachable gain and puts
    correct extractions at risk of being "improved".

    The confidence rule only applies to rows produced by the calibrated pipeline. A raw
    logit is not on the `[0, 1]` scale the threshold is expressed in, so comparing
    against one would route by noise."""
    schema_version = (
        settings.extraction_schema_version
        if extraction_schema_version is None
        else extraction_schema_version
    )
    confidence_is_calibrated = schema_version >= settings.extraction_schema_version
    multi_token_types = _multi_token_types()

    selected: list[int] = []
    for index, entity in enumerate(entities):
        if confidence_is_calibrated and entity.confidence < settings.postprocess_confidence_threshold:
            selected.append(index)
            continue
        # A type that declares a numeric or date kind but produced no typed value is a
        # value the deterministic parser could not read — exactly the class of surface
        # damage this stage exists for.
        if _is_typed_kind(entity, type_config or {}) and entity.value_kind is None:
            selected.append(index)
            continue
        if (
            (entity.entity_type or "").upper() in multi_token_types
            and len(entity.entity_value.split()) == 1
        ):
            selected.append(index)
            continue
        if _has_near_neighbour(entity, entities):
            selected.append(index)
    return selected


# --------------------------------------------------------------------------------------
# Request construction
# --------------------------------------------------------------------------------------


def build_window(token_records: list[dict], entity: NormalizedEntity) -> str:
    """The evidence window for one candidate: its own words plus surrounding context,
    grown outward until `postprocess_context_chars` is reached.

    Built from the token list rather than sliced out of the raw document so it is
    assembled exactly the way the entity value is, which is what makes the containment
    check in `_evidence_supported` a meaningful test rather than a whitespace lottery."""
    if not token_records or entity.word_index_start is None or entity.word_index_end is None:
        return entity.entity_value

    budget = settings.postprocess_context_chars
    start = max(0, entity.word_index_start)
    end = min(len(token_records) - 1, entity.word_index_end)
    length = sum(len(token_records[i]["token"]) + 1 for i in range(start, end + 1))

    while length < budget and (start > 0 or end < len(token_records) - 1):
        grew = False
        if start > 0:
            candidate_length = length + len(token_records[start - 1]["token"]) + 1
            if candidate_length <= budget:
                start -= 1
                length = candidate_length
                grew = True
        if end < len(token_records) - 1:
            candidate_length = length + len(token_records[end + 1]["token"]) + 1
            if candidate_length <= budget:
                end += 1
                length = candidate_length
                grew = True
        if not grew:
            break

    return " ".join(record["token"] for record in token_records[start:end + 1])


def build_candidates(
    entities: list[NormalizedEntity],
    indices: list[int],
    token_records: list[dict],
) -> list[Candidate]:
    return [
        Candidate(candidate_id=position, entity=entities[index], window=build_window(token_records, entities[index]))
        for position, index in enumerate(indices)
    ]


PROMPT_VERSIONS: dict[str, str] = {
    "v1": (
        "You are correcting the output of a named-entity recognition model. You are NOT "
        "extracting entities: every item below was already found by the model, and your "
        "only job is to decide what to do with it.\n\n"
        "For each candidate return exactly one decision:\n"
        '  "keep"   - the value and type are correct as they are.\n'
        '  "modify" - the value and/or type is wrong and the evidence window shows the '
        "correction. Set \"value\" to the corrected surface text, and/or \"entity_type\" "
        "to the corrected type.\n"
        '  "merge"  - this candidate and the candidates listed in "merge_with" are '
        "fragments of one entity. Set \"value\" to the combined surface text.\n"
        '  "reject" - the candidate is not a real instance of its type (an extraction '
        "artifact, or a value of an entirely different kind).\n\n"
        "Hard rules:\n"
        "- Any value you return MUST appear verbatim in that candidate's evidence window. "
        "Never write a value the window does not contain. If you cannot correct a "
        'candidate using only the window, return "keep".\n'
        "- Never invent a candidate. Return exactly one decision per candidate id given.\n"
        "- Only use an entity type from the allowed list.\n"
        "- Do not fix capitalisation, punctuation or spacing; that is handled elsewhere.\n"
        "- Do not return numbers, dates or units; those are derived separately.\n\n"
        "Allowed entity types: {allowed_types}\n\n"
        "Respond with JSON only, in the form:\n"
        '{{"decisions": [{{"candidate_id": 0, "decision": "keep", "value": null, '
        '"entity_type": null, "merge_with": [], "reason": "..."}}]}}'
    )
}


def render_prompt(candidates: list[Candidate], allowed_types: list[str]) -> tuple[str, str]:
    version = settings.postprocess_prompt_version
    template = PROMPT_VERSIONS.get(version)
    if template is None:
        raise PostprocessUnavailable(f"unknown postprocess prompt version: {version!r}")

    system = template.format(allowed_types=", ".join(sorted(allowed_types)) or "(none configured)")
    payload = {
        "candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "entity_type": candidate.entity.entity_type,
                "value": candidate.entity.entity_value,
                "page_number": candidate.entity.page_number,
                "evidence_window": candidate.window,
            }
            for candidate in candidates
        ]
    }
    return system, json.dumps(payload, ensure_ascii=False)


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------


def _comparable(value: str) -> str:
    """Both sides of the containment check are folded and casefolded the same way, so a
    correction that differs from the source only by a curly quote or a zero-width space
    is still recognised as supported — and one that differs by a word is not."""
    return " ".join(fold_text(value or "").casefold().split())


def _evidence_supported(value: str, window: str) -> bool:
    needle = _comparable(value)
    return bool(needle) and needle in _comparable(window)


def validate_decisions(
    raw: object,
    candidates: list[Candidate],
    allowed_types: set[str],
) -> tuple[dict[int, dict], list[str]]:
    """Turns whatever the model returned into decisions safe to apply.

    A response that does not parse against the schema discards the whole batch; a single
    bad item discards only itself. Nothing here writes to the database — validated
    decisions are applied by `apply_decisions`, and the resulting values still go through
    the same deterministic canonicalization and semantic normalization as every other
    row, so the model cannot bypass the tenant's value-kind configuration."""
    if not isinstance(raw, dict):
        raise PostprocessUnavailable("response was not a JSON object")
    items = raw.get("decisions")
    if not isinstance(items, list):
        raise PostprocessUnavailable("response had no 'decisions' list")

    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    accepted: dict[int, dict] = {}
    discarded: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            discarded.append("decision was not an object")
            continue

        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, int) or candidate_id not in by_id:
            discarded.append(f"unknown candidate_id {candidate_id!r}")
            continue
        if candidate_id in accepted:
            discarded.append(f"duplicate decision for candidate_id {candidate_id}")
            continue

        decision = item.get("decision")
        if decision not in DECISIONS:
            discarded.append(f"candidate {candidate_id}: unknown decision {decision!r}")
            continue

        candidate = by_id[candidate_id]
        entity_type = item.get("entity_type")
        if entity_type is not None:
            if not isinstance(entity_type, str) or entity_type.strip().upper() not in allowed_types:
                discarded.append(f"candidate {candidate_id}: entity_type {entity_type!r} is not configured")
                continue

        value = item.get("value")
        if decision in (MODIFY, MERGE):
            if not isinstance(value, str) or not value.strip():
                # A `modify` with no value is only a type correction; without either it
                # says nothing.
                if decision == MODIFY and entity_type is not None:
                    value = None
                else:
                    discarded.append(f"candidate {candidate_id}: {decision} without a value")
                    continue
            elif not _evidence_supported(value, candidate.window):
                # The invention boundary.
                discarded.append(
                    f"candidate {candidate_id}: value not supported by the evidence window"
                )
                continue

        merge_with: list[int] = []
        if decision == MERGE:
            raw_merge = item.get("merge_with")
            if not isinstance(raw_merge, list) or not raw_merge:
                discarded.append(f"candidate {candidate_id}: merge without merge_with")
                continue
            invalid = False
            for other_id in raw_merge:
                other = by_id.get(other_id) if isinstance(other_id, int) else None
                if other is None or other_id == candidate_id:
                    discarded.append(f"candidate {candidate_id}: merge_with {other_id!r} is not a candidate")
                    invalid = True
                    break
                if not _mergeable(candidate.entity, other.entity):
                    discarded.append(
                        f"candidate {candidate_id}: merge_with {other_id} is not an adjacent same-page neighbour"
                    )
                    invalid = True
                    break
                merge_with.append(other_id)
            if invalid:
                continue

        accepted[candidate_id] = {
            "decision": decision,
            "value": value if isinstance(value, str) else None,
            "entity_type": entity_type,
            "merge_with": merge_with,
        }

    return accepted, discarded


def _mergeable(left: NormalizedEntity, right: NormalizedEntity) -> bool:
    """Merging is bounded exactly as BIO continuation is: same type, same page, and
    within the configured word gap. An unbounded merge would re-create the cross-page
    stitching the reconstruction guard exists to prevent."""
    if (left.entity_type or "").upper() != (right.entity_type or "").upper():
        return False
    if left.page_number != right.page_number:
        return False
    if left.word_index_end is None or right.word_index_start is None:
        return False
    first, second = (left, right) if left.word_index_end <= right.word_index_start else (right, left)
    stride = second.word_index_start - first.word_index_end
    return stride > 0 and stride - 1 <= settings.max_entity_word_gap


# --------------------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------------------


def _stamp(entity: NormalizedEntity, status: str, processed_at: datetime) -> None:
    entity.postprocess_status = status
    entity.postprocess_model = settings.azure_openai_chat_deployment
    entity.postprocess_prompt_version = settings.postprocess_prompt_version
    entity.postprocess_at = processed_at


def _record_source(entity: NormalizedEntity, original_value: str, original_type: str) -> None:
    """Originals are stored only when something actually changed, so a NULL means
    "unchanged" rather than "unknown"."""
    if entity.entity_value != original_value:
        entity.source_entity_value = original_value
    if entity.entity_type != original_type:
        entity.source_entity_type = original_type


def apply_decisions(
    entities: list[NormalizedEntity],
    indices: list[int],
    candidates: list[Candidate],
    accepted: dict[int, dict],
    type_config: dict | None,
) -> list[NormalizedEntity]:
    """Rebuilds the entity list with validated decisions applied.

    Candidates with no accepted decision keep exactly what the deterministic pipeline
    produced. The post-processor never writes to `document_entities`; corrected values
    are re-canonicalized and re-typed here by the same code every other row goes through."""
    processed_at = datetime.now(timezone.utc)
    entity_by_candidate = {c.candidate_id: c.entity for c in candidates}
    dropped: set[int] = set()
    absorbed: set[int] = set()

    for candidate_id, decision in accepted.items():
        entity = entity_by_candidate[candidate_id]
        original_value, original_type = entity.entity_value, entity.entity_type

        if decision["decision"] == KEEP:
            _stamp(entity, STATUS_KEPT, processed_at)
            continue

        if decision["decision"] == REJECT:
            dropped.add(id(entity))
            continue

        if decision["decision"] == MERGE:
            targets = [entity_by_candidate[other_id] for other_id in decision["merge_with"]]
            if any(id(t) in dropped or id(t) in absorbed for t in targets):
                _stamp(entity, STATUS_KEPT, processed_at)
                continue
            merged_value, _, _ = trim_span(decision["value"])
            entity.entity_value = merged_value
            entity.normalized_value = canonicalize(merged_value)
            _extend_span(entity, targets)
            for target in targets:
                absorbed.add(id(target))
            _record_source(entity, original_value, original_type)
            _stamp(entity, STATUS_MERGED, processed_at)
            continue

        # MODIFY
        if decision["value"]:
            modified_value, _, _ = trim_span(decision["value"])
            entity.entity_value = modified_value
            entity.normalized_value = canonicalize(modified_value)
        if decision["entity_type"]:
            entity.entity_type = decision["entity_type"].strip().upper()
        _record_source(entity, original_value, original_type)
        _stamp(entity, STATUS_MODIFIED, processed_at)

    surviving = [e for e in entities if id(e) not in dropped and id(e) not in absorbed]

    # Typed values are re-derived rather than accepted from the model: a corrected value
    # can change what the number is, and an unverifiable number in an indexed numeric
    # column is exactly what the contract forbids.
    changed = [e for e in surviving if e.postprocess_status in (STATUS_MODIFIED, STATUS_MERGED)]
    if changed and type_config:
        for entity in changed:
            entity.value_kind = None
            entity.value_number = None
            entity.value_number_high = None
            entity.value_unit = None
            entity.value_date = None
            entity.value_date_high = None
        apply_semantic_normalization(changed, type_config)

    return surviving


def _extend_span(entity: NormalizedEntity, targets: list[NormalizedEntity]) -> None:
    starts = [entity.char_start] + [t.char_start for t in targets]
    ends = [entity.char_end] + [t.char_end for t in targets]
    word_starts = [entity.word_index_start] + [t.word_index_start for t in targets]
    word_ends = [entity.word_index_end] + [t.word_index_end for t in targets]
    if all(s is not None for s in starts):
        entity.char_start = min(starts)
    if all(e is not None for e in ends):
        entity.char_end = max(ends)
    if all(s is not None for s in word_starts):
        entity.word_index_start = min(word_starts)
    if all(e is not None for e in word_ends):
        entity.word_index_end = max(word_ends)
    entity.confidence = min([entity.confidence] + [t.confidence for t in targets])
    entity.occurrence_count = max([entity.occurrence_count] + [t.occurrence_count for t in targets])


# --------------------------------------------------------------------------------------
# Provider call
# --------------------------------------------------------------------------------------


def _build_client():
    from openai import AzureOpenAI, OpenAI

    if settings.azure_openai_endpoint:
        return AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    return OpenAI(api_key=settings.openai_api_key)


def call_postprocessor(system_prompt: str, user_payload: str) -> tuple[object, int]:
    """One provider call. Returns the parsed body and the tokens it consumed.

    Retries once on a transport error and honours a `Retry-After` on a rate limit; any
    other outcome raises `PostprocessUnavailable`, which the caller turns into a
    degraded — never failed — run."""
    from openai import APIError, APITimeoutError, RateLimitError

    client = _build_client()
    attempts = 0
    last_error: Exception | None = None

    while attempts < 2:
        attempts += 1
        try:
            response = client.chat.completions.create(
                model=settings.azure_openai_chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_payload},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                timeout=settings.postprocess_timeout_seconds,
            )
            content = response.choices[0].message.content
            usage = getattr(response, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) or 0
            try:
                return json.loads(content), tokens
            except (TypeError, json.JSONDecodeError) as exc:
                # Unparseable output is not retried: the same prompt at temperature 0
                # produces the same shape, so a retry spends tokens to fail again.
                raise PostprocessUnavailable(f"response was not valid JSON: {exc}") from exc
        except RateLimitError as exc:
            last_error = exc
            delay = _retry_after_seconds(exc)
            if attempts >= 2 or delay is None or delay > settings.postprocess_timeout_seconds:
                raise PostprocessUnavailable(f"rate limited: {exc}") from exc
            time.sleep(delay)
        except (APITimeoutError, APIError) as exc:
            last_error = exc
            if attempts >= 2:
                raise PostprocessUnavailable(f"provider error: {exc}") from exc

    raise PostprocessUnavailable(f"provider error: {last_error}")


def _retry_after_seconds(error: Exception) -> float | None:
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    raw = headers.get("Retry-After") or headers.get("retry-after")
    try:
        return float(raw) if raw is not None else 1.0
    except (TypeError, ValueError):
        return 1.0


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------


def postprocess_document(
    entities: list[NormalizedEntity],
    token_records: list[dict],
    type_config: dict | None,
    allowed_types: set[str],
    token_budget_remaining: int | None = None,
) -> tuple[PostprocessOutcome, int]:
    """Runs the stage for one document. Returns the outcome and the tokens consumed.

    Fail-open by construction: every failure path returns the deterministic entities
    with `postprocess_status = 'failed'` and `degraded = True`. A successful BERT
    extraction is never lost because an optional enhancement was unavailable — and the
    run that contains it completes rather than failing, since `run_batch_extraction`
    declares `max_retries=0` and a failed run is not retried."""
    indices = select_candidates(entities, type_config)
    if not indices:
        return PostprocessOutcome(entities=entities), 0

    if token_budget_remaining is not None and token_budget_remaining <= 0:
        return _degrade(entities, indices, "token budget exhausted"), 0

    candidates = build_candidates(entities, indices, token_records)

    try:
        system_prompt, user_payload = render_prompt(candidates, sorted(allowed_types))
        raw, tokens_used = call_postprocessor(system_prompt, user_payload)
        accepted, discarded = validate_decisions(raw, candidates, allowed_types)
    except PostprocessUnavailable as exc:
        logger.warning("Entity post-processing degraded: %s", exc)
        return _degrade(entities, indices, str(exc)), 0
    except Exception as exc:  # noqa: BLE001 - the stage must never fail the extraction
        logger.warning("Entity post-processing degraded on an unexpected error: %s", exc)
        return _degrade(entities, indices, str(exc)), 0

    for candidate in candidates:
        if candidate.candidate_id not in accepted:
            _stamp(candidate.entity, STATUS_FAILED, datetime.now(timezone.utc))

    surviving = apply_decisions(entities, indices, candidates, accepted, type_config)
    return PostprocessOutcome(entities=surviving, degraded=bool(discarded), discarded=discarded), tokens_used


def _degrade(entities: list[NormalizedEntity], indices: list[int], reason: str) -> PostprocessOutcome:
    processed_at = datetime.now(timezone.utc)
    for index in indices:
        entities[index].postprocess_status = STATUS_FAILED
        entities[index].postprocess_at = processed_at
    return PostprocessOutcome(entities=entities, degraded=True, discarded=[reason])
