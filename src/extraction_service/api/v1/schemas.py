from datetime import datetime
from pydantic import BaseModel, Field

from src.extraction_service.services.processing_modes import (
    DEFAULT_PROCESSING_MODE,
    ProcessingMode,
)


class ExtractRequest(BaseModel):
    text: str


class BatchExtractRequest(BaseModel):
    """Body of `POST /api/v1/extract-batch`.

    The processing mode travels with the request rather than living in client state, so
    the server — not the browser — decides what a run does, and the run records what it
    actually did. An unknown mode is a 422 from Pydantic's enum validation before any
    run row is written."""

    document_ids: list[str] | None = Field(default=None, alias="documentIds")
    processing_mode: ProcessingMode = DEFAULT_PROCESSING_MODE

    model_config = {"populate_by_name": True}


class ExtractedEntity(BaseModel):
    entity_type: str
    value: str
    confidence: float
    start_offset: int
    end_offset: int


class ExtractResponse(BaseModel):
    entities: list[ExtractedEntity]
    model_version: str | None = None


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
    model_version: str | None = None
    # Additive: a client that ignores these is unaffected. `postprocess_degraded`
    # distinguishes a run that completed with post-processing applied from one that
    # completed because the fail-open path kept the BERT result when it could not be.
    processing_mode: str | None = None
    postprocess_model: str | None = None
    postprocess_prompt_version: str | None = None
    postprocess_degraded: bool | None = None


class BatchRunListItem(BatchRunStatus):
    run_id: str


class BatchRunListResponse(BaseModel):
    runs: list[BatchRunListItem]


class EligibleDocument(BaseModel):
    id: str
    filename: str
    already_extracted: bool


class EligibleDocumentListResponse(BaseModel):
    documents: list[EligibleDocument]


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
