"""Safe-copy generation for LLM pre-labeling.

`extract_and_ground_document` (`worker.py`) is the only caller. Before it sends anything to the
external LLM provider, `mask_document` finds every span of every `pattern`- and `local_only`-
sensitivity entity type directly against the real document text, and returns a masked copy with
those spans replaced by placeholders — the copy that is actually allowed to leave the building
(ADR-015).

Two detection mechanisms, both already used elsewhere in this platform rather than invented here:
`pattern` types via their own `validation_rule` regex (pure, no I/O), and `local_only` types via
the tenant's own locally-hosted extraction model — the same `/internal/v1/infer` call and
`base_label_mapping` bridge `extraction_service.worker` already uses for production extraction,
and `src.shared.entity_views.entity_type_literals` already generalizes for both a fine-tuned
tenant (whose labels are the tenant's own type names) and a base-model tenant (PER/ORG/LOC/MISC
via `base_label_mapping`).

Local-model detection is real I/O and sits behind a `LocalModelClient` Protocol with a
`StubLocalModelClient`, mirroring `llm_client.LLMClient` / `StubLLMClient`: the provider is the
one thing tests must not reach. Pattern detection is pure and needs no stub.
"""

import re
from dataclasses import dataclass
from typing import Protocol

from src.extraction_service.services.entity_normalizer import merge_wordpieces, reconstruct_entities
from src.shared.entity_views import EntityDefinitionSpec, entity_type_literals

SENSITIVITY_OPEN = "open"
SENSITIVITY_PATTERN = "pattern"
SENSITIVITY_LOCAL_ONLY = "local_only"

SOURCE_PATTERN = "pattern"
SOURCE_LOCAL_MODEL = "local_model"

_TOKEN_RE = re.compile(r"\S+")

_PLACEHOLDER_OPEN = "⟦"  # ⟦
_PLACEHOLDER_CLOSE = "⟧"  # ⟧


class LocalDetectionUnavailable(Exception):
    """Local detection could not complete for this document — the local model was unreachable,
    or a configured `validation_rule` failed to compile. Raised rather than swallowed:
    `extract_and_ground_document` must never respond to this by falling back to sending
    unmasked text to the external LLM provider (ADR-015, fail-closed). A pre-labeling job that
    silently produced zero suggestions would be indistinguishable from a document that
    genuinely contains none of these entity types — the same reasoning `LLMUnavailable`
    (`llm_client.py`) already applies to the external provider."""


class LocalModelClient(Protocol):
    """One call: a tenant id and a list of whitespace tokens in, per-token base-model-class
    predictions out (the same shape `model_serving`'s `/internal/v1/infer` returns)."""

    def infer(self, tenant_id: str, tokens: list[str]) -> list[dict]:  # pragma: no cover
        ...


class StubLocalModelClient:
    """A client that returns canned predictions and counts its calls — the local-model
    analogue of `llm_client.StubLLMClient`. Lives beside the real client rather than in the
    test tree for the same reason `StubLLMClient` does: tests assert on `call_count` and on
    what tokens this received, both properties of the interface."""

    def __init__(
        self,
        predictions: list[dict] | None = None,
        fail: bool = False,
        fail_on: int | None = None,
    ):
        self.predictions = predictions if predictions is not None else []
        self.fail = fail
        # 1-indexed call number to fail on, for modeling one document's local-model call
        # failing in the middle of a batch rather than the whole service being down —
        # mirrors `FailingOnNthClient` for the external LLM (`test_seed_bootstrap_batch.py`).
        self.fail_on = fail_on
        self.calls: list[tuple[str, list[str]]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def infer(self, tenant_id: str, tokens: list[str]) -> list[dict]:
        self.calls.append((tenant_id, list(tokens)))
        if self.fail or self.call_count == self.fail_on:
            raise LocalDetectionUnavailable("stub configured to fail")
        return self.predictions


class ModelServingClient:
    """The configured local extraction model, reached over `model_serving`'s internal API.

    SDK/network imports are deferred to the call, matching `llm_client.AzureOpenAIClient`'s own
    reasoning: importing this module must not require a network library to be reachable at
    import time."""

    def infer(self, tenant_id: str, tokens: list[str]) -> list[dict]:
        import requests

        from src.shared.auth import create_access_token
        from src.shared.config import settings

        if not tokens:
            return []

        service_token = create_access_token(
            tenant_id=tenant_id, user_id="pii-masking-local-detector", role="system_admin",
        )
        url = f"{settings.model_serving_url.rstrip('/')}/internal/v1/infer"
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {service_token}"},
                json={"tokens": tokens},
                timeout=60,
            )
            response.raise_for_status()
        except Exception as exc:
            raise LocalDetectionUnavailable(f"local model unavailable: {exc}") from exc

        return response.json().get("predictions", [])


def get_local_model_client() -> LocalModelClient:
    return ModelServingClient()


