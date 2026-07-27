from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_index: int
    chunk_text: str
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class RetrievalResult(BaseModel):
    document_id: str
    chunk_index: int
    chunk_text: str
    similarity_score: float
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None
