from datetime import datetime
from pydantic import BaseModel, Field


class AnalyticsFilter(BaseModel):
    entity_types: list[str] | None = None
    confidence: dict[str, float] | None = None
    date_from: str | None = None
    date_to: str | None = None
    document_sources: list[str] | None = None
    annotators: list[str] | None = None


class AnalyticsQueryRequest(BaseModel):
    entity_types: list[str] | None = None
    confidence: dict[str, float] | None = None
    date_from: str | None = None
    date_to: str | None = None
    document_sources: list[str] | None = None
    annotators: list[str] | None = None
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=1000)


class EntityCoverageWidget(BaseModel):
    entity_type: str
    coverage_pct: float


class ConfidenceBucket(BaseModel):
    label: str
    count: int


class ConfidenceDistributionWidget(BaseModel):
    buckets: list[ConfidenceBucket]


class ExtractionVolumePoint(BaseModel):
    date: str
    count: int


class ExtractionVolumeWidget(BaseModel):
    data: list[ExtractionVolumePoint]
    interval: str = "day"
    lookback_days: int = 30


class DocumentEntityCountsWidget(BaseModel):
    entity_type: str
    avg_per_document: float


class DashboardResponse(BaseModel):
    entity_coverage: list[EntityCoverageWidget]
    confidence_distribution: ConfidenceDistributionWidget
    extraction_volume: ExtractionVolumeWidget
    document_entity_counts: list[DocumentEntityCountsWidget]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsQueryResponse(BaseModel):
    results: list[dict]
    pagination: dict


class AnalyticsExportRequest(BaseModel):
    entity_types: list[str] | None = None
    confidence: dict[str, float] | None = None
    date_from: str | None = None
    date_to: str | None = None
    document_sources: list[str] | None = None
    annotators: list[str] | None = None
    format: str = Field(default="csv", pattern="^(csv|json)$")