def find_uncovered_local_only_type(entity_types: list[dict]) -> str | None:
    """The name of the first active `local_only` entity type with no `base_label_mapping`
    configured, or `None` if every `local_only` type has one.

    `base_label_mapping` is the explicit signal that someone has told the system how to
    recognize this type locally — a fine-tuned tenant's model may organically predict a label
    matching the type's own name with no mapping at all (`entity_type_literals` covers that
    case for detection itself), but requiring the mapping here is a deliberate, conservative
    gate: pre-labeling must not run for a `local_only` type nobody has confirmed is locally
    detectable, because the alternative is silently sending its real values externally — the
    exact exposure this mechanism exists to prevent."""
    for entity_type in entity_types:
        if entity_type.get("sensitivity") != SENSITIVITY_LOCAL_ONLY:
            continue
        if not entity_type.get("base_label_mapping"):
            return entity_type["name"]
    return None


def detect_pattern_spans(document_text: str, entity_types: list[dict]) -> list[dict]:
    """Every span of every `pattern`-sensitivity entity type, found via its own
    `validation_rule` regex. Pure — no model, no network.

    Raises `LocalDetectionUnavailable` if a configured `validation_rule` fails to compile,
    rather than silently matching nothing for that type — a `pattern` type is sensitive
    precisely because its values must never reach the external LLM, so a broken detector for
    it is a reason to stop, not a reason to extract that type as if it had no pattern at all."""
    spans = []
    for entity_type in entity_types:
        if entity_type.get("sensitivity") != SENSITIVITY_PATTERN:
            continue
        rule = entity_type.get("validation_rule")
        if not rule:
            continue
        try:
            compiled = re.compile(rule)
        except re.error as exc:
            raise LocalDetectionUnavailable(
                f"validation_rule for '{entity_type['name']}' failed to compile: {exc}"
            ) from exc
        for match in compiled.finditer(document_text):
            if match.start() == match.end():
                continue
            spans.append(
                {
                    "entity_type": entity_type["name"],
                    "char_start": match.start(),
                    "char_end": match.end(),
                    "text": document_text[match.start():match.end()],
                    "confidence": 1.0,
                    "source": SOURCE_PATTERN,
                }
            )
    return spans


def _tokenize(document_text: str) -> list[dict]:
    """Whitespace tokens with absolute character offsets, matching the tokenizer
    `extraction_service.worker` uses for production extraction, so the same model is fed
    comparable input."""
    return [
        {"token": m.group(0), "char_start": m.start(), "char_end": m.end()}
        for m in _TOKEN_RE.finditer(document_text)
    ]


def _align(predictions: list[dict], token_records: list[dict]) -> list[dict]:
    """Attaches char_start/char_end from `token_records` to each prediction: by `word_index`
    when present (the fine-tuned path, exact), or by scanning forward for matching token text
    (the base-model WordPiece path). The same two-path alignment
    `extraction_service.worker._align_predictions_with_offsets` uses — reproduced here rather
    than imported across the service boundary, since that function lives in a Celery worker
    module rather than a pure `services/` one. A prediction that cannot be placed gets `None`
    offsets rather than aborting; `reconstruct_entities` drops what it cannot locate."""
    aligned = []
    ptr = 0
    n = len(token_records)
    for pred in predictions:
        word_index = pred.get("word_index")
        if word_index is not None and 0 <= word_index < n:
            record = token_records[word_index]
            merged = dict(pred)
            merged["char_start"] = record["char_start"]
            merged["char_end"] = record["char_end"]
            aligned.append(merged)
            ptr = word_index + 1
            continue

        tok_text = pred.get("token", "")
        found_idx = None
        for i in range(ptr, n):
            if token_records[i]["token"] == tok_text:
                found_idx = i
                break
        merged = dict(pred)
        if found_idx is not None:
            merged["char_start"] = token_records[found_idx]["char_start"]
            merged["char_end"] = token_records[found_idx]["char_end"]
            ptr = found_idx + 1
        else:
            merged["char_start"] = None
            merged["char_end"] = None
        aligned.append(merged)
    return aligned


