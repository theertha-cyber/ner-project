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
import re

from src.annotation_service.services.llm_prelabel import ground_quote

# Per-document character budget for the seed set. A proposal reads a handful of documents at
# once, and a seed set of full-length documents can exceed a model's context window — at which
# point the provider truncates silently from the end and the later documents contribute nothing
# while appearing to have been read. Truncating here instead makes the loss explicit and even:
# every seed document contributes its opening section rather than the first few contributing
# everything. Entity types recur throughout a document, so the opening section is where a
# schema is visible; this is not the same trade-off as pre-labeling, which must see all of a
# document because it must find every occurrence.
SEED_DOCUMENT_CHAR_BUDGET = 15000

# How many candidates the model is asked for in discovery mode (no Q&A pair). An upper bound,
# not a target: a tenant whose documents genuinely contain four entity types should get four.
MAX_CANDIDATES = 40

# Absolute ceiling for the Q&A-driven path, where the limit is derived from how many Q&A pairs
# the tenant actually wrote. A guard against a pathological Q&A document, not a normal limit.
HARD_MAX_CANDIDATES = 80

# Headroom added to the counted Q&A-pair total: the documents occasionally surface a field the
# tenant did not think to ask about, and one or two extra candidates a reviewer can reject is
# cheaper than a missing one.
QA_CANDIDATE_HEADROOM = 5


def count_qa_pairs(qa_pair_text: str | None) -> int:
    """How many question/answer pairs the tenant's Q&A document contains.

    Tenants write these documents freely, so this counts the two shapes seen in practice and
    takes the larger: lines that open with a question marker (``Q:``, ``Q.``, ``1)``,
    ``Question 3 -``) and, failing that, question marks. Zero means "could not tell" and the
    caller falls back to the discovery-mode cap."""
    text_value = qa_pair_text or ""
    if not text_value.strip():
        return 0

    marker = re.compile(r"^\s*(?:Q\s*[:.)-]|Question\b|\d+\s*[.)])", re.IGNORECASE | re.MULTILINE)
    by_marker = len(marker.findall(text_value))
    by_question_mark = text_value.count("?")
    return max(by_marker, by_question_mark)


def resolve_max_candidates(qa_pair_text: str | None) -> int:
    """The candidate cap for this run: derived from the Q&A pair count when there is one,
    the discovery-mode default otherwise."""
    pairs = count_qa_pairs(qa_pair_text)
    if pairs <= 0:
        return MAX_CANDIDATES
    return max(1, min(pairs + QA_CANDIDATE_HEADROOM, HARD_MAX_CANDIDATES))

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


# Used instead of SYSTEM_PROMPT whenever a Q&A-pair document is attached. There the team has
# already written down exactly what they want extracted, one field per Q&A pair, so the model's
# job is not to discover a schema but to transcribe that list into entity types and attach a
# real example value to each. Where a document contains the value it is quoted from there;
# where none does, the answer the tenant wrote in the Q&A pair is used instead, so a reviewer
# always sees a concrete value.
QA_DRIVEN_SYSTEM_PROMPT_TEMPLATE = """You are configuring a named-entity recognition system
from a question/answer specification a team has written.

The Q&A document lists EXACTLY what the team wants to extract — one field per Q&A pair. Turn
that list into entity types.

Rules you must follow exactly:
1. Produce exactly one entity type for every Q&A pair, in the same order. Do not merge two
   pairs, drop a pair, or invent a pair that is not there. Produce at most %(max_candidates)d
   entity types.
2. Name each entity type with a short lowercase snake_case name derived from the question
   ("What is the candidate's email address?" -> "email_address").
3. Give each a one-sentence description of what a value of that type is.
4. For each entity type, give example values this way, in order of preference:
   a. Quote the value as it literally appears in a document — the shortest exact span that
      captures it, copied character for character. If more than one document contains a
      value, give one example from each (three documents -> three examples).
   b. If NO document shown contains the value, fall back to the answer text given for that
      pair in the Q&A specification and use it as the single example.
   Never paraphrase, translate, reformat, or compute a value.
5. Only return "examples": [] when a document has no value AND the Q&A pair gives no usable
   answer (for instance the answer says the value is not present). Still produce the entity
   type.
6. Do not return character positions, offsets, or indices of any kind.

Respond with JSON only, in exactly this shape:
{"candidates": [{"name": "<snake_case_name>", "description": "<one sentence>",
                 "examples": ["<value>", "<value>"]}]}"""


