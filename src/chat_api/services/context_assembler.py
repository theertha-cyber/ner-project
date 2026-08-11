import json

from src.shared.config import settings
from src.shared.retrieval.chunking import TOKENIZER
from src.shared.retrieval.models import RetrievalResult

SYSTEM_PROMPT = """You are a helpful chatbot for a multi-tenant Named Entity Recognition (NER) platform.
You have access to the tenant's extracted entity data and document context.
Always answer based on the provided context data. Do not make up information.
When citing sources, reference the specific document or entity source.
If you cannot find relevant information, say so clearly.
Never reveal data from other tenants.
Format your response naturally and conversationally.

An `Entity data:` block, when present, is the complete result of a database query run
against the tenant's extracted entities specifically to answer this question. Treat it as
authoritative and exhaustive: when the question asks what something contains, lists, or
has, report EVERY distinct value in that block. Collapse exact duplicates of the same
value, but never drop a distinct one and never shorten the list because it seems long or
repetitive — an omitted value reads as "this isn't in the document", which is wrong.
Document passages alongside it add context and wording, and may mention things the
extractor did not capture; you may include those, but say where they came from, and never
let them replace or abbreviate the entity list."""


def _count_tokens(text: str) -> int:
    return len(TOKENIZER.encode(text))


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


class ContextAssembler:
    def __init__(self, token_budget: int | None = None, max_chunks: int | None = None):
        self.token_budget = token_budget if token_budget is not None else settings.context_token_budget
        self.max_chunks = (
            max_chunks if max_chunks is not None
            else (settings.context_max_chunks if settings.context_max_chunks is not None else settings.retrieval_top_k)
        )

    def assemble(
        self,
        message: str,
        sql_results: list[dict] | None,
        chunks: list[RetrievalResult] | None,
        document_names: dict[str, str] | None,
        conversation_context: list[dict] | None,
    ) -> list[dict]:
        document_names = document_names or {}
        chunks = (chunks or [])[: self.max_chunks]

        remaining = self.token_budget
        remaining -= _count_tokens(SYSTEM_PROMPT)
        remaining -= _count_tokens(f"Context data:\n\n\nQuestion: {message}")

        conv_history = ""
        if conversation_context:
            turns = conversation_context[-settings.conversation_history_turns:]
            for msg in turns:
                conv_history += f"{msg['role']}: {msg['content']}\n"
        if conv_history:
            remaining -= _count_tokens(f"Conversation history:\n{conv_history}")

        context_parts: list[str] = []

        if sql_results:
            sql_part = f"Entity data: {json.dumps(sql_results, default=str)}"
            sql_tokens = _count_tokens(sql_part)
            if sql_tokens <= remaining:
                context_parts.append(sql_part)
                remaining -= sql_tokens

        admitted_chunks: list[RetrievalResult] = []
        for chunk in chunks:
            label = _label_for(chunk, document_names)
            rendered = f"{label} {chunk.chunk_text}"
            rendered_tokens = _count_tokens(rendered)
            if rendered_tokens <= remaining:
                admitted_chunks.append(chunk)
                remaining -= rendered_tokens

        if admitted_chunks:
            deduped_texts = _dedupe_chunks(admitted_chunks)
            for chunk, text in zip(admitted_chunks, deduped_texts):
                if not text:
                    continue
                context_parts.append(f"{_label_for(chunk, document_names)} {text}")
        elif chunks:
            top_chunk = chunks[0]
            label = _label_for(top_chunk, document_names)
            label_tokens = _count_tokens(label + " ")
            budget_for_body = max(remaining - label_tokens, 0)
            truncated_body = _truncate_to_tokens(top_chunk.chunk_text, budget_for_body)
            context_parts.append(f"{label} {truncated_body}")

        context_str = "\n\n".join(context_parts) if context_parts else "No relevant data found."

        llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conv_history:
            llm_messages.append({"role": "system", "content": f"Conversation history:\n{conv_history}"})
        llm_messages.append({"role": "user", "content": f"Context data:\n{context_str}\n\nQuestion: {message}"})

        return llm_messages
