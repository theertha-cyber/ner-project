"""Prompt construction, response parsing, and example validation for entity schema proposal.

The mirror image of `llm_prelabel`: there the tenant's entity types are an input and spans are
the output; here the entity types are the output. Everything else is deliberately the same
shape. The functions are pure — seed text and configuration in, candidates out — the provider
call lives behind `llm_client.LLMClient`, and the database work lives in the Celery task, so the
part most likely to be wrong (deciding whether an example is really in the document) can be
tested without a network or a database.

The one rule this module exists to enforce is that a proposal is a *proposal*. Nothing here
creates, modifies, or activates an entity type; the candidates it returns are rows a human
approves before the existing entity-config API is asked to create anything (design.md
Decision 1).
"""

import json

from src.annotation_service.services.llm_prelabel import ground_quote

# Per-document character budget for the seed set. A proposal reads a handful of documents at
# once, and a seed set of full-length documents can exceed a model's context window — at which
# point the provider truncates silently from the end and the later documents contribute nothing
# while appearing to have been read. Truncating here instead makes the loss explicit and even:
# every seed document contributes its opening section rather than the first few contributing
# everything. Entity types recur throughout a document, so the opening section is where a
# schema is visible; this is not the same trade-off as pre-labeling, which must see all of a
# document because it must find every occurrence.
SEED_DOCUMENT_CHAR_BUDGET = 6000

# How many candidates the model is asked for. An upper bound, not a target: a tenant whose
# documents genuinely contain four entity types should get four.
MAX_CANDIDATES = 15

SYSTEM_PROMPT = """You are helping a team work out which entity types their documents contain,
so they can configure a named-entity recognition system.

You will be shown excerpts from several documents of the same kind. Propose the entity types
that a human annotator would need in order to label these documents.

Rules you must follow exactly:
1. Propose entity types that actually appear in the documents shown. Do not propose a type
   because it is common in documents of this kind — propose it because you can point at it.
2. Every example value you give must be a VERBATIM quote copied character-for-character from
   one of the documents shown. Never paraphrase, summarise, normalise, translate, reformat, or
   compute a value. If you cannot quote it, do not give it.
3. Give each entity type a short lowercase snake_case name and a one-sentence description of
   what a value of that type is.
4. Give at least two example values per entity type where the documents contain that many.
5. Propose at most %(max_candidates)d entity types. Prefer the types a human would actually
   want to extract over exhaustive coverage.
6. Do not return character positions, offsets, or indices of any kind.

Respond with JSON only, in exactly this shape:
{"candidates": [{"name": "<snake_case_name>", "description": "<one sentence>",
                 "examples": ["<verbatim quote>", "<verbatim quote>"]}]}

Return {"candidates": []} if the documents contain no extractable entities.""" % {
    "max_candidates": MAX_CANDIDATES
}


def build_seed_block(seed_documents: list[dict]) -> str:
    """The seed documents, numbered and truncated to the per-document budget.

    Numbered rather than identified by id: the model has no use for a UUID, and giving it one
    invites it to quote the id back as if it were document content."""
    blocks = []
    for index, document in enumerate(seed_documents, start=1):
        excerpt = (document.get("text") or "")[:SEED_DOCUMENT_CHAR_BUDGET]
        blocks.append("--- Document {} ---\n{}".format(index, excerpt))
    return "\n\n".join(blocks)


def build_existing_config_block(entity_types: list[dict]) -> str:
    """What the tenant has already configured, so the model does not re-propose it.

    Their QA pairs come along because they are the clearest statement a tenant has made about
    what they care about extracting — the same few-shot role they play in pre-labeling, used
    here to characterise the tenant's interest rather than to label a document. A tenant with
    nothing configured yet is the ordinary case and produces an empty block."""
    if not entity_types:
        return ""

    lines = []
    for entity_type in entity_types:
        lines.append("- {}".format(entity_type["name"]))
        description = entity_type.get("description")
        if description:
            lines.append("  description: {}".format(description))
        for pair in entity_type.get("qa_examples") or []:
            question = (pair or {}).get("question")
            answer = (pair or {}).get("answer")
            if question and answer:
                lines.append('  Q: "{}" A: "{}"'.format(question, answer))
    return "\n".join(lines)