def qa_driven_system_prompt(max_candidates: int) -> str:
    return QA_DRIVEN_SYSTEM_PROMPT_TEMPLATE % {"max_candidates": max_candidates}


# Back-compat alias for callers/tests that imported the constant name.
QA_DRIVEN_SYSTEM_PROMPT = qa_driven_system_prompt(HARD_MAX_CANDIDATES)


def system_prompt_for(qa_pair_text: str | None, max_candidates: int | None = None) -> str:
    """The Q&A-driven prompt when a Q&A-pair document is attached, the discovery prompt
    otherwise. `max_candidates` defaults to the value derived from the Q&A pair."""
    if not (qa_pair_text or "").strip():
        return SYSTEM_PROMPT
    if max_candidates is None:
        max_candidates = resolve_max_candidates(qa_pair_text)
    return qa_driven_system_prompt(max_candidates)


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


def build_qa_pair_block(qa_pair_text: str | None, qa_driven: bool = False) -> str:
    """A Tenant Admin's question/answer document, verbatim.

    In discovery mode it is guidance — context about which entity types matter, not a
    grounding source. In Q&A-driven mode it is the specification itself: one entity type per
    pair, in order."""
    text_value = (qa_pair_text or "").strip()
    if not text_value:
        return ""
    if qa_driven:
        return (
            "This is the specification. Produce exactly one entity type per Q&A pair below, "
            "in this order. For each, prefer an example value quoted from the documents that "
            "follow; if no document contains the value, use the answer text from that Q&A "
            "pair as the example instead.\n"
            "--- Q&A specification ---\n"
            f"{text_value}\n"
            "--- end Q&A specification ---\n\n"
        )
    return (
        "The team also supplied this question/answer document describing what they want to "
        "extract. Use it to decide WHICH entity types to propose. It is NOT a grounding "
        "source and NOT a set of questions to answer about the documents below.\n"
        "--- Q&A ---\n"
        f"{text_value}\n"
        "--- end Q&A ---\n\n"
    )


def build_user_payload(
    seed_documents: list[dict],
    entity_types: list[dict],
    qa_pair_text: str | None = None,
    qa_driven: bool = False,
) -> str:
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

    return "{}{}Documents:\n\n{}".format(
        preamble,
        build_qa_pair_block(qa_pair_text, qa_driven=qa_driven),
        build_seed_block(seed_documents),
    )


