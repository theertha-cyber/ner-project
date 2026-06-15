from datetime import datetime
from pydantic import BaseModel


class ExtractRequest(BaseModel):
    text: str


class ExtractedEntity(BaseModel):
    entity_type: str
    value: str
    confidence: float
    start_offset: int
    end_offset: int


class ExtractResponse(BaseModel):
    entities: list[ExtractedEntity]


class BatchExtractResponse(BaseModel):
    run_id: str
    status: str = "queued"


class BatchRunStatus(BaseModel):
    status: str
    total_documents: int | None = None
    processed_count: int | None = None
    skipped_count: int | None = None
    failed_count: int | None = None
    completed_at: datetime | None = None
    started_at: datetime | None = None


class EntityQueryParams(BaseModel):
    documentId: str | None = None
    type: str | None = None
    minConfidence: float | None = None
    reviewStatus: str | None = None
    page: int = 1
    per_page: int = 20


class EntityItem(BaseModel):
    id: str
    run_id: str
    entity_id: str
    value: str
    confidence: float
    normalized_value: str | None = None
    source_span_id: str | None = None
    review_status: str
    corrected_value: str | None = None
    corrected_by: str | None = None
    correction_notes: str | None = None


class EntityListResponse(BaseModel):
    items: list[EntityItem]
    total: int
    page: int
    per_page: int


class EntityPatchRequest(BaseModel):
    review_status: str
    corrected_value: str | None = None
    correction_notes: str | None = None
