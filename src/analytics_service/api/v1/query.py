import json
import csv
import io
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.analytics_service.api.v1.schemas import (
    AnalyticsQueryRequest,
    AnalyticsExportRequest,
    AnalyticsQueryResponse,
)
from src.analytics_service.dependencies import get_db
from src.analytics_service.services.query_service import build_where_clause, validate_filter
from src.analytics_service.common import QUERY_TIMEOUT_SECONDS, MAX_EXPORT_ROWS

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.post("/query")
async def analytics_query(
    body: AnalyticsQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    validate_filter(body)
    where_clause, params = build_where_clause(body)

    limit = body.limit or 50
    offset = 0
    if body.cursor:
        try:
            offset = int(body.cursor)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid cursor value")

    sql = f"""
        SELECT e.id, e.entity_id AS entity_type, e.value, e.confidence, e.document_id,
               r.started_at AS extracted_at
        FROM extracted_entities e
        JOIN extraction_runs r ON r.id = e.run_id
        {where_clause}
        ORDER BY extracted_at DESC NULLS LAST, e.id
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit + 1
    params["offset"] = offset

    try:
        result = await db.execute(
            text(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT_SECONDS}s'")
        )
        rows_result = await db.execute(text(sql), params)
        rows = rows_result.fetchall()
    except Exception:
        raise HTTPException(status_code=504, detail="Query timed out")

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    results = [
        {
            "id": r[0],
            "entity_type": r[1],
            "value": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
            "document_id": r[4],
            "extracted_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]

    next_cursor = str(offset + limit) if has_more else None

    return AnalyticsQueryResponse(
        results=results,
        pagination={
            "next_cursor": next_cursor,
            "has_more": has_more,
            "limit": limit,
        },
    )


@router.post("/export")
async def analytics_export(
    body: AnalyticsExportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    validate_filter(body)
    where_clause, params = build_where_clause(body)

    sql = f"""
        SELECT e.entity_id AS entity_type, e.value, e.confidence, e.document_id,
               r.started_at AS extracted_at
        FROM extracted_entities e
        JOIN extraction_runs r ON r.id = e.run_id
        {where_clause}
        ORDER BY extracted_at DESC NULLS LAST, e.id
        LIMIT :limit
    """
    params["limit"] = MAX_EXPORT_ROWS + 1

    try:
        rows_result = await db.execute(
            text(f"SET LOCAL statement_timeout = '{QUERY_TIMEOUT_SECONDS}s'")
        )
        rows_result = await db.execute(text(sql), params)
        rows = rows_result.fetchall()
    except Exception:
        raise HTTPException(status_code=504, detail="Export query timed out")

    truncated = len(rows) > MAX_EXPORT_ROWS
    if truncated:
        rows = rows[:MAX_EXPORT_ROWS]

    if body.format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["entity_type", "value", "confidence", "document_id", "extracted_at"])
        for r in rows:
            writer.writerow([
                r[0], r[1], float(r[2]) if r[2] is not None else "",
                r[3], r[4].isoformat() if r[4] else "",
            ])
        output.seek(0)
        headers = {
            "Content-Disposition": "attachment; filename=analytics-export.csv",
            "X-Result-Truncated": "true" if truncated else "false",
        }
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers=headers,
        )
    else:
        items = [
            {
                "entity_type": r[0],
                "value": r[1],
                "confidence": float(r[2]) if r[2] is not None else None,
                "document_id": r[3],
                "extracted_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]
        content = json.dumps(items, default=str)
        headers = {
            "Content-Disposition": "attachment; filename=analytics-export.json",
            "X-Result-Truncated": "true" if truncated else "false",
        }
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers=headers,
        )


@router.post("/refresh")
async def analytics_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_coverage"))
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_confidence_distribution"))
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_extraction_volume"))
        await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_document_entity_counts"))
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Materialized view refresh failed")

    return {"status": "refreshed"}
