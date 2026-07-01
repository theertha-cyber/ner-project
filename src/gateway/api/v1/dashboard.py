from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.dependencies import get_db, require_tenant_role, get_request_tenant_id


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


def _tenant_schema(tenant_id: str) -> str:
    safe = tenant_id.replace("-", "_")
    return f"tenant_{safe}"


async def _all_tenant_schemas(db: AsyncSession) -> list[str]:
    result = await db.execute(
        text("SELECT id FROM public.tenants WHERE status = 'active'")
    )
    return [_tenant_schema(row[0]) for row in result.fetchall()]


async def _system_admin_data(db: AsyncSession, tenant_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    tenant_count: str | None = None
    doc_count_all: str | None = None
    pending_approvals: str | None = None
    avg_f1: str | None = None

    try:
        result = await db.execute(text("SELECT COUNT(*) FROM public.tenants"))
        tenant_count = str(result.scalar())
        sources["tenants"] = True
    except Exception:
        pass

    schemas = []
    try:
        schemas = await _all_tenant_schemas(db)
    except Exception:
        pass

    if schemas:
        total_docs = 0
        try:
            for s in schemas:
                try:
                    r = await db.execute(text(f"SELECT COUNT(*) FROM {s}.documents"))
                    total_docs += r.scalar() or 0
                except Exception:
                    pass
            doc_count_all = str(total_docs)
            sources["documents"] = True
        except Exception:
            pass

        try:
            total_pending = 0
            for s in schemas:
                try:
                    r = await db.execute(
                        text(f"SELECT COUNT(*) FROM {s}.training_jobs WHERE status = 'pending_approval'")
                    )
                    total_pending += r.scalar() or 0
                except Exception:
                    pass
            pending_approvals = str(total_pending)
        except Exception:
            pass

        try:
            f1_values: list[float] = []
            for s in schemas:
                try:
                    r = await db.execute(
                        text(f"SELECT metrics->>'f1' FROM {s}.model_versions WHERE status = 'promoted' ORDER BY promoted_at DESC LIMIT 1")
                    )
                    val = r.scalar()
                    if val is not None:
                        f1_values.append(float(val))
                except Exception:
                    pass
            if f1_values:
                avg_f1 = f"{(sum(f1_values) / len(f1_values)) * 100:.1f}"
                sources["models"] = True
        except Exception:
            pass

    pending_sub = "needs review" if pending_approvals is not None else "service unavailable"
    title_suffix = f"{pending_approvals} jobs await approval." if pending_approvals and pending_approvals != "0" else "No pending approvals."

    data = DashboardData(
        kicker="Platform control plane",
        title=f"{tenant_count} tenants. {title_suffix}" if tenant_count is not None else "Platform overview.",
        line="Dashboard data for training, documents, and models will appear as services come online.",
        stats=[
            _stat("Active tenants", tenant_count, "", "active", "+2", "up") if tenant_count is not None
            else _stat("Active tenants", None, "", "unavailable", "\u2014"),
            _stat("Documents (all)", doc_count_all, "", "active" if doc_count_all is not None else "service unavailable", "\u2014"),
            _stat("Pending approvals", pending_approvals, "", pending_sub, "now", "warn"),
            _stat("Avg model F1", avg_f1, "%", "active" if avg_f1 is not None else "service unavailable", "\u2014"),
        ],
        pTitle="Approval queue",
        pMeta="system_admin",
        pRows=[
            ActivityRow(title="No jobs pending", sub="Training queue is empty", tag="\u2014", tk="queued", go="training"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="training"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="training"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="training"),
        ],
        sideTop="Platform health",
        sideMeta="uptime 30d",
        big="\u2014",
        bigUnit="% SLA",
        bar=0,
        sideMetrics=[
            SideMetric(k="p95", v="\u2014"),
            SideMetric(k="err", v="\u2014"),
            SideMetric(k="GPU", v="\u2014"),
        ],
        sideBot="Storage by tenant",
        sideRows=[],
    )
    return data, sources


async def _tenant_admin_data(db: AsyncSession, tenant_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    doc_count: str | None = None
    ann_pct: str | None = None
    model_f1: str | None = None
    training_count: str | None = None

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.documents WHERE status != 'error'")
        )
        doc_count = str(result.scalar())
        sources["documents"] = True
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT (COUNT(DISTINCT document_id) FILTER (WHERE status = 'completed'))::float / NULLIF(COUNT(DISTINCT document_id), 0) * 100 FROM {schema}.annotation_tasks")
        )
        val = result.scalar()
        ann_pct = f"{val:.0f}" if val is not None else None
        if val is not None:
            sources["annotations"] = True
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT metrics->>'f1' FROM {schema}.model_versions WHERE status = 'promoted' ORDER BY promoted_at DESC LIMIT 1")
        )
        f1_raw = result.scalar()
        if f1_raw is not None:
            model_f1 = f"{float(f1_raw) * 100:.1f}"
            sources["models"] = True
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.training_jobs WHERE started_at >= NOW() - INTERVAL '24 hours'")
        )
        training_count = str(result.scalar())
        sources["training"] = True
    except Exception:
        pass

    pipeline_rows: list[ActivityRow] = []
    try:
        pipeline_rows = await _tenant_pipeline_activity(db, schema)
    except Exception:
        pipeline_rows = [
            ActivityRow(title="No recent activity", sub="Activity will appear as pipeline runs", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
        ]

    side_metrics, big_val, side_rows = await _tenant_side_panel(db, schema)

    stats = [
        _stat("Documents", doc_count, "", "active" if doc_count is not None else "service unavailable", "\u2014"),
        _stat("Annotation", ann_pct, "%", "active" if ann_pct is not None else "service unavailable", "\u2014"),
        _stat("Active model", model_f1, "F1", "active" if model_f1 is not None else "service unavailable", "\u2014"),
        _stat("Training", training_count, "", "active" if training_count is not None else "service unavailable", "\u2014", "warn" if training_count is not None else None),
    ]

    data = DashboardData(
        kicker="Good morning",
        title="Pipeline overview.",
        line="Your tenant's document processing and training pipeline at a glance.",
        stats=stats,
        pTitle="Pipeline activity",
        pMeta="last 24h",
        pRows=pipeline_rows,
        sideTop="Active model",
        sideMeta="no model promoted" if big_val == "\u2014" else "eval metrics",
        big=big_val,
        bigUnit="eval F1",
        bar=0,
        sideMetrics=side_metrics,
        sideBot="Quota usage",
        sideRows=side_rows,
    )
    return data, sources


async def _tenant_pipeline_activity(db: AsyncSession, schema: str) -> list[ActivityRow]:
    rows: list[ActivityRow] = []
    result = await db.execute(
        text(f"""
            (SELECT 'training_job' AS kind, id, status, started_at AS ts, NULL AS title_str
             FROM {schema}.training_jobs
             WHERE started_at >= NOW() - INTERVAL '24 hours')
            UNION ALL
            (SELECT 'document' AS kind, id, status, created_at AS ts, filename AS title_str
             FROM {schema}.documents
             WHERE created_at >= NOW() - INTERVAL '24 hours')
            ORDER BY ts DESC
            LIMIT 4
        """)
    )
    for row in result:
        kind = row.kind
        status = row.status or "queued"
        if kind == "training_job":
            title = f"Training {status}"
            sub = f"Job {row.id[:8]}..."
        elif kind == "document":
            title = row.title_str or "Document upload"
            sub = f"Status: {status}"
        else:
            title = "Activity"
            sub = ""
        tag = status
        tk = _activity_tag_colour(status)
        go = "training" if kind == "training_job" else "documents"
        rows.append(ActivityRow(title=title, sub=sub, tag=tag, tk=tk, go=go))
    while len(rows) < 4:
        rows.append(ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"))
    return rows[:4]


def _activity_tag_colour(status: str) -> str:
    mapping = {
        "completed": "success",
        "annotated": "success",
        "running": "progress",
        "processing": "progress",
        "queued": "queued",
        "failed": "error",
        "error": "error",
    }
    return mapping.get(status.lower(), "queued")


async def _tenant_side_panel(db: AsyncSession, schema: str) -> tuple[list[SideMetric], str, list[SideRow]]:
    side_metrics: list[SideMetric] = [
        SideMetric(k="prec", v="\u2014"),
        SideMetric(k="rec", v="\u2014"),
        SideMetric(k="loss", v="\u2014"),
    ]
    big_val = "\u2014"
    side_rows: list[SideRow] = []

    try:
        result = await db.execute(
            text(f"SELECT metrics->>'f1', metrics->>'precision', metrics->>'recall', metrics->>'loss' FROM {schema}.model_versions WHERE status = 'promoted' ORDER BY promoted_at DESC LIMIT 1")
        )
        row = result.fetchone()
        if row and row[0] is not None:
            big_val = f"{float(row[0]) * 100:.1f}"
            prec = row[1]
            rec = row[2]
            loss = row[3]
            if prec is not None:
                side_metrics[0] = SideMetric(k="prec", v=f"{float(prec):.3f}")
            if rec is not None:
                side_metrics[1] = SideMetric(k="rec", v=f"{float(rec):.3f}")
            if loss is not None:
                side_metrics[2] = SideMetric(k="loss", v=f"{float(loss):.4f}")
    except Exception:
        pass

    return side_metrics, big_val, side_rows


async def _annotator_data(db: AsyncSession, tenant_id: str, user_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    task_count: str | None = None
    span_count: str | None = None
    suggestion_count: str | None = None
    completion_pct: str | None = None

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.annotation_tasks WHERE annotator_user_id = :user_id"),
            {"user_id": user_id},
        )
        task_count = str(result.scalar())
        sources["annotations"] = True
    except Exception:
        pass

    try:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {schema}.spans"))
        span_count = str(result.scalar())
    except Exception:
        pass

    try:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {schema}.suggested_spans"))
        suggestion_count = str(result.scalar())
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"""
                SELECT (COUNT(*) FILTER (WHERE status = 'completed'))::float / NULLIF(COUNT(*), 0) * 100
                FROM {schema}.annotation_tasks WHERE annotator_user_id = :user_id
            """),
            {"user_id": user_id},
        )
        val = result.scalar()
        completion_pct = f"{val:.0f}" if val is not None else None
    except Exception:
        pass

    task_rows: list[ActivityRow] = []
    try:
        task_rows = await _annotator_task_activity(db, schema, user_id)
    except Exception:
        task_rows = [
            ActivityRow(title="No tasks assigned", sub="Tasks will appear here when assigned", tag="\u2014", tk="queued", go="annotation"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="annotation"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="annotation"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="annotation"),
        ]

    side_big, side_metrics_list, side_rows = await _annotator_side_panel(db, schema)

    stats = [
        _stat("Assigned tasks", task_count, "", "active" if task_count is not None else "service unavailable", "\u2014"),
        _stat("Spans confirmed", span_count, "", "active" if span_count is not None else "service unavailable", "\u2014"),
        _stat("Suggestions", suggestion_count, "", "active" if suggestion_count is not None else "service unavailable", "\u2014", "warn" if suggestion_count is not None else None),
        _stat("Completion", completion_pct, "%", "active" if completion_pct is not None else "service unavailable", "\u2014"),
    ]

    data = DashboardData(
        kicker="Your annotation queue",
        title=f"{task_count} tasks assigned." if task_count is not None else "No tasks assigned yet.",
        line="Track your annotation progress and dataset readiness.",
        stats=stats,
        pTitle="My tasks",
        pMeta="annotator",
        pRows=task_rows,
        sideTop="Dataset readiness",
        sideMeta="toward training",
        big=side_big,
        bigUnit="/ 500 spans",
        bar=0,
        sideMetrics=side_metrics_list,
        sideBot="Spans by entity type",
        sideRows=side_rows,
    )
    return data, sources


