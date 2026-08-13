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
    # Set when chunks from more than one retrieval invocation are merged. The reranker
    # falls back to unranked fusion candidates on failure, so one plan can produce two
    # invocations whose raw scores live on incomparable scales — RRF around 0.016
    # against cross-encoder logits that may be negative. Rank position is the one basis
    # both share, so the merge orders on this and keeps `similarity_score` for display.
    merge_rank_score: float | None = None
    # What `similarity_score` actually means for this result, so a citation's relevance
    # is not silently "RRF" in one turn and "cross-encoder logit" in the next.
    score_basis: str | None = None