def build_user_payload(seed_documents: list[dict], entity_types: list[dict]) -> str:
    """The whole per-request half of the prompt."""
    existing = build_existing_config_block(entity_types)
    if existing:
        preamble = (
            "This team has already configured the entity types below. Do NOT propose any of "
            "them again. Any Q/A lines show the kind of value they care about — they are "
            "context about this team's interests, not questions to answer about the documents.\n"
            "{}\n\n".format(existing)
        )
    else:
        preamble = "This team has not configured any entity types yet.\n\n"

    return "{}Documents:\n\n{}".format(preamble, build_seed_block(seed_documents))


def parse_proposal_response(response) -> list[dict]:
    """The model's output reduced to `{name, description, examples}` candidates.

    Only those three fields are read; anything else the model sends is dropped by construction,
    the same mechanism `llm_prelabel.parse_llm_response` uses to make it impossible for an
    offset to originate from the model even if a future prompt edit accidentally invites one.

    Accepts either the documented `{"candidates": [...]}` envelope or a bare list, since a model
    occasionally drops the wrapper. Malformed elements are skipped rather than raising: one bad
    candidate should cost that one candidate, not the whole proposal."""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return []

    candidates = response.get("candidates") if isinstance(response, dict) else response
    if not isinstance(candidates, list):
        return []

    parsed = []
    for element in candidates[:MAX_CANDIDATES]:
        if not isinstance(element, dict):
            continue
        name = element.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        description = element.get("description")
        examples = element.get("examples")
        parsed.append(
            {
                "name": name.strip(),
                "description": description.strip() if isinstance(description, str) else None,
                "examples": [
                    example.strip()
                    for example in (examples if isinstance(examples, list) else [])
                    if isinstance(example, str) and example.strip()
                ],
            }
        )
    return parsed


def validate_candidate_examples(candidates: list[dict], seed_documents: list[dict]) -> list[dict]:
    """Drop every example that is not verbatim in some seed document, and every candidate left
    without one.

    `ground_quote` is imported rather than reimplemented, and that is the point: an example is
    validated by exactly the test a pre-labeled span is grounded by, so "verbatim" cannot come
    to mean one thing on this path and another on that one (task 2.3). The claimed-ranges
    argument is empty because nothing here is claiming territory in the document — two
    candidates may legitimately quote the same words, and only the presence of the text matters.

    The excerpt, not the whole document, is what the model was shown, so the excerpt is what an
    example is checked against. Checking against the full text would pass a quote the model
    could not have read and must therefore have invented.

    A candidate whose every example is discarded is itself discarded. An entity type the model
    cannot point at in the documents is the exact failure the verbatim rule exists to catch,
    and forwarding it to a human as a nameless plausible-sounding suggestion wastes their
    attention on the model's least reliable output."""
    excerpts = [
        (document.get("text") or "")[:SEED_DOCUMENT_CHAR_BUDGET] for document in seed_documents
    ]

    validated = []
    for candidate in candidates:
        grounded_examples = [
            example
            for example in candidate["examples"]
            if any(ground_quote(excerpt, example, []) is not None for excerpt in excerpts)
        ]
        if not grounded_examples:
            continue
        validated.append(
            {
                "name": candidate["name"],
                "description": candidate["description"],
                "examples": grounded_examples,
            }
        )
    return validated


class ProposalResult:
    """Validated candidates plus the counts behind them.

    The same reasoning as `llm_prelabel.GroundingResult`: a model that invents entity types it
    cannot quote loses them silently, and a returned-vs-kept ratio nobody can read is a risk
    nobody can see."""

    def __init__(self, candidates: list[dict], returned: int, examples_returned: int):
        self.candidates = candidates
        self.returned = returned
        self.examples_returned = examples_returned

    @property
    def examples_kept(self) -> int:
        return sum(len(candidate["examples"]) for candidate in self.candidates)

    def counts(self) -> dict:
        return {
            "candidates_returned": self.returned,
            "candidates_kept": len(self.candidates),
            "examples_returned": self.examples_returned,
            "examples_kept": self.examples_kept,
        }


def propose_candidates(response, seed_documents: list[dict]) -> ProposalResult:
    """Parse and validate in one step — what the task stores."""
    parsed = parse_proposal_response(response)
    return ProposalResult(
        candidates=validate_candidate_examples(parsed, seed_documents),
        returned=len(parsed),
        examples_returned=sum(len(candidate["examples"]) for candidate in parsed),
    )