async def _annotator_task_activity(db: AsyncSession, schema: str, user_id: str) -> list[ActivityRow]:
    rows: list[ActivityRow] = []
    result = await db.execute(
        text(f"""
            SELECT at.id, at.status, at.created_at, d.filename
            FROM {schema}.annotation_tasks at
            LEFT JOIN {schema}.documents d ON d.id = at.document_id
            WHERE at.annotator_user_id = :user_id
            ORDER BY at.created_at DESC
            LIMIT 4
        """),
        {"user_id": user_id},
    )
    for row in result:
        title = row.filename or f"Task {row.id[:8]}..."
        sub = f"Status: {row.status or 'open'}"
        tag = row.status or "open"
        tk = _activity_tag_colour(row.status or "queued")
        go = "annotation"
        rows.append(ActivityRow(title=title, sub=sub, tag=tag, tk=tk, go=go))
    while len(rows) < 4:
        rows.append(ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="annotation"))
    return rows[:4]


async def _annotator_side_panel(db: AsyncSession, schema: str) -> tuple[str, list[SideMetric], list[SideRow]]:
    total_spans = 0
    doc_count = 0
    type_count = 0
    today_spans = 0
    span_by_type: list[SideRow] = []

    try:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {schema}.spans"))
        total_spans = result.scalar() or 0
    except Exception:
        pass

    try:
        result = await db.execute(text(f"SELECT COUNT(DISTINCT document_id) FROM {schema}.spans"))
        doc_count = result.scalar() or 0
    except Exception:
        pass

    try:
        result = await db.execute(text(f"SELECT COUNT(DISTINCT entity_type) FROM {schema}.spans"))
        type_count = result.scalar() or 0
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.spans WHERE created_at >= CURRENT_DATE")
        )
        today_spans = result.scalar() or 0
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"""
                SELECT entity_type, COUNT(*) AS cnt
                FROM {schema}.spans
                GROUP BY entity_type
                ORDER BY cnt DESC
                LIMIT 5
            """)
        )
        total = sum(r.cnt for r in result) or 1
        result = await db.execute(
            text(f"""
                SELECT entity_type, COUNT(*) AS cnt
                FROM {schema}.spans
                GROUP BY entity_type
                ORDER BY cnt DESC
                LIMIT 5
            """)
        )
        for r in result:
            pct = round(r.cnt / total * 100, 1)
            span_by_type.append(SideRow(label=r.entity_type, val=str(r.cnt), pct=pct, c="blue"))
    except Exception:
        pass

    bar_pct = min(total_spans / 500 * 100, 100) if total_spans > 0 else 0
    big_text = str(total_spans)
    side_metrics = [
        SideMetric(k="docs", v=str(doc_count)),
        SideMetric(k="types", v=str(type_count)),
        SideMetric(k="today", v=str(today_spans)),
    ]

    return big_text, side_metrics, span_by_type


