from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.analytics_service.dependencies import get_db
from src.analytics_service.api.v1.schemas import (
    DashboardResponse,
    EntityCoverageWidget,
    ConfidenceBucket,
    ConfidenceDistributionWidget,
    ExtractionVolumePoint,
    ExtractionVolumeWidget,
    DocumentEntityCountsWidget,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


async def fetch_widget_data(db: AsyncSession, mv_name: str):
    try:
        result = await db.execute(text(f"SELECT * FROM {mv_name} ORDER BY 1"))
        rows = result.fetchall()
        return rows
    except Exception:
        return []


@router.get("/dashboard")
async def analytics_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    entity_coverage_rows = await fetch_widget_data(db, "mv_entity_coverage")
    confidence_rows = await fetch_widget_data(db, "mv_confidence_distribution")
    volume_rows = await fetch_widget_data(db, "mv_extraction_volume")
    doc_counts_rows = await fetch_widget_data(db, "mv_document_entity_counts")

    entity_coverage = [
        EntityCoverageWidget(entity_type=r[0], coverage_pct=float(r[1]))
        for r in entity_coverage_rows
    ]

    confidence_buckets = [
        ConfidenceBucket(label=r[0], count=r[1])
        for r in confidence_rows
    ]

    volume_data = [
        ExtractionVolumePoint(date=str(r[0]), count=r[1])
        for r in volume_rows
    ]

    doc_counts = [
        DocumentEntityCountsWidget(entity_type=r[0], avg_per_document=float(r[1]))
        for r in doc_counts_rows
    ]

    return DashboardResponse(
        entity_coverage=entity_coverage,
        confidence_distribution=ConfidenceDistributionWidget(buckets=confidence_buckets),
        extraction_volume=ExtractionVolumeWidget(data=volume_data),
        document_entity_counts=doc_counts,
    )