def detect_local_only_spans(
    document_text: str,
    entity_types: list[dict],
    client: LocalModelClient,
    tenant_id: str,
) -> list[dict]:
    """Every span of every `local_only`-sensitivity entity type, found by the tenant's own
    locally-hosted extraction model. Offsets are against `document_text` directly — nothing
    here is masked yet.

    Raises `LocalDetectionUnavailable` (propagated from `client.infer`) if the model cannot be
    reached. Returning an empty list must only ever mean "the model ran and found nothing",
    never "the call failed" — the two are not interchangeable under fail-closed."""
    local_only_types = [
        et for et in entity_types if et.get("sensitivity") == SENSITIVITY_LOCAL_ONLY
    ]
    if not local_only_types:
        return []

    token_records = _tokenize(document_text)
    tokens = [t["token"] for t in token_records]
    if not tokens:
        return []

    raw_predictions = client.infer(tenant_id, tokens)
    aligned = _align(raw_predictions, token_records)
    merged = merge_wordpieces(aligned)
    entities = reconstruct_entities(merged, token_records)

    literal_to_type: dict[str, str] = {}
    for entity_type in local_only_types:
        spec = EntityDefinitionSpec(
            name=entity_type["name"],
            sql_identifier=None,
            base_label_mapping=entity_type.get("base_label_mapping"),
        )
        for literal in entity_type_literals(spec):
            literal_to_type[literal] = entity_type["name"]

    spans = []
    for entity in entities:
        canonical = literal_to_type.get((entity.entity_type or "").strip().upper())
        if canonical is None or entity.char_start is None or entity.char_end is None:
            continue
        spans.append(
            {
                "entity_type": canonical,
                "char_start": entity.char_start,
                "char_end": entity.char_end,
                "text": document_text[entity.char_start:entity.char_end],
                "confidence": entity.confidence,
                "source": SOURCE_LOCAL_MODEL,
            }
        )
    return spans


def _resolve_overlaps(spans: list[dict]) -> list[dict]:
    """First-claimed, lowest-offset span wins — the same overlap rule `ground_entities`
    (`llm_prelabel.py`) already applies to LLM suggestions, reused here so a pattern match and
    a local-model match that disagree about the same characters resolve the same way an LLM
    disagreeing with itself would."""
    resolved = []
    claimed_end = -1
    for span in sorted(spans, key=lambda s: s["char_start"]):
        if span["char_start"] < claimed_end:
            continue
        resolved.append(span)
        claimed_end = span["char_end"]
    return resolved


@dataclass
class MaskingResult:
    """`masked_text` is what may be sent to the external LLM provider. `local_spans` are
    already-grounded suggestions (correct offsets against the original document) that never
    go anywhere near the external call. `segments` is the offset-translation table:
    `(orig_start, orig_end, masked_start, masked_end)` for every *unmasked* stretch of text, in
    order — `translate_offset` uses it to map a location the external LLM's quote grounded to
    (in `masked_text`) back to the original document."""

    masked_text: str
    local_spans: list[dict]
    segments: list[tuple[int, int, int, int]]


def mask_document(
    document_text: str,
    entity_types: list[dict],
    local_model_client: LocalModelClient,
    tenant_id: str,
) -> MaskingResult:
    """The whole safe-copy pipeline: detect, resolve overlaps, replace with placeholders.

    A tenant with no `pattern`/`local_only` entity types gets a masked copy identical to the
    original — no detector runs, no local-model call is made, and nothing about today's
    behavior changes for them."""
    pattern_spans = detect_pattern_spans(document_text, entity_types)
    local_model_spans = detect_local_only_spans(
        document_text, entity_types, local_model_client, tenant_id
    )
    local_spans = _resolve_overlaps(pattern_spans + local_model_spans)

    placeholder_by_text: dict[str, str] = {}
    counters: dict[str, int] = {}

    masked_parts: list[str] = []
    segments: list[tuple[int, int, int, int]] = []
    cursor = 0
    masked_cursor = 0

    for span in local_spans:
        gap = document_text[cursor:span["char_start"]]
        if gap:
            masked_parts.append(gap)
            segments.append((cursor, span["char_start"], masked_cursor, masked_cursor + len(gap)))
            masked_cursor += len(gap)

        placeholder = placeholder_by_text.get(span["text"])
        if placeholder is None:
            entity_label = span["entity_type"].upper()
            counters[entity_label] = counters.get(entity_label, 0) + 1
            placeholder = (
                f"{_PLACEHOLDER_OPEN}{entity_label}_{counters[entity_label]}{_PLACEHOLDER_CLOSE}"
            )
            placeholder_by_text[span["text"]] = placeholder
        masked_parts.append(placeholder)
        masked_cursor += len(placeholder)
        cursor = span["char_end"]

    tail = document_text[cursor:]
    if tail:
        masked_parts.append(tail)
        segments.append((cursor, len(document_text), masked_cursor, masked_cursor + len(tail)))

    return MaskingResult(
        masked_text="".join(masked_parts), local_spans=local_spans, segments=segments
    )


def translate_offset(
    masked_start: int, masked_end: int, segments: list[tuple[int, int, int, int]]
) -> tuple[int, int] | None:
    """Maps a `[masked_start, masked_end)` range in the masked copy back to the corresponding
    range in the original document, using `MaskingResult.segments`. Returns `None` when the
    range is not entirely contained in one unmasked segment — it either falls inside a
    placeholder or straddles one — so the caller discards it rather than storing a corrupted
    offset, the same "a wrong offset is worse than a missing suggestion" principle
    `ground_quote` (`llm_prelabel.py`) already applies."""
    for orig_start, _orig_end, seg_start, seg_end in segments:
        if seg_start <= masked_start and masked_end <= seg_end:
            shift = orig_start - seg_start
            return masked_start + shift, masked_end + shift
    return None
