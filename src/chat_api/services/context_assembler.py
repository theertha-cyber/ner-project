import json
from dataclasses import dataclass, field

from src.shared.config import settings
from src.shared.conversation_history import render_history
from src.shared.retrieval.chunking import TOKENIZER
from src.shared.retrieval.models import RetrievalResult

_PROMPT_HEAD = """You are a helpful chatbot for a multi-tenant Named Entity Recognition (NER) platform.
You have access to the tenant's extracted entity data and document context.
Always answer based on the provided context data. Do not make up information.
When citing sources, reference the specific document or entity source.
If you cannot find relevant information, say so clearly.
Never reveal data from other tenants.
Format your response naturally and conversationally.
"""

# The exhaustiveness claim is only true when the block really is the whole result. It
# was asserted unconditionally, so a query truncated by `LIMIT 100` — or a block the
# assembler trimmed for budget — was still presented to the model as the complete set.
EXHAUSTIVE_ENTITY_INSTRUCTION = """
An `Entity data:` block, when present, is the complete result of a database query run
against the tenant's extracted entities specifically to answer this question. Treat it as
authoritative and exhaustive: when the question asks what something contains, lists, or
has, report EVERY distinct value in that block. Collapse exact duplicates of the same
value, but never drop a distinct one and never shorten the list because it seems long or
repetitive — an omitted value reads as "this isn't in the document", which is wrong.
Document passages alongside it add context and wording, and may mention things the
extractor did not capture; you may include those, but say where they came from, and never
let them replace or abbreviate the entity list.
"""

PARTIAL_ENTITY_INSTRUCTION = """
An `Entity data:` block, when present, is the result of a database query run against the
tenant's extracted entities specifically to answer this question — but for THIS turn it
is PARTIAL, and the block itself says how partial. Report every distinct value it does
contain, and say plainly that the list is incomplete and how many rows matched in total.
Do NOT present it as the complete set, do NOT state or imply that a value absent from it
is absent from the data, and do NOT count, total, or rank over it as though it were the
whole result. Document passages alongside it add context and wording; you may include
those, but say where they came from.
"""

_PROMPT_TAIL = """
A `Conversation history:` block, when present, is what you and the user already
established, and the question may depend on it. When the question restricts itself to
something an earlier turn named — "which of the following candidates", "of those",
"compare the two", "any of them" — those earlier subjects are the entire set you may
answer about. Answer for each of them and for no one else: introducing a subject the user
did not ask about contradicts the conversation, and dropping one leaves the question half
answered. Retrieval may return rows about other subjects, because it searches more
broadly than the question does; ignore them. If the context data holds no evidence for one
of the named subjects, say that about that subject rather than substituting someone else.

Identify every subject by its name. `document_id` values are opaque internal
identifiers — never present one to the user as a candidate, a person, or a subject's
name. When a row carries no name, refer to the source by its document name or filename,
and say the name was not extracted."""


def build_system_prompt(entity_data_is_complete: bool = True) -> str:
    """The system prompt, with the entity-data instruction matching what was admitted."""
    instruction = (
        EXHAUSTIVE_ENTITY_INSTRUCTION if entity_data_is_complete else PARTIAL_ENTITY_INSTRUCTION
    )
    return _PROMPT_HEAD + instruction + _PROMPT_TAIL


# The complete-result prompt, kept as a module constant because tests and the budget
# accounting both refer to it by name.
SYSTEM_PROMPT = build_system_prompt(True)


PART_SEPARATOR = "\n\n"


def _count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text))


# Each context part after the first is joined to the previous one by PART_SEPARATOR.
# Those separators are part of the rendered prompt, so admission has to pay for them:
# charging only the parts themselves under-reserves by a token per join, and a context
# that fills its budget then renders slightly over the limit it was assembled against.
_SEPARATOR_TOKENS = _count_tokens(PART_SEPARATOR)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    tokens = TOKENIZER.encode(text)
    return TOKENIZER.decode(tokens[:max_tokens])


def _label_for(chunk: RetrievalResult, document_names: dict[str, str]) -> str:
    name = document_names.get(chunk.document_id) or chunk.document_id
    if chunk.page_number is not None:
        return f'Document "{name}" (page {chunk.page_number}):'
    return f'Document "{name}":'


def _dedupe_chunks(chunks: list[RetrievalResult]) -> list[str]:
    """Returns rendered chunk text (label + body), overlap-trimmed. Never mutates inputs."""
    texts = [c.chunk_text for c in chunks]

    by_doc: dict[str, list[int]] = {}
    for i, c in enumerate(chunks):
        by_doc.setdefault(c.document_id, []).append(i)

    for indices in by_doc.values():
        by_chunk_index = {chunks[i].chunk_index: i for i in indices}
        for i in indices:
            cur = chunks[i]
            prev_i = by_chunk_index.get(cur.chunk_index - 1)
            if prev_i is None:
                continue
            prev_text = texts[prev_i]
            cur_text = texts[i]
            overlap_len = _shared_boundary_length(prev_text, cur_text)
            if overlap_len > 0:
                texts[i] = cur_text[overlap_len:]

    for indices in by_doc.values():
        by_chunk_index: dict[int, list[int]] = {}
        for i in indices:
            by_chunk_index.setdefault(chunks[i].chunk_index, []).append(i)
        for same_index_positions in by_chunk_index.values():
            for a_pos, i in enumerate(same_index_positions):
                for j in same_index_positions[a_pos + 1:]:
                    if texts[i] and texts[j] and texts[i] == texts[j]:
                        texts[j] = ""

    return texts


