from fastapi import HTTPException
from src.analytics_service.api.v1.schemas import AnalyticsQueryRequest, AnalyticsExportRequest


def validate_filter(body: AnalyticsQueryRequest | AnalyticsExportRequest):
    if body.date_from:
        try:
            from datetime import datetime
            datetime.strptime(body.date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date_from format. Use YYYY-MM-DD")

    if body.date_to:
        try:
            from datetime import datetime
            datetime.strptime(body.date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date_to format. Use YYYY-MM-DD")

    if body.confidence:
        if "min" in body.confidence and not isinstance(body.confidence["min"], (int, float)):
            raise HTTPException(status_code=422, detail="confidence.min must be a number")
        if "max" in body.confidence and not isinstance(body.confidence["max"], (int, float)):
            raise HTTPException(status_code=422, detail="confidence.max must be a number")
        if "min" in body.confidence and "max" in body.confidence:
            if body.confidence["min"] > body.confidence["max"]:
                raise HTTPException(status_code=422, detail="confidence.min cannot exceed confidence.max")


def build_where_clause(body: AnalyticsQueryRequest | AnalyticsExportRequest):
    conditions = []
    params = {}

    if body.entity_types:
        conditions.append("e.entity_id = ANY(:entity_types)")
        params["entity_types"] = body.entity_types

    if body.confidence:
        if "min" in body.confidence:
            conditions.append("e.confidence >= :conf_min")
            params["conf_min"] = body.confidence["min"]
        if "max" in body.confidence:
            conditions.append("e.confidence <= :conf_max")
            params["conf_max"] = body.confidence["max"]

    if body.date_from:
        conditions.append("r.started_at >= :date_from::date")
        params["date_from"] = body.date_from

    if body.date_to:
        conditions.append("r.started_at < :date_to::date + interval '1 day'")
        params["date_to"] = body.date_to

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    return where_clause, params
