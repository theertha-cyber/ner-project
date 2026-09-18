"""Prompt construction, response parsing, and grounding for LLM pre-labeling.

Every function here is pure: configuration and document text in, suggestions out. The provider
call lives behind `llm_client.LLMClient` and the database work lives in the Celery task, so the
part most likely to have edge-case bugs — deciding *where* in the text a quote actually is — can
be tested without a network or a database (design.md Decision 2).
"""

import json

# The keyword matcher's 0.85 reflects an exact match against a phrase the tenant configured by
# hand. Grounding guarantees an LLM suggestion's *offsets* are right, but says nothing about
# whether the label is, so LLM suggestions sit below it rather than at it. The semantics of this
# number are still an open question in design.md; it is deliberately distinguishable from the
# keyword value so downstream confidence-based routing has something to route on.
LLM_SUGGESTION_CONFIDENCE = 0.75

SUGGESTION_SOURCE_LLM = "llm"
SUGGESTION_SOURCE_KEYWORD = "keyword"

# Offsets are absent from this contract on purpose. An LLM asked to count characters gets it
# wrong in ways nothing downstream can detect, so the model is never given the opportunity:
# it returns what it saw, and `ground_quote` decides where.
SYSTEM_PROMPT = """You extract named entities from a document for a human annotator to review.

Rules you must follow exactly:
1. Find EVERY occurrence of EVERY entity type listed below that appears in the document. Do not
   stop at the first one, and do not skip an entity type because no example resembles it.
2. Each entity you return must be a VERBATIM quote copied character-for-character from the
   document text. Never paraphrase, summarise, normalise, translate, reformat, or compute a
   value. If the answer is not literally written in the document, do not return it.
3. Use only the entity type names listed below. Never invent a new entity type.
4. Do not return character positions, offsets, or indices of any kind.

Respond with JSON only, in exactly this shape:
{"entities": [{"entity_type": "<one of the listed names>", "quote": "<verbatim text>"}]}

Return {"entities": []} if the document contains none of the listed entity types."""


def build_entity_type_block(entity_types: list[dict]) -> str:
    """Renders every active entity type, with its own examples and QA pairs attached to it.

    Every type is listed whether or not it has QA pairs, and the QA pairs of one type never
    appear under another. This is what keeps QA pairs few-shot context rather than a
    questionnaire: an entity type configured with none is described by its name, description,
    and examples and is extracted on exactly the same footing (design.md Decision 3).

    The alternative — asking the model to answer the configured questions — leaves every
    unlisted type and every extra occurrence unlabelled, and `export.py` tags every uncovered
    token `O`, so partial coverage actively teaches a future model that real entities are not
    entities."""
    blocks = []
    for entity_type in entity_types:
        lines = [f"- {entity_type['name']}"]
        description = entity_type.get("description")
        if description:
            lines.append(f"  description: {description}")
        examples = entity_type.get("examples") or []
        rendered = ", ".join(f'"{example}"' for example in examples if example)
        if rendered:
            lines.append(f"  examples of values of this type: {rendered}")
        for pair in entity_type.get("qa_examples") or []:
            question = (pair or {}).get("question")
            answer = (pair or {}).get("answer")
            if question and answer:
                lines.append(f'  for illustration only — Q: "{question}" A: "{answer}"')
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def build_user_payload(
    document_text: str, entity_types: list[dict], guidance_text: str = ""
) -> str:
    """The per-document half of the prompt.

    The illustration note is repeated here rather than left to the system prompt alone: the QA
    pairs sit a few lines above it, and that adjacency is where a model is most likely to read
    them as questions about this specific document.

    `guidance_text`, when present, is reviewer guidance carried over from a Tenant Admin's
    review of an initial validation batch (Automated workflow, step 3). It is advisory prompt
    context, not a constraint on which types or how many occurrences to extract."""
    guidance_block = f"{guidance_text}\n" if guidance_text else ""
    return (
        "Entity types to extract (extract all occurrences of all of them):\n"
        f"{build_entity_type_block(entity_types)}\n\n"
        f"{guidance_block}"
        "Any Q/A lines above illustrate what a value of that entity type looks like. They are "
        "NOT questions to answer about the document below, and they do not limit which entity "
        "types or how many occurrences you extract.\n\n"
        "Document text:\n"
        "---\n"
        f"{document_text}\n"
        "---"
    )


# Fields the parser reads. Anything else the model sends — `char_start`, `start`, `offset`,
# `confidence` — is dropped here, which is the mechanism that makes it impossible for an offset
# to originate from the model even if a future prompt edit accidentally invites one.
_ALLOWED_ENTITY_FIELDS = ("entity_type", "quote")