def _shared_boundary_length(prev_text: str, cur_text: str) -> int:
    max_check = min(len(prev_text), len(cur_text))
    for length in range(max_check, 0, -1):
        if prev_text[-length:] == cur_text[:length]:
            return length
    return 0


# A failure explained in a hundred characters is as useful to the answer model as one
# explained in a thousand, and the budget it spends comes out of the evidence.
MAX_STATUS_ERROR_CHARS = 200

RETRIEVAL_STATUS_PREAMBLE = (
    "Retrieval status: part of this turn's retrieval did not complete, so the context "
    "below is incomplete. Answer from what is here, and do NOT state or imply that the "
    "missing information is absent from the data — it was not looked up successfully."
)


def _bounded(text: str | None) -> str:
    value = (text or "").strip()
    if len(value) > MAX_STATUS_ERROR_CHARS:
        return value[: MAX_STATUS_ERROR_CHARS - 1].rstrip() + "…"
    return value


def render_retrieval_status(status) -> str | None:
    """Renders the turn's retrieval outcome for the answer model, or None when every
    attempted capability succeeded or legitimately found nothing.

    This is the reader that `sql_error` / `retrieval_error` never had. Without it a
    failed source and an empty one look identical to the generation model, which is why
    a broken turn came back as "I couldn't find that in your data"."""
    if status is None:
        return None

    lines: list[str] = []
    for entry in status.failures():
        detail = _bounded(entry.error)
        suffix = f" ({detail})" if detail else ""
        lines.append(f"- The `{entry.capability_name}` source FAILED for this turn{suffix}.")
    for entry in status.skips():
        detail = _bounded(entry.reason)
        suffix = f" ({detail})" if detail else ""
        lines.append(f"- A `{entry.capability_name}` recovery step was SKIPPED{suffix}.")
    if status.planning_degraded:
        detail = _bounded(status.stop_reason)
        suffix = f" ({detail})" if detail else ""
        lines.append(f"- Retrieval planning DEGRADED to a fallback plan{suffix}.")

    if not lines:
        return None
    return RETRIEVAL_STATUS_PREAMBLE + "\n" + "\n".join(lines)


@dataclass
class AdmittedEvidence:
    """Exactly what prompt assembly put in front of the model.

    Citations are derived from this, so the evidence the user is shown and the evidence
    the answer was written from are the same set. Previously `source_assembly` sliced
    chunks at 3 while the assembler admitted 5 and could drop the structured block
    whole — so citations and evidence disagreed in both directions, and a citation could
    survive for a block the prompt never contained."""

    chunks: list[RetrievalResult] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    rows_truncated: bool = False
    matched_rows: int | None = None
    structured_admitted: bool = False

    @property
    def structured_complete(self) -> bool:
        if not self.structured_admitted:
            return True
        if self.rows_truncated:
            return False
        # An unknown total is not a complete one: the prompt must not claim
        # exhaustiveness on evidence nobody could size.
        return self.matched_rows is not None and self.matched_rows <= len(self.rows)