async def _business_user_data(db: AsyncSession, tenant_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    doc_count: str | None = None
    entity_count: str | None = None
    avg_conf: str | None = None
    auto_cleared_pct: str | None = None

    try:
        result = await db.execute(
            text(f"SELECT COUNT(DISTINCT document_id) FROM {schema}.extracted_entities")
        )
        doc_count = str(result.scalar())
        sources["extraction"] = True
    except Exception:
        pass

    try:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {schema}.extracted_entities"))
        entity_count = str(result.scalar())
    except Exception:
        pass

    avg_conf_sub = "service unavailable"
    try:
        result = await db.execute(
            text(f"SELECT AVG(confidence) FROM {schema}.extracted_entities")
        )
        val = result.scalar()
        if val is not None:
            avg_conf = f"{float(val) * 100:.0f}"
            avg_conf_sub = "active"
        else:
            avg_conf = "0"
            avg_conf_sub = "no extractions yet"
    except Exception:
        pass

    auto_cleared_sub = "service unavailable"
    try:
        result = await db.execute(
            text(f"""
                SELECT (COUNT(*) FILTER (WHERE review_status = 'auto_cleared'))::float / NULLIF(COUNT(*), 0) * 100
                FROM {schema}.extracted_entities
            """)
        )
        val = result.scalar()
        if val is not None:
            auto_cleared_pct = f"{val:.1f}"
            auto_cleared_sub = "active"
        else:
            auto_cleared_pct = "0.0"
            auto_cleared_sub = "no extractions yet"
    except Exception:
        pass

    extraction_rows: list[ActivityRow] = []
    try:
        extraction_rows = await _business_extraction_activity(db, schema)
    except Exception:
        extraction_rows = [
            ActivityRow(title="No extractions yet", sub="Extractions will appear once documents are processed", tag="\u2014", tk="queued", go="extractions"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="extractions"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="extractions"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="extractions"),
        ]

    side_big, side_metrics_list, side_rows = await _business_side_panel(db, schema)

    stats = [
        _stat("Docs extracted", doc_count, "", "active" if doc_count is not None else "service unavailable", "\u2014"),
        _stat("Entities found", entity_count, "", "active" if entity_count is not None else "service unavailable", "\u2014"),
        _stat("Avg confidence", avg_conf, "%", avg_conf_sub, "\u2014"),
        _stat("Auto-cleared", auto_cleared_pct, "%", auto_cleared_sub, "\u2014"),
    ]

    data = DashboardData(
        kicker="Extraction intelligence",
        title=f"{doc_count} documents processed." if doc_count is not None else "No documents processed yet.",
        line="Review extraction results and model performance across your documents.",
        stats=stats,
        pTitle="Recent extractions",
        pMeta="business_user",
        pRows=extraction_rows,
        sideTop="Active model",
        sideMeta="no model promoted" if side_big == "\u2014" else "eval metrics",
        big=side_big,
        bigUnit="eval F1",
        bar=0,
        sideMetrics=side_metrics_list,
        sideBot="Top extracted fields",
        sideRows=side_rows,
    )
    return data, sources


async def _business_extraction_activity(db: AsyncSession, schema: str) -> list[ActivityRow]:
    rows: list[ActivityRow] = []
    result = await db.execute(
        text(f"""
            SELECT er.id, er.status, er.started_at, d.filename,
                   (SELECT COUNT(*) FROM {schema}.extracted_entities ee WHERE ee.run_id = er.id) AS entity_count,
                   (SELECT AVG(confidence) FROM {schema}.extracted_entities ee WHERE ee.run_id = er.id) AS avg_conf
            FROM {schema}.extraction_runs er
            LEFT JOIN {schema}.documents d ON d.id = er.document_id
            ORDER BY er.started_at DESC NULLS LAST
            LIMIT 4
        """)
    )
    for row in result:
        title = row.filename or f"Run {row.id[:8]}..."
        sub = f"{row.entity_count or 0} entities"
        if row.avg_conf is not None:
            sub += f", {float(row.avg_conf) * 100:.0f}% conf"
        tag = row.status or "queued"
        tk = _activity_tag_colour(row.status or "queued")
        go = "extractions"
        rows.append(ActivityRow(title=title, sub=sub, tag=tag, tk=tk, go=go))
    while len(rows) < 4:
        rows.append(ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="extractions"))
    return rows[:4]


