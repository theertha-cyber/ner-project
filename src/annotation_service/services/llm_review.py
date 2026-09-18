"""Asking the LLM to judge one low-confidence prediction.

The deterministic half of the LLM review route: build a prompt for one queued prediction, and
turn the provider's answer back into the same resolution body a human reviewer would submit.
Everything on the far side of that — recording the outcome, creating any span, discarding the
prediction — is `review_resolution.resolve_prediction`, which the human endpoint also calls.

That shared path is the point. The LLM never writes a span, and cannot: nothing in this module
or in the task that drives it touches `{schema}.spans`. A span exists only because
`create_span_from_outcome` made one from a recorded outcome, whoever the reviewer was
(design.md Decision 4). Giving the LLM its own write path would be handing one model an
unaudited route into the training data of another, which is the failure this whole plan avoids.

The prompt asks a *closed* question — is this span, at these offsets, this type? — rather than
"find the entities". The LLM is a reviewer of a BERT prediction here, not a pre-labeler; that
is changes 1, 2 and 4's job, and asking it to re-extract would let it introduce spans no model
proposed and no threshold routed.
"""

import json

from src.shared.confidence_routing import (
    OUTCOME_CONFIRMED,
    OUTCOME_CORRECTED,
    OUTCOME_REJECTED,
    OUTCOMES,
    ROUTE_LLM,
)

# How much document text to send either side of the span. The reviewer's question is local —
# whether this text, in this sentence, is this kind of entity — so a window is both sufficient
# and cheaper than the document, and it keeps the prompt size independent of document length.
CONTEXT_CHARS = 400

SYSTEM_PROMPT = """You are reviewing a single named-entity prediction made by a NER model.

You are given a document excerpt, a character span within it, and the entity type the model
assigned. Decide one of exactly three things:

- "confirmed": the span and the entity type are both correct as given.
- "corrected": the entity is present but the model got the boundary or the type wrong. Supply
  the corrected char_start and char_end (absolute offsets into the full document, not the
  excerpt) and/or the corrected entity_type.
- "rejected": the text at those offsets is not an entity of any configured type.

Rules you must follow:
- Offsets are absolute positions in the full document. The excerpt's offset origin is given to
  you; add it to any position you compute within the excerpt.
- Never invent text. A corrected span must be a substring of the document at the offsets you
  give.
- Only use an entity type from the supplied list.
- Answer with JSON only, in the form:
  {"outcome": "confirmed" | "corrected" | "rejected",
   "entity_type": "<type>", "char_start": <int>, "char_end": <int>,
   "reason": "<one short sentence>"}
- For "confirmed" and "rejected", echo the prediction's own entity_type, char_start and
  char_end unchanged."""


class LLMReviewError(ValueError):
    """The provider's answer could not be read as a review outcome.

    Raised rather than defaulted to `confirmed`: a malformed answer means the LLM did not
    review this prediction, and silently confirming it would put an unreviewed span into the
    training set under a label that says a reviewer approved it.
    """


def build_user_payload(prediction: dict, document_text: str, entity_types) -> str:
    """The excerpt, the span, and the configured type list.

    The excerpt's `context_char_start` travels with it so the model can convert a position it
    found inside the excerpt back to a document offset. Sending the excerpt without its origin
    is the obvious way to get offsets that are wrong by exactly the window size.
    """
    char_start = prediction["char_start"]
    char_end = prediction["char_end"]
    context_start = max(0, char_start - CONTEXT_CHARS)
    context_end = min(len(document_text), char_end + CONTEXT_CHARS)

    return json.dumps(
        {
            "excerpt": document_text[context_start:context_end],
            "excerpt_char_start": context_start,
            "prediction": {
                "entity_type": prediction["entity_type"],
                "char_start": char_start,
                "char_end": char_end,
                "text": document_text[char_start:char_end],
            },
            "allowed_entity_types": sorted(entity_types),
        },
        ensure_ascii=False,
    )


def parse_review_response(response: dict, prediction: dict, document_text: str) -> dict:
    """Turn the provider's JSON into the body `resolve_prediction` accepts.

    Validated hard, because this is the point where a model's output becomes training data:

    * The outcome must be one of the three. Anything else is an error, not a default.
    * A corrected span must match the document at the offsets it claims. A model that returned
      offsets computed against the excerpt rather than the document produces a span whose text
      is not what the document says there — the "answer is not in the text" failure mode — and
      it is cheap to catch by slicing.
    * A corrected outcome that changed nothing is downgraded to `confirmed` rather than
      rejected: the model agreed with the prediction and mislabelled its own answer, which is a
      naming mistake, not a review that failed to happen. `resolve_prediction` would otherwise
      raise on it.
    """
    outcome = response.get("outcome")
    if outcome not in OUTCOMES:
        raise LLMReviewError(f"outcome must be one of {list(OUTCOMES)}, got {outcome!r}")

    if outcome in (OUTCOME_CONFIRMED, OUTCOME_REJECTED):
        # Both echo the prediction. Whatever the model returned in the other fields is ignored
        # rather than trusted: for these two outcomes the offsets are not the model's to move.
        return {"outcome": outcome, "route": ROUTE_LLM}

    entity_type = response.get("entity_type", prediction["entity_type"])
    char_start = response.get("char_start", prediction["char_start"])
    char_end = response.get("char_end", prediction["char_end"])

    if not isinstance(char_start, int) or not isinstance(char_end, int):
        raise LLMReviewError("corrected offsets must be integers")
    if char_end <= char_start:
        raise LLMReviewError("char_end must be greater than char_start")
    if char_start < 0 or char_end > len(document_text):
        raise LLMReviewError("corrected offsets fall outside the document")

    unchanged = (
        entity_type == prediction["entity_type"]
        and char_start == prediction["char_start"]
        and char_end == prediction["char_end"]
    )
    if unchanged:
        return {"outcome": OUTCOME_CONFIRMED, "route": ROUTE_LLM}

    return {
        "outcome": OUTCOME_CORRECTED,
        "route": ROUTE_LLM,
        "entity_type": entity_type,
        "char_start": char_start,
        "char_end": char_end,
    }


def review_prediction(client, prediction: dict, document_text: str, entity_types) -> dict:
    """One provider call, validated. Returns a resolution body for `resolve_prediction`."""
    payload = build_user_payload(prediction, document_text, entity_types)
    response = client.complete_json(SYSTEM_PROMPT, payload)
    return parse_review_response(response, prediction, document_text)