def _normalize_for_match(value: str) -> str:
    """Lowercased, with every run of non-alphanumeric characters collapsed to a single space.

    Used only for validating a schema-proposal *example* — a display string, never an offset —
    so "8.09 / 10.0" and "8.09/10.0", or "Kerala, India" and "Kerala India", are treated as the
    same value. Pre-labeling's `ground_quote` stays strict because it produces character
    offsets; nothing here does."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _lenient_contains(haystack: str, needle: str) -> bool:
    normalized_needle = _normalize_for_match(needle)
    if not normalized_needle:
        return False
    return normalized_needle in _normalize_for_match(haystack)


def parse_proposal_response(response, max_candidates: int = MAX_CANDIDATES) -> list[dict]:
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
    for element in candidates[:max_candidates]:
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


MAX_EXAMPLES_PER_CANDIDATE = 5

# An entity type's stored examples are read back into every future pre-labeling prompt as "a
# value of this type looks like X" (llm_prelabel.build_entity_type_block) — a short illustrative
# span, not the field's full content. A Q&A answer, unlike a grounded quote, can be an entire
# paragraph (a tenant is free to write "current_role_responsibilities: <five sentences>"), and
# storing that verbatim quietly turns every later prompt into "here is a complete essay-length
# answer for this type," which measurably suppresses extraction on any document that doesn't
# resemble the one the paragraph came from (confirmed: capping examples at this length flipped
# one all-zero document to 8 correct extractions with no other prompt change).
MAX_EXAMPLE_VALUE_CHARS = 120


def _cap_example_length(example: str) -> str:
    if len(example) <= MAX_EXAMPLE_VALUE_CHARS:
        return example
    return example[:MAX_EXAMPLE_VALUE_CHARS].rstrip() + "…"


# Phrases a Q&A answer uses to say "this document has no value" — not example values. Matched
# against the whole normalised example, so "not specified in the document" is caught but a real
# value that merely contains one of these words is not.
_NON_VALUE_ANSWERS = {
    "not specified", "not specified in the document", "not mentioned", "not mentioned in the document",
    "not available", "not provided", "not present", "none", "n a", "na", "unknown", "not applicable",
}


def _is_non_value(example: str) -> bool:
    return _normalize_for_match(example) in _NON_VALUE_ANSWERS


def validate_candidate_examples(
    candidates: list[dict],
    seed_documents: list[dict],
    require_grounding: bool = True,
    lenient: bool = False,
) -> list[dict]:
    """Filter each candidate's examples to the ones actually present in a seed document.

    Discovery mode (`require_grounding=True`, `lenient=False`): an example must be a verbatim
    substring of a seed excerpt — exactly `ground_quote`'s test, so "verbatim" cannot mean one
    thing here and another in pre-labeling. A candidate left with no grounded example is
    dropped: a type the model cannot point at is the failure the verbatim rule exists to catch.

    Q&A-driven mode (`require_grounding=False`, `lenient=True`): the tenant named every field,
    so no candidate is dropped. Examples are matched leniently — whitespace and punctuation
    differences ignored — because they are display strings, not offsets, and OCR'd documents
    rarely reproduce a value's spacing exactly. A candidate that still ends up with nothing
    grounded keeps the model's own example values (which, per the prompt, fall back to the
    tenant's Q&A answer), so a reviewer always sees a concrete value to check.

    The excerpt, not the whole document, is what the model was shown, so the excerpt is what an
    example is checked against."""
    excerpts = [
        (document.get("text") or "")[:SEED_DOCUMENT_CHAR_BUDGET] for document in seed_documents
    ]

    def is_present(example: str) -> bool:
        if lenient:
            return any(_lenient_contains(excerpt, example) for excerpt in excerpts)
        return any(ground_quote(excerpt, example, []) is not None for excerpt in excerpts)

    validated = []
    for candidate in candidates:
        grounded_examples = [ex for ex in candidate["examples"] if is_present(ex)]

        if require_grounding and not grounded_examples:
            continue

        # Q&A-driven: keep the model's values (Q&A-answer fallbacks included) when nothing in
        # the documents matched, so the field is never shown with a blank value list unless the
        # model itself returned none — but drop "not specified in the document" style answers,
        # which are statements of absence, not values.
        fallback = [ex for ex in candidate["examples"] if not _is_non_value(ex)]
        examples = grounded_examples or (fallback if not require_grounding else [])

        validated.append(
            {
                "name": candidate["name"],
                "description": candidate["description"],
                "examples": [
                    _cap_example_length(ex) for ex in _dedupe(examples)[:MAX_EXAMPLES_PER_CANDIDATE]
                ],
            }
        )
    return validated


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = _normalize_for_match(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


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


def propose_candidates(
    response,
    seed_documents: list[dict],
    require_grounding: bool = True,
    max_candidates: int = MAX_CANDIDATES,
) -> ProposalResult:
    """Parse and validate in one step — what the task stores.

    On the Q&A-driven path `require_grounding` is False (every named field becomes a candidate),
    example matching is lenient, and `max_candidates` is derived from the Q&A pair count."""
    lenient = not require_grounding
    parsed = parse_proposal_response(response, max_candidates=max_candidates)
    return ProposalResult(
        candidates=validate_candidate_examples(
            parsed,
            seed_documents,
            require_grounding=require_grounding,
            lenient=lenient,
        ),
        returned=len(parsed),
        examples_returned=sum(len(candidate["examples"]) for candidate in parsed),
    )