async def _business_side_panel(db: AsyncSession, schema: str) -> tuple[str, list[SideMetric], list[SideRow]]:
    side_metrics: list[SideMetric] = [
        SideMetric(k="prec", v="\u2014"),
        SideMetric(k="rec", v="\u2014"),
        SideMetric(k="loss", v="\u2014"),
    ]
    big_val = "\u2014"
    side_rows: list[SideRow] = []

    try:
        result = await db.execute(
            text(f"SELECT metrics->>'f1', metrics->>'precision', metrics->>'recall', metrics->>'loss' FROM {schema}.model_versions WHERE status = 'promoted' ORDER BY promoted_at DESC LIMIT 1")
        )
        row = result.fetchone()
        if row and row[0] is not None:
            big_val = f"{float(row[0]) * 100:.1f}"
            if row[1] is not None:
                side_metrics[0] = SideMetric(k="prec", v=f"{float(row[1]):.3f}")
            if row[2] is not None:
                side_metrics[1] = SideMetric(k="rec", v=f"{float(row[2]):.3f}")
            if row[3] is not None:
                side_metrics[2] = SideMetric(k="loss", v=f"{float(row[3]):.4f}")
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT entity_id, COUNT(*) AS cnt FROM {schema}.extracted_entities GROUP BY entity_id ORDER BY cnt DESC LIMIT 5")
        )
        total = sum(r.cnt for r in result) or 1
        result = await db.execute(
            text(f"SELECT entity_id, COUNT(*) AS cnt FROM {schema}.extracted_entities GROUP BY entity_id ORDER BY cnt DESC LIMIT 5")
        )
        for r in result:
            pct = round(r.cnt / total * 100, 1)
            side_rows.append(SideRow(label=r.entity_id, val=str(r.cnt), pct=pct, c="blue"))
    except Exception:
        pass

    return big_val, side_metrics, side_rows


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
    tenant_id: str = Depends(get_request_tenant_id),
):
    user_id = getattr(request.state, "user_id", None)
    handler = _ROLE_DATA.get(role, _business_user_data)

    if role == "annotator":
        data, sources = await handler(db, tenant_id, user_id)
    elif role == "system_admin":
        data, sources = await handler(db, tenant_id)
    else:
        data, sources = await handler(db, tenant_id)

    return DashboardSummaryResponse(data=data, sources=sources)