def parse_llm_response(response) -> list[dict]:
    """The model's output reduced to `{entity_type, quote}` pairs.

    Accepts either the documented `{"entities": [...]}` envelope or a bare list, since a model
    occasionally drops the wrapper. Malformed elements are skipped rather than raising: one bad
    element should cost that one suggestion, not the whole document's worth."""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return []

    entities = response.get("entities") if isinstance(response, dict) else response
    if not isinstance(entities, list):
        return []

    parsed = []
    for element in entities:
        if not isinstance(element, dict):
            continue
        entity_type = element.get("entity_type")
        quote = element.get("quote")
        if not isinstance(entity_type, str) or not isinstance(quote, str):
            continue
        if not entity_type.strip() or not quote.strip():
            continue
        parsed.append({field: element[field] for field in _ALLOWED_ENTITY_FIELDS})
    return parsed


def ground_quote(
    document_text: str, quote: str, claimed_ranges: list[tuple[int, int]]
) -> tuple[int, int] | None:
    """Where `quote` actually is in `document_text`, or `None`.

    Exact, case-insensitive substring matching and nothing else. No fuzzy matching, no
    whitespace normalisation, no nearest-match fallback: a wrong offset is worse than a missing
    suggestion, because it either corrupts a training label silently or points a reviewer at
    text that is not what it claims to be (design.md Decision 4). A quote the model computed
    rather than copied — "5 years" from a document that only says "2019-2024" — has no exact
    match, and so is dropped here rather than force-fit somewhere plausible.

    When the quote appears more than once, the first occurrence not already claimed by another
    grounded suggestion wins, mirroring the overlap rule in `prelabel_document` (task 1.3,
    signed off in design.md).
    """
    if not quote or not document_text:
        return None

    haystack = document_text.lower()
    needle = quote.lower()

    search_from = 0
    while True:
        start = haystack.find(needle, search_from)
        if start == -1:
            return None
        end = start + len(needle)
        overlaps = any(
            start < claimed_end and end > claimed_start
            for claimed_start, claimed_end in claimed_ranges
        )
        if not overlaps:
            return start, end
        search_from = start + 1


class GroundingResult:
    """Grounded suggestions plus the counts that make the drop rate observable.

    design.md flags a high grounding drop rate as the main risk of the extractive-only contract
    — a model that paraphrases despite the prompt loses suggestions silently. `returned`,
    `grounded`, `ungrounded`, and `unconfigured_type` are carried on the job so that rate is a
    number someone can look at rather than an absence nobody notices."""

    def __init__(self, spans: list[dict], returned: int, ungrounded: int, unconfigured_type: int):
        self.spans = spans
        self.returned = returned
        self.ungrounded = ungrounded
        self.unconfigured_type = unconfigured_type

    @property
    def grounded(self) -> int:
        return len(self.spans)

    def counts(self) -> dict:
        return {
            "returned": self.returned,
            "grounded": self.grounded,
            "ungrounded": self.ungrounded,
            "unconfigured_type": self.unconfigured_type,
        }


def ground_entities(
    document_text: str, entities: list[dict], active_entity_types: list[str]
) -> GroundingResult:
    """Turns parsed LLM entities into storable suggested spans.

    Two filters, in order. An entity whose type the tenant has not configured is dropped before
    grounding — pre-labeling never creates an entity type as a side effect, matching
    `validate_entity_type`'s rule in `spans.py` that a type must already exist in
    `entity_definitions`. What survives is grounded, and what will not ground is dropped.

    Type matching is case-insensitive but the stored value is the tenant's own spelling, so a
    model that returns `PERSON_NAME` for a configured `person_name` produces a span the promote
    path and the exporter recognise."""
    canonical_by_lower = {name.lower(): name for name in active_entity_types}

    spans: list[dict] = []
    claimed_ranges: list[tuple[int, int]] = []
    ungrounded = 0
    unconfigured_type = 0

    for entity in entities:
        canonical = canonical_by_lower.get(entity["entity_type"].strip().lower())
        if canonical is None:
            unconfigured_type += 1
            continue

        located = ground_quote(document_text, entity["quote"], claimed_ranges)
        if located is None:
            ungrounded += 1
            continue

        char_start, char_end = located
        claimed_ranges.append((char_start, char_end))
        spans.append(
            {
                "entity_type": canonical,
                "char_start": char_start,
                "char_end": char_end,
                # The document's own casing, not the model's: the span must be the text that is
                # actually there, and grounding is case-insensitive.
                "text": document_text[char_start:char_end],
                "confidence": LLM_SUGGESTION_CONFIDENCE,
                "source": SUGGESTION_SOURCE_LLM,
            }
        )

    spans.sort(key=lambda span: span["char_start"])
    return GroundingResult(
        spans=spans,
        returned=len(entities),
        ungrounded=ungrounded,
        unconfigured_type=unconfigured_type,
    )
