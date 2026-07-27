import tiktoken
from src.shared.config import settings
from src.shared.retrieval.models import Chunk

TOKENIZER = tiktoken.get_encoding("cl100k_base")


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    page_number: int | None = None,
    char_start: int | None = None,
) -> list[Chunk]:
    if not text or not text.strip():
        return []

    chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap

    span_offset = char_start if char_start is not None else 0
    search_pos = 0

    tokens = TOKENIZER.encode(text)
    chunks: list[Chunk] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_str = TOKENIZER.decode(chunk_tokens)

        local_start = text.find(chunk_str, search_pos)
        if local_start == -1:
            local_start = search_pos
        search_pos = local_start + 1

        chunks.append(Chunk(
            chunk_index=len(chunks),
            chunk_text=chunk_str,
            page_number=page_number,
            char_start=span_offset + local_start if char_start is not None else None,
            char_end=span_offset + local_start + len(chunk_str) if char_start is not None else None,
        ))
        if end == len(tokens):
            break
        start += chunk_size - overlap
    return chunks
