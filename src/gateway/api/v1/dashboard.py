from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.dependencies import get_db, require_tenant_role

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _null_sources() -> dict:
    return {"tenants": False, "training": False, "documents": False, "annotations": False, "models": False}


def _stat(label: str, value, unit: str, sub: str, delta: str, dir_: str | None = None) -> dict:
    s: dict = {"label": label, "value": value, "unit": unit, "sub": sub, "delta": delta}
    if dir_:
        s["dir"] = dir_
    return s


async def _system_admin_data(db: AsyncSession) -> tuple[dict, dict]:
    sources = _null_sources()
    tenant_count = None

    try:
        result = await db.execute(text("SELECT COUNT(*) FROM public.tenants"))
        tenant_count = result.scalar()
        sources["tenants"] = True
    except Exception:
        sources["tenants"] = False

    data = {
        "kicker": "Platform control plane",
        "title": f"{tenant_count} tenants." if tenant_count is not None else "Platform overview.",
        "line": "Dashboard data for training, documents, and models will appear as services come online.",
        "stats": [
            _stat("Active tenants", tenant_count, "", "", "", None),
            _stat("Documents (all)", None, "k", "service unavailable", "—", None),
            _stat("Pending approvals", None, "", "service unavailable", "—", "warn"),
            _stat("Avg model F1", None, "", "service unavailable", "—", None),
        ],
        "pTitle": "Approval queue",
        "pMeta": "system_admin",
        "pRows": [
            {"title": "No jobs pending", "sub": "Training queue is empty", "tag": "—", "tk": "queued", "go": "training"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "training"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "training"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "training"},
        ],
        "sideTop": "Platform health",
        "sideMeta": "uptime 30d",
        "big": "—",
        "bigUnit": "% SLA",
        "bar": 0,
        "sideMetrics": [
            {"k": "p95", "v": "—"},
            {"k": "err", "v": "—"},
            {"k": "GPU", "v": "—"},
        ],
        "sideBot": "Storage by tenant",
        "sideRows": [],
    }
    return data, sources


def _tenant_admin_data() -> tuple[dict, dict]:
    sources = _null_sources()
    data = {
        "kicker": "Good morning",
        "title": "Pipeline overview.",
        "line": "Dashboard data for documents, annotation, models, and training will appear as services come online.",
        "stats": [
            _stat("Documents", None, "", "service unavailable", "—", None),
            _stat("Annotation", None, "%", "service unavailable", "—", None),
            _stat("Active model", None, "F1", "service unavailable", "—", None),
            _stat("Training", None, "", "service unavailable", "—", "warn"),
        ],
        "pTitle": "Pipeline activity",
        "pMeta": "last 24h",
        "pRows": [
            {"title": "No recent activity", "sub": "Activity will appear as pipeline runs", "tag": "—", "tk": "queued", "go": "documents"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "documents"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "documents"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "documents"},
        ],
        "sideTop": "Active model",
        "sideMeta": "no model promoted",
        "big": "—",
        "bigUnit": "eval F1",
        "bar": 0,
        "sideMetrics": [
            {"k": "prec", "v": "—"},
            {"k": "rec", "v": "—"},
            {"k": "loss", "v": "—"},
        ],
        "sideBot": "Quota usage",
        "sideRows": [],
    }
    return data, sources


def _annotator_data() -> tuple[dict, dict]:
    sources = _null_sources()
    data = {
        "kicker": "Your annotation queue",
        "title": "No tasks assigned yet.",
        "line": "Task data will appear as your team assigns annotation work to you.",
        "stats": [
            _stat("Assigned tasks", None, "", "service unavailable", "—", None),
            _stat("Spans confirmed", None, "", "service unavailable", "—", None),
            _stat("Suggestions", None, "", "service unavailable", "—", "warn"),
            _stat("Completion", None, "%", "service unavailable", "—", None),
        ],
        "pTitle": "My tasks",
        "pMeta": "annotator",
        "pRows": [
            {"title": "No tasks assigned", "sub": "Tasks will appear here when assigned", "tag": "—", "tk": "queued", "go": "annotation"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "annotation"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "annotation"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "annotation"},
        ],
        "sideTop": "Dataset readiness",
        "sideMeta": "toward training",
        "big": "—",
        "bigUnit": "/ 500 spans",
        "bar": 0,
        "sideMetrics": [
            {"k": "docs", "v": "—"},
            {"k": "types", "v": "—"},
            {"k": "today", "v": "—"},
        ],
        "sideBot": "Spans by entity type",
        "sideRows": [],
    }
    return data, sources


def _business_user_data() -> tuple[dict, dict]:
    sources = _null_sources()
    data = {
        "kicker": "Extraction intelligence",
        "title": "No documents processed yet.",
        "line": "Extraction data will appear once documents have been processed through the pipeline.",
        "stats": [
            _stat("Docs extracted", None, "", "service unavailable", "—", None),
            _stat("Entities found", None, "", "service unavailable", "—", None),
            _stat("Avg confidence", None, "", "service unavailable", "—", None),
            _stat("Auto-cleared", None, "%", "service unavailable", "—", None),
        ],
        "pTitle": "Recent extractions",
        "pMeta": "business_user",
        "pRows": [
            {"title": "No extractions yet", "sub": "Extractions will appear once documents are processed", "tag": "—", "tk": "queued", "go": "extractions"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "extractions"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "extractions"},
            {"title": "—", "sub": "—", "tag": "—", "tk": "queued", "go": "extractions"},
        ],
        "sideTop": "Active model",
        "sideMeta": "no model promoted",
        "big": "—",
        "bigUnit": "eval F1",
        "bar": 0,
        "sideMetrics": [
            {"k": "prec", "v": "—"},
            {"k": "rec", "v": "—"},
            {"k": "loss", "v": "—"},
        ],
        "sideBot": "Top extracted fields",
        "sideRows": [],
    }
    return data, sources


@router.get("/summary")
async def get_dashboard_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
    role: str = Depends(require_tenant_role),
):
    if role == "system_admin":
        data, sources = await _system_admin_data(db)
    elif role == "tenant_admin":
        data, sources = _tenant_admin_data()
    elif role == "annotator":
        data, sources = _annotator_data()
    else:
        data, sources = _business_user_data()

    return {"data": data, "sources": sources}
