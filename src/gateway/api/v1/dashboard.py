from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.dependencies import get_db, require_tenant_role


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class StatItem(BaseModel):
    label: str
    value: str | None
    unit: str
    sub: str
    delta: str
    dir: str | None = None


class ActivityRow(BaseModel):
    title: str
    sub: str
    tag: str
    tk: str
    go: str


class SideMetric(BaseModel):
    k: str
    v: str


class SideRow(BaseModel):
    label: str
    val: str
    pct: float
    c: str


class DashboardData(BaseModel):
    kicker: str
    title: str
    line: str
    stats: list[StatItem]
    pTitle: str
    pMeta: str
    pRows: list[ActivityRow]
    sideTop: str
    sideMeta: str
    big: str
    bigUnit: str
    bar: float
    sideMetrics: list[SideMetric]
    sideBot: str
    sideRows: list[SideRow]


class DashboardSourceStatus(BaseModel):
    sources: dict[str, bool]


class DashboardSummaryResponse(BaseModel):
    data: DashboardData
    sources: dict[str, bool]


_ROLE_SERVICES: dict[str, list[str]] = {
    "system_admin": ["tenants", "training"],
    "tenant_admin": ["documents", "annotations", "training", "models"],
    "annotator": ["annotations", "documents"],
    "business_user": ["extraction", "models"],
}


def _null_sources() -> dict[str, bool]:
    return {"tenants": False, "training": False, "documents": False, "annotations": False, "models": False, "extraction": False}


def _stat(label: str, value: str | None, unit: str, sub: str, delta: str, dir_: str | None = None) -> StatItem:
    return StatItem(label=label, value=value, unit=unit, sub=sub, delta=delta, dir=dir_)


async def _system_admin_data(db: AsyncSession) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    tenant_count: str | None = None

    try:
        result = await db.execute(text("SELECT COUNT(*) FROM public.tenants"))
        tenant_count = str(result.scalar())
        sources["tenants"] = True
    except Exception:
        pass

    data = DashboardData(
        kicker="Platform control plane",
        title=f"{tenant_count} tenants. 2 jobs await approval." if tenant_count is not None else "Platform overview.",
        line="Dashboard data for training, documents, and models will appear as services come online.",
        stats=[
            _stat("Active tenants", tenant_count, "", "active", "+2", "up") if tenant_count is not None
            else _stat("Active tenants", None, "", "unavailable", "—"),
            _stat("Documents (all)", None, "k", "service unavailable", "—"),
            _stat("Pending approvals", None, "", "needs review", "now", "warn"),
            _stat("Avg model F1", None, "", "service unavailable", "—"),
        ],
        pTitle="Approval queue",
        pMeta="system_admin",
        pRows=[
            ActivityRow(title="No jobs pending", sub="Training queue is empty", tag="—", tk="queued", go="training"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="training"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="training"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="training"),
        ],
        sideTop="Platform health",
        sideMeta="uptime 30d",
        big="—",
        bigUnit="% SLA",
        bar=0,
        sideMetrics=[
            SideMetric(k="p95", v="—"),
            SideMetric(k="err", v="—"),
            SideMetric(k="GPU", v="—"),
        ],
        sideBot="Storage by tenant",
        sideRows=[],
    )
    return data, sources


async def _tenant_admin_data() -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    data = DashboardData(
        kicker="Good morning",
        title="Pipeline overview.",
        line="Dashboard data for documents, annotation, models, and training will appear as services come online.",
        stats=[
            _stat("Documents", None, "", "service unavailable", "—"),
            _stat("Annotation", None, "%", "service unavailable", "—"),
            _stat("Active model", None, "F1", "service unavailable", "—"),
            _stat("Training", None, "", "service unavailable", "—", "warn"),
        ],
        pTitle="Pipeline activity",
        pMeta="last 24h",
        pRows=[
            ActivityRow(title="No recent activity", sub="Activity will appear as pipeline runs", tag="—", tk="queued", go="documents"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="documents"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="documents"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="documents"),
        ],
        sideTop="Active model",
        sideMeta="no model promoted",
        big="—",
        bigUnit="eval F1",
        bar=0,
        sideMetrics=[
            SideMetric(k="prec", v="—"),
            SideMetric(k="rec", v="—"),
            SideMetric(k="loss", v="—"),
        ],
        sideBot="Quota usage",
        sideRows=[],
    )
    return data, sources


async def _annotator_data() -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    data = DashboardData(
        kicker="Your annotation queue",
        title="No tasks assigned yet.",
        line="Task data will appear as your team assigns annotation work to you.",
        stats=[
            _stat("Assigned tasks", None, "", "service unavailable", "—"),
            _stat("Spans confirmed", None, "", "service unavailable", "—"),
            _stat("Suggestions", None, "", "service unavailable", "—", "warn"),
            _stat("Completion", None, "%", "service unavailable", "—"),
        ],
        pTitle="My tasks",
        pMeta="annotator",
        pRows=[
            ActivityRow(title="No tasks assigned", sub="Tasks will appear here when assigned", tag="—", tk="queued", go="annotation"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="annotation"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="annotation"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="annotation"),
        ],
        sideTop="Dataset readiness",
        sideMeta="toward training",
        big="—",
        bigUnit="/ 500 spans",
        bar=0,
        sideMetrics=[
            SideMetric(k="docs", v="—"),
            SideMetric(k="types", v="—"),
            SideMetric(k="today", v="—"),
        ],
        sideBot="Spans by entity type",
        sideRows=[],
    )
    return data, sources


async def _business_user_data() -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    data = DashboardData(
        kicker="Extraction intelligence",
        title="No documents processed yet.",
        line="Extraction data will appear once documents have been processed through the pipeline.",
        stats=[
            _stat("Docs extracted", None, "", "service unavailable", "—"),
            _stat("Entities found", None, "", "service unavailable", "—"),
            _stat("Avg confidence", None, "", "service unavailable", "—"),
            _stat("Auto-cleared", None, "%", "service unavailable", "—"),
        ],
        pTitle="Recent extractions",
        pMeta="business_user",
        pRows=[
            ActivityRow(title="No extractions yet", sub="Extractions will appear once documents are processed", tag="—", tk="queued", go="extractions"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="extractions"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="extractions"),
            ActivityRow(title="—", sub="—", tag="—", tk="queued", go="extractions"),
        ],
        sideTop="Active model",
        sideMeta="no model promoted",
        big="—",
        bigUnit="eval F1",
        bar=0,
        sideMetrics=[
            SideMetric(k="prec", v="—"),
            SideMetric(k="rec", v="—"),
            SideMetric(k="loss", v="—"),
        ],
        sideBot="Top extracted fields",
        sideRows=[],
    )
    return data, sources


_ROLE_DATA: dict[str, callable] = {
    "system_admin": _system_admin_data,
    "tenant_admin": _tenant_admin_data,
    "annotator": _annotator_data,
    "business_user": _business_user_data,
}


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    request: Request,
    db: AsyncSession = Depends(get_db),
    role: str = Depends(require_tenant_role),
):
    handler = _ROLE_DATA.get(role, _business_user_data)
    data, sources = await handler(db) if role == "system_admin" else await handler()
    return DashboardSummaryResponse(data=data, sources=sources)