def collapse_duplicate_rows(rows: list[dict]) -> list[dict]:
    """Drops exact duplicate rendered rows, preserving order.

    The row budget buys more distinct information this way — the observed
    "Who knows AWS?" result returned four identical rows. Collapse is keyed on the
    FULL rendered row, so the same value from two documents survives as two rows:
    provenance is exactly what makes those rows distinct."""
    seen: set[str] = set()
    collapsed: list[dict] = []
    for row in rows:
        key = json.dumps(row, default=str, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(row)
    return collapsed


def render_structured_block(rows: list[dict], matched: int | None, truncated: bool) -> str:
    """The `Entity data:` block with an explicit statement of what it holds.

    The marker is what stops the model claiming completeness it does not have."""
    if matched is None:
        completeness = f"showing {len(rows)} row(s); the total matched is unknown"
    elif truncated or matched > len(rows):
        completeness = f"showing {len(rows)} of {matched} matched row(s) — PARTIAL"
    else:
        completeness = f"showing all {len(rows)} matched row(s)"
    return f"Entity data ({completeness}): {json.dumps(rows, default=str)}"


class ContextAssembler:
    def __init__(self, token_budget: int | None = None, max_chunks: int | None = None):
        self.token_budget = token_budget if token_budget is not None else settings.context_token_budget
        self.max_chunks = max_chunks if max_chunks is not None else settings.context_max_chunks

    def assemble(
        self,
        message: str,
        sql_results: list[dict] | None,
        chunks: list[RetrievalResult] | None,
        document_names: dict[str, str] | None,
        conversation_context: list[dict] | None,
        retrieval_status=None,
        sql_completeness: dict | None = None,
        return_evidence: bool = False,
    ):
        """Builds the generation prompt. Returns the messages, or
        `(messages, AdmittedEvidence)` when `return_evidence` is set.

        The default return shape is unchanged so existing callers and tests are
        unaffected; `prompt_assembly_node` asks for the evidence because
        `source_assembly` derives citations from it."""
        document_names = document_names or {}
        chunks = (chunks or [])[: self.max_chunks]
        evidence = AdmittedEvidence()

        query_truncated = bool((sql_completeness or {}).get("truncated"))
        # No completeness report at all means the caller handed over the whole result —
        # the rows are the answer. `matched: None` inside a report is different: the
        # retrieval layer looked and could not determine the total, and says so.
        matched_total = (sql_completeness or {}).get("matched")
        matched_is_unknown = sql_completeness is not None and matched_total is None

        # Whether the structured block is complete decides which entity-data
        # instruction the system prompt carries, and the prompt's own token cost.
        # Assume complete, then re-derive once admission is known.
        system_prompt = SYSTEM_PROMPT
        overhead = _count_tokens(system_prompt)
        overhead += _count_tokens(f"Context data:\n\n\nQuestion: {message}")

        conv_history = render_history(conversation_context)
        if conv_history:
            overhead += _count_tokens(f"Conversation history:\n{conv_history}")

        remaining = self.token_budget - overhead
        context_parts: list[str] = []

        # Charged before any evidence: the model has to know the context is incomplete
        # even on the turns where the budget is tightest, and those are exactly the
        # turns where something went wrong.
        status_part = render_retrieval_status(retrieval_status)
        if status_part:
            context_parts.append(status_part)
            remaining -= _count_tokens(status_part)

        if sql_results:
            distinct_rows = collapse_duplicate_rows(sql_results)
            if not matched_is_unknown and matched_total is None:
                matched_total = len(distinct_rows)

            separator = _SEPARATOR_TOKENS if context_parts else 0
            admitted_rows, assembler_truncated = self._fit_rows(
                distinct_rows, matched_total, query_truncated, remaining - separator,
            )
            sql_part = render_structured_block(
                admitted_rows, matched_total, query_truncated or assembler_truncated,
            )
            context_parts.append(sql_part)
            remaining -= _count_tokens(sql_part) + separator

            evidence.rows = admitted_rows
            evidence.structured_admitted = True
            evidence.rows_truncated = query_truncated or assembler_truncated
            evidence.matched_rows = matched_total

        admitted_chunks: list[RetrievalResult] = []
        for chunk in chunks:
            label = _label_for(chunk, document_names)
            rendered = f"{label} {chunk.chunk_text}"
            cost = _count_tokens(rendered)
            if context_parts or admitted_chunks:
                cost += _SEPARATOR_TOKENS
            if cost <= remaining:
                admitted_chunks.append(chunk)
                remaining -= cost

        if admitted_chunks:
            deduped_texts = _dedupe_chunks(admitted_chunks)
            for chunk, text in zip(admitted_chunks, deduped_texts):
                if not text:
                    continue
                context_parts.append(f"{_label_for(chunk, document_names)} {text}")
        elif chunks and not evidence.structured_admitted:
            top_chunk = chunks[0]
            label = _label_for(top_chunk, document_names)
            label_tokens = _count_tokens(label + " ")
            budget_for_body = max(remaining - label_tokens, 0)
            truncated_body = _truncate_to_tokens(top_chunk.chunk_text, budget_for_body)
            context_parts.append(f"{label} {truncated_body}")
            admitted_chunks = [top_chunk]

        evidence.chunks = admitted_chunks

        if not evidence.structured_complete:
            system_prompt = build_system_prompt(entity_data_is_complete=False)

        context_str = PART_SEPARATOR.join(context_parts) if context_parts else "No relevant data found."

        llm_messages = [{"role": "system", "content": system_prompt}]
        if conv_history:
            llm_messages.append({"role": "system", "content": f"Conversation history:\n{conv_history}"})
        llm_messages.append({"role": "user", "content": f"Context data:\n{context_str}\n\nQuestion: {message}"})

        return (llm_messages, evidence) if return_evidence else llm_messages

    @staticmethod
    def _fit_rows(
        rows: list[dict], matched: int | None, query_truncated: bool, budget: int,
    ) -> tuple[list[dict], bool]:
        """Admits whole rows until the budget is exhausted, and reports whether it had
        to stop early.

        Whole rows, so the JSON stays parseable. At least one row always, because a
        block that was retrieved and then vanished entirely is the defect this replaces
        — a 7,944-token result set was measured disappearing while its citation
        survived."""
        if not rows:
            return [], False

        for count in range(len(rows), 0, -1):
            candidate = rows[:count]
            rendered = render_structured_block(
                candidate, matched, query_truncated or count < len(rows),
            )
            if _count_tokens(rendered) <= budget:
                return candidate, count < len(rows)

        # Nothing fits. One row still goes in: truncation is a degraded answer, an
        # absent block is a wrong one.
        return rows[:1], True
