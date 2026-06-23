import uuid
import tiktoken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.chat_api.services.embedding_service import EmbeddingService

TOKENIZER = tiktoken.get_encoding("cl100k_base")
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    tokens = TOKENIZER.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_str = TOKENIZER.decode(chunk_tokens)
        chunks.append({
            "chunk_index": len(chunks),
            "chunk_text": chunk_str,
        })
        if end == len(tokens):
            break
        start += chunk_size - overlap
    return chunks


async def chunk_and_embed_document(document_id: str, tenant_id: str, full_text: str):
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    schema = f"tenant_{tenant_id.replace('-', '_')}"
    embedder = EmbeddingService()

    chunks = chunk_text(full_text)
    texts = [c["chunk_text"] for c in chunks]
    embeddings = await embedder.embed_batch(texts)

    async with session_factory() as session:
        for i, chunk in enumerate(chunks):
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.document_chunks (id, document_id, chunk_index, chunk_text, embedding)
                    VALUES (:id, :doc_id, :chunk_index, :chunk_text, :embedding)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "chunk_text": chunk["chunk_text"],
                    "embedding": str(embeddings[i]) if embeddings else None,
                },
            )
        await session.commit()
