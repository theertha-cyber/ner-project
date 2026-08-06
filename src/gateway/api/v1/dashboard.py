import asyncio
import logging
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.dependencies import get_db, require_tenant_role, get_request_tenant_id
from src.shared.config import settings

logger = logging.getLogger(__name__)

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
    icon: str = ""
    time: str = ""
    id: str = ""


class SideMetric(BaseModel):
    k: str
    v: str


class SideRow(BaseModel):
    label: str
    val: str
    pct: float
    c: str


class ResponseQualityCard(BaseModel):
    status: str  # "healthy" | "monitor" | "needs_attention" | "no_data"
    satisfactionPct: float | None
    positive: int
    negative: int
    rated: int
    total: int
    recommendation: str


class ActiveModelInfo(BaseModel):
    """Deployment metadata only — which model is currently serving, not how
    well it performs. Performance/quality now lives exclusively on
    ResponseQualityCard."""
    name: str
    status: str  # "active" | "unavailable"
    version: str
    deployedAt: str


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
    responseQuality: ResponseQualityCard | None = None
    activeModel: ActiveModelInfo | None = None


class DashboardSourceStatus(BaseModel):
    sources: dict[str, bool]


class DashboardSummaryResponse(BaseModel):
    data: DashboardData
    sources: dict[str, bool]


class DashboardActivityResponse(BaseModel):
    rows: list[ActivityRow]


_ROLE_SERVICES: dict[str, list[str]] = {
    "system_admin": ["tenants", "training"],
    "tenant_admin": ["documents", "annotations", "training", "models"],
    "annotator": ["annotations", "documents"],
    "business_user": ["conversations", "feedback", "assistant_health"],
}


def _null_sources() -> dict[str, bool]:
    return {"tenants": False, "training": False, "documents": False, "annotations": False, "models": False, "extraction": False, "feedback": False, "conversations": False, "assistant_health": False}


def _stat(label: str, value: str | None, unit: str, sub: str, delta: str, dir_: str | None = None) -> StatItem:
    return StatItem(label=label, value=value, unit=unit, sub=sub, delta=delta, dir=dir_)


def _tenant_schema(tenant_id: str) -> str:
    safe = tenant_id.replace("-", "_")
    return f"tenant_{safe}"


async def _all_tenant_schemas(db: AsyncSession) -> list[str]:
    result = await db.execute(
        text("""
            SELECT t.id
            FROM public.tenants t
            JOIN pg_namespace n ON n.nspname = 'tenant_' || replace(t.id, '-', '_')
            WHERE t.status = 'active'
        """)
    )
    return [_tenant_schema(row[0]) for row in result.fetchall()]


_SYSTEM_ACTIVITY_TITLES: dict[str, str] = {
    "tenant.create": "Tenant created",
    "tenant.deactivate": "Tenant deactivated",
    "user.create": "User onboarded",
    "training_job.submit": "Training job submitted",
    "training_job.approve": "Training job approved",
    "training_job.reject": "Training job rejected",
    "model_version.promote": "Model promoted",
}

_SYSTEM_ACTIVITY_GO: dict[str, str] = {
    "user.create": "users",
    "model_version.promote": "models",
}


def _system_activity_title(action: str) -> str:
    if action in _SYSTEM_ACTIVITY_TITLES:
        return _SYSTEM_ACTIVITY_TITLES[action]
    return action.replace("_", " ").replace(".", ": ")


def _system_activity_go(action: str) -> str:
    if action.startswith("tenant."):
        return "tenants"
    if action.startswith("training_job."):
        return "training"
    return _SYSTEM_ACTIVITY_GO.get(action, "dashboard")


async def _system_activity_feed(db: AsyncSession, limit: int) -> list[ActivityRow]:
    result = await db.execute(
        text("""
            SELECT actor, role, action, target, kind, tenant_id, created_at
            FROM public.audit_events
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows: list[ActivityRow] = []
    for row in result:
        rows.append(
            ActivityRow(
                title=_system_activity_title(row.action),
                sub=f"{row.actor} \u00b7 {row.target}",
                tag=row.kind,
                tk=_activity_tag_colour(row.kind),
                go=_system_activity_go(row.action),
                icon=row.kind,
                time=_relative_time(row.created_at),
            )
        )
    return rows


async def _platform_service_health() -> dict[str, str]:
    async def _check(url: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{url}/health")
            return "Online" if resp.status_code == 200 else "Offline"
        except Exception:
            return "Offline"

    chat_api, extraction, training, model_serving = await asyncio.gather(
        _check(settings.chat_api_url),
        _check(settings.extraction_service_url),
        _check(settings.training_service_url),
        _check(settings.model_serving_url),
    )
    return {
        "gateway": "Online",
        "chat_api": chat_api,
        "extraction": extraction,
        "training": training,
        "model_serving": model_serving,
    }


def _platform_health_status(gateway: str, chat_api: str, extraction: str, training: str, model_serving: str) -> str:
    if gateway == "Offline" or model_serving == "Offline":
        return "Critical"
    if chat_api == "Offline" or extraction == "Offline" or training == "Offline":
        return "Degraded"
    return "Healthy"


async def _system_admin_data(db: AsyncSession, tenant_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    tenant_count: str | None = None
    active_user_count: str | None = None
    pending_approvals: str | None = None
    training_jobs_running: str | None = None

    try:
        result = await db.execute(text("SELECT COUNT(*) FROM public.tenants"))
        tenant_count = str(result.scalar())
        sources["tenants"] = True
    except Exception:
        pass

    try:
        result = await db.execute(text("SELECT COUNT(*) FROM public.tenant_users WHERE status = 'active'"))
        active_user_count = str(result.scalar())
    except Exception:
        pass

    schemas = []
    try:
        schemas = await _all_tenant_schemas(db)
    except Exception:
        pass

    if schemas:
        try:
            total_pending = 0
            total_running = 0
            training_complete = True
            for s in schemas:
                try:
                    r = await db.execute(
                        text(f"SELECT COUNT(*) FILTER (WHERE status = 'pending_approval'), COUNT(*) FILTER (WHERE status = 'running') FROM {s}.training_jobs")
                    )
                    row = r.fetchone()
                    total_pending += row[0] or 0
                    total_running += row[1] or 0
                except Exception:
                    logger.exception("system_admin dashboard: training_jobs count failed for schema %s", s)
                    await db.rollback()
                    training_complete = False
            pending_approvals = str(total_pending)
            training_jobs_running = str(total_running)
            sources["training"] = training_complete
        except Exception:
            pass

    pRows: list[ActivityRow] = []
    try:
        pRows = await _system_activity_feed(db, 6)
    except Exception:
        logger.exception("system_admin dashboard: activity feed fetch failed")
        await db.rollback()

    health = await _platform_service_health()
    big = _platform_health_status(
        health["gateway"], health["chat_api"], health["extraction"], health["training"], health["model_serving"]
    )

    pending_sub = "needs review" if pending_approvals is not None else "service unavailable"
    title_suffix = f"{pending_approvals} jobs await approval." if pending_approvals and pending_approvals != "0" else "No pending approvals."

    data = DashboardData(
        kicker="Platform control plane",
        title=f"{tenant_count} tenants. {title_suffix}" if tenant_count is not None else "Platform overview.",
        line="Monitor tenant onboarding, platform health, and approvals across the platform.",
        stats=[
            _stat("Active Tenants", tenant_count, "", "active", "+2", "up") if tenant_count is not None
            else _stat("Active Tenants", None, "", "unavailable", "\u2014"),
            _stat("Active Users", active_user_count, "", "active" if active_user_count is not None else "service unavailable", "\u2014"),
            _stat("Pending Approvals", pending_approvals, "", pending_sub, "now", "warn"),
            _stat("Training Jobs Running", training_jobs_running, "", "active" if training_jobs_running is not None else "service unavailable", "\u2014"),
        ],
        pTitle="Platform Activity",
        pMeta="system_admin",
        pRows=pRows,
        sideTop="Platform Health",
        sideMeta="live service checks",
        big=big,
        bigUnit="",
        bar=100 if big == "Healthy" else (50 if big == "Degraded" else 0),
        sideMetrics=[
            SideMetric(k="gateway", v=health["gateway"]),
            SideMetric(k="chat api", v=health["chat_api"]),
            SideMetric(k="extraction", v=health["extraction"]),
        ],
        sideBot="Backing services",
        sideRows=[
            SideRow(
                label="Training Service",
                val=health["training"],
                pct=100 if health["training"] == "Online" else 0,
                c="var(--color-delta-up)" if health["training"] == "Online" else "var(--bad)",
            ),
            SideRow(
                label="Model Serving",
                val=health["model_serving"],
                pct=100 if health["model_serving"] == "Online" else 0,
                c="var(--color-delta-up)" if health["model_serving"] == "Online" else "var(--bad)",
            ),
        ],
    )
    return data, sources


async def _tenant_admin_data(db: AsyncSession, tenant_id: str, auth_header: str | None = None) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    doc_count: str | None = None
    ann_pct: str | None = None
    training_count: str | None = None

    # Documents: used/capacity fraction + delta (added in last 24h) + quota % subtext
    doc_sub = "service unavailable"
    doc_delta = "\u2014"
    doc_dir: str | None = None
    doc_total = 0
    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.documents WHERE status != 'error'")
        )
        doc_total = result.scalar() or 0
        doc_count = str(doc_total)
        sources["documents"] = True
        try:
            r = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.documents WHERE status != 'error' AND created_at >= NOW() - INTERVAL '24 hours'")
            )
            added = r.scalar() or 0
            if added > 0:
                doc_delta = f"+{added}"
                doc_dir = "up"
        except Exception:
            await db.rollback()
        try:
            r = await db.execute(
                text("SELECT max_documents FROM public.tenants WHERE id = :tid"),
                {"tid": tenant_id},
            )
            max_docs = r.scalar()
            if max_docs:
                doc_count = f"{doc_total}/{max_docs}"
                doc_sub = f"{round(doc_total / max_docs * 100)}% of quota"
            else:
                doc_sub = "active"
        except Exception:
            await db.rollback()
            doc_sub = "active"
    except Exception:
        pass

    # Annotation: documents annotated / documents uploaded for annotation + delta
    ann_sub = "service unavailable"
    ann_delta = "\u2014"
    ann_dir: str | None = None
    try:
        result = await db.execute(
            text(f"""
                WITH latest_task AS (
                    SELECT DISTINCT ON (document_id) document_id, status
                    FROM {schema}.annotation_tasks
                    ORDER BY document_id, created_at DESC
                )
                SELECT
                    COUNT(*) FILTER (WHERE status = 'completed') AS done,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status != 'completed') AS remaining
                FROM latest_task
            """)
        )
        row = result.fetchone()
        if row and row.total:
            ann_pct = f"{int(row.done or 0)}/{int(row.total)}"
            ann_sub = f"{int(row.remaining or 0)} docs left"
            sources["annotations"] = True
        try:
            r = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.annotation_tasks WHERE status = 'completed' AND updated_at >= NOW() - INTERVAL '24 hours'")
            )
            done = r.scalar() or 0
            if done > 0:
                ann_delta = f"+{done}"
                ann_dir = "up"
        except Exception:
            await db.rollback()
    except Exception:
        pass

    # Active model: fetched from training_service (MLflow-backed), not Postgres \u2014
    # see _fetch_active_model for why the Postgres model_versions.status column
    # can't be trusted here.
    active_model = await _fetch_active_model(auth_header)
    if active_model:
        sources["models"] = True

    # Training: value SHALL reflect jobs currently running right now, not a
    # historical 24h count \u2014 showing "1" while "No training in progress" is
    # displayed underneath was a contradictory, confusing pairing.
    train_sub = "service unavailable"
    train_delta = "\u2014"
    train_dir: str | None = None
    try:
        r = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.training_jobs WHERE status = 'running'")
        )
        running = r.scalar() or 0
        training_count = str(running)
        sources["training"] = True

        recent = 0
        try:
            r2 = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.training_jobs WHERE started_at >= NOW() - INTERVAL '24 hours'")
            )
            recent = r2.scalar() or 0
        except Exception:
            await db.rollback()

        if running > 0:
            train_sub = f"{running} job{'s' if running != 1 else ''} running"
            train_delta = "live"
            train_dir = "warn"
        elif recent > 0:
            train_sub = f"{recent} job{'s' if recent != 1 else ''} ran in last 24h"
        else:
            train_sub = "No training in progress"
    except Exception:
        pass

    pipeline_rows: list[ActivityRow] = []
    try:
        pipeline_rows = await _tenant_curated_activity(db, schema, tenant_id, 4)
    except Exception:
        pipeline_rows = [
            ActivityRow(title="No recent activity", sub="Activity will appear as your workspace runs", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents"),
        ]

    side_metrics, big_val, model_side_meta = _model_side_panel_from_active(active_model)
    active_model_card = _active_model_card(active_model)
    response_quality = await _tenant_response_quality_card(db, schema)
    if response_quality is not None:
        sources["feedback"] = True

    stats = [
        _stat("Documents", doc_count, "", doc_sub, doc_delta, doc_dir),
        _stat("Annotation", ann_pct, "", ann_sub, ann_delta, ann_dir),
        _stat("Training", training_count, "", train_sub, train_delta, train_dir),
    ]

    data = DashboardData(
        kicker="Good morning",
        title="Workspace overview.",
        line="Monitor your AI workspace, model performance, and dataset readiness.",
        stats=stats,
        pTitle="Recent Activity",
        pMeta="recent activity",
        pRows=pipeline_rows,
        sideTop="Active model",
        sideMeta=model_side_meta,
        big=big_val,
        bigUnit="eval F1",
        bar=0,
        sideMetrics=side_metrics,
        sideBot="",
        sideRows=[],
        responseQuality=response_quality,
        activeModel=active_model_card,
    )
    return data, sources


# Reused for the annotator "Dataset readiness" panel (_annotator_side_panel)
# and the tenant_admin "Dataset reached training readiness" activity event \u2014
# a single source of truth for the entity count that unlocks training.
DATASET_READINESS_ENTITY_THRESHOLD = 500

# Documents at or above this size are surfaced as a "Large document upload
# completed" event in the tenant_admin activity feed.
LARGE_DOCUMENT_UPLOAD_BYTES = 20 * 1024 * 1024


def _relative_time(dt: datetime | None) -> str:
    """Formats a timestamp as a short relative string ("2 hours ago",
    "Yesterday", "3 days ago") for the tenant_admin activity feed. Backend
    formats this once per request rather than shipping a raw ISO timestamp
    and a client-side date library \u2014 see design.md Decision 5."""
    if dt is None:
        return "\u2014"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(seconds // 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(seconds // 86400)
    if days == 1:
        return "Yesterday"
    return f"{days} days ago"


async def _tenant_curated_activity(db: AsyncSession, schema: str, tenant_id: str, limit: int) -> list[ActivityRow]:
    """Curated operational activity feed for tenant_admin: training
    lifecycle events, model deployment, batch extraction, dataset
    readiness, large uploads, and user-added events \u2014 derived from
    existing status columns rather than raw per-record activity (no
    audit-log table exists yet; see design.md Decision 1)."""
    events: list[tuple[datetime | None, ActivityRow]] = []

    async def _add(query: str, params: dict, build_row) -> None:
        try:
            result = await db.execute(text(query), params)
            for row in result:
                ts, activity_row = build_row(row)
                events.append((ts, activity_row))
        except Exception:
            await db.rollback()

    await _add(
        f"SELECT id, status, created_at, started_at, completed_at, failed_at FROM {schema}.training_jobs "
        f"WHERE status IN ('pending_approval', 'failed', 'completed') OR (status = 'queued' AND started_at IS NULL)",
        {},
        lambda row: (
            {
                "pending_approval": row.created_at,
                "queued": row.created_at,
                "failed": row.failed_at,
                "completed": row.completed_at,
            }[row.status],
            ActivityRow(
                title={
                    "pending_approval": "Model training requested",
                    "queued": "Model training approved",
                    "failed": "Model training failure",
                    "completed": "Model training completed",
                }[row.status],
                sub=f"Job {row.id[:8]}...",
                tag={"pending_approval": "requested", "queued": "approved", "failed": "failed", "completed": "completed"}[row.status],
                tk={"pending_approval": "pending_approval", "queued": "queued", "failed": "failed", "completed": "completed"}[row.status],
                go="training",
                icon="failure" if row.status == "failed" else "training",
                time=_relative_time({
                    "pending_approval": row.created_at,
                    "queued": row.created_at,
                    "failed": row.failed_at,
                    "completed": row.completed_at,
                }[row.status]),
            ),
        ),
    )

    await _add(
        f"SELECT id, promoted_at FROM {schema}.model_versions WHERE status = 'promoted' AND promoted_at IS NOT NULL "
        f"ORDER BY promoted_at DESC LIMIT 20",
        {},
        lambda row: (
            row.promoted_at,
            ActivityRow(title="Model deployment", sub=f"Version {row.id[:8]}... deployed", tag="deployed", tk="promoted", go="models", icon="deploy", time=_relative_time(row.promoted_at)),
        ),
    )

    await _add(
        f"""
            SELECT date_trunc('minute', er.completed_at) AS bucket, COUNT(*) AS n, MAX(er.completed_at) AS ts
            FROM {schema}.extraction_runs er
            WHERE er.status = 'completed' AND er.completed_at IS NOT NULL
            GROUP BY bucket
            HAVING COUNT(*) >= 2
            ORDER BY bucket DESC
            LIMIT 20
        """,
        {},
        lambda row: (
            row.ts,
            ActivityRow(title="Batch extraction completed", sub=f"{row.n} documents processed", tag="completed", tk="completed", go="extractions", icon="batch", time=_relative_time(row.ts)),
        ),
    )

    await _add(
        f"SELECT id, filename, file_size_bytes, created_at FROM {schema}.documents "
        f"WHERE status != 'error' AND file_size_bytes >= :threshold ORDER BY created_at DESC LIMIT 20",
        {"threshold": LARGE_DOCUMENT_UPLOAD_BYTES},
        lambda row: (
            row.created_at,
            ActivityRow(title="Large document upload completed", sub=row.filename or f"Document {row.id[:8]}...", tag="uploaded", tk="completed", go="documents", icon="upload", time=_relative_time(row.created_at)),
        ),
    )

    await _add(
        f"""
            SELECT crossing_ts FROM (
                SELECT created_at AS crossing_ts, ROW_NUMBER() OVER (ORDER BY created_at) AS rn
                FROM {schema}.spans
            ) ranked
            WHERE rn = :threshold
        """,
        {"threshold": DATASET_READINESS_ENTITY_THRESHOLD},
        lambda row: (
            row.crossing_ts,
            ActivityRow(title="Dataset reached training readiness", sub=f"{DATASET_READINESS_ENTITY_THRESHOLD}+ entities annotated", tag="ready", tk="completed", go="annotation", icon="dataset", time=_relative_time(row.crossing_ts)),
        ),
    )

    await _add(
        "SELECT id, role, created_at FROM public.tenant_users WHERE tenant_id = :tid AND role IN ('business_user', 'annotator') ORDER BY created_at DESC LIMIT 20",
        {"tid": tenant_id},
        lambda row: (
            row.created_at,
            ActivityRow(
                title="Business User added" if row.role == "business_user" else "Annotator added",
                sub="New user added to the workspace",
                tag="added",
                tk="active",
                go="users",
                icon="user",
                time=_relative_time(row.created_at),
            ),
        ),
    )

    events.sort(key=lambda e: e[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    rows = [row for _, row in events[:limit]]
    while len(rows) < limit:
        rows.append(ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="documents", icon="\u2014", time="\u2014"))
    return rows


async def _fetch_active_model(auth_header: str | None) -> dict | None:
    """The Postgres model_versions.status column is not updated by
    promote/demote (those only move MLflow's registry stage), so it can't
    be trusted as the source of truth for the currently active model.
    Ask training_service directly — same MLflow-backed source the Model
    Registry page uses."""
    if not auth_header:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.training_service_url}/api/v1/models/active",
                headers={"Authorization": auth_header},
            )
        if resp.status_code != 200:
            return None
        if resp.headers.get("x-info") == "no-promoted-model":
            return None
        return resp.json()
    except Exception:
        logger.exception("dashboard: failed to fetch active model from training_service")
        return None


def _format_deployed_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return dt.strftime("%d %b %Y").lstrip("0")


def _active_model_card(active: dict | None) -> ActiveModelInfo | None:
    """Deployment metadata only (which model is serving) — no eval metrics.
    Performance/quality lives on ResponseQualityCard."""
    if not active:
        return None

    run_name = active.get("run_name")
    version_number = active.get("version_number")
    name = run_name or (f"v{version_number}" if version_number is not None else "Active model")

    return ActiveModelInfo(
        name=name,
        status="active",
        version=f"v{version_number}" if version_number is not None else "—",
        deployedAt=_format_deployed_date(active.get("promoted_at")),
    )


def _model_side_panel_from_active(active: dict | None) -> tuple[list[SideMetric], str, str]:
    side_metrics = [
        SideMetric(k="prec", v="—"),
        SideMetric(k="rec", v="—"),
        SideMetric(k="loss", v="—"),
    ]
    big_val = "—"
    if not active:
        return side_metrics, big_val, "no model promoted"

    metrics = active.get("metrics") or {}
    f1 = metrics.get("eval_f1", metrics.get("f1"))
    prec = metrics.get("eval_precision", metrics.get("precision"))
    rec = metrics.get("eval_recall", metrics.get("recall"))
    loss = metrics.get("eval_loss", metrics.get("loss"))

    if f1 is not None:
        big_val = f"{float(f1):.4f}"
    if prec is not None:
        side_metrics[0] = SideMetric(k="prec", v=f"{float(prec):.4f}")
    if rec is not None:
        side_metrics[1] = SideMetric(k="rec", v=f"{float(rec):.4f}")
    if loss is not None:
        side_metrics[2] = SideMetric(k="loss", v=f"{float(loss):.4f}")

    run_name = active.get("run_name")
    version_number = active.get("version_number")
    if run_name:
        side_meta = run_name
    elif version_number:
        side_meta = f"v{version_number}"
    else:
        side_meta = "eval metrics" if big_val != "—" else "no model promoted"

    return side_metrics, big_val, side_meta


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


def _response_quality_status(rated: int, positive: int) -> str:
    if rated == 0:
        return "no_data"
    pct = positive / rated * 100
    if pct >= 80:
        return "healthy"
    if pct >= 60:
        return "monitor"
    return "needs_attention"


_RECOMMENDATIONS = {
    "healthy": "No retraining recommended. Business users are consistently rating responses positively.",
    "monitor": "Keep an eye on response quality. Consider gathering more feedback before deciding on retraining.",
    "needs_attention": "Consider retraining the model. Business users are reporting low response quality.",
    "no_data": "Not enough feedback yet to assess model performance.",
}


async def _tenant_response_quality_card(db: AsyncSession, schema: str) -> ResponseQualityCard | None:
    """Builds the Response Quality card: a status derived from the satisfaction
    ratio (positive / rated, never positive / total — per design.md Decision 4),
    the underlying counts, and a plain-language recommendation, so a Tenant
    Admin can judge model health and whether retraining is warranted without
    interpreting raw numbers themselves. Only feeds `responseQuality`; the
    Active model eval-metrics panel (sideTop/big/bigUnit/bar/sideMetrics) is
    untouched."""
    total = 0
    rated = 0
    positive = 0
    try:
        # Defensive: an earlier query elsewhere in this request (e.g. the
        # Annotation block above) may have failed and left the shared `db`
        # session's transaction aborted without rolling back. Clear that state
        # before running our own queries so a prior, unrelated failure doesn't
        # also blank out this card.
        await db.rollback()
        r = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.chat_messages WHERE role = 'assistant' AND answer_kind = 'answer'")
        )
        total = r.scalar() or 0

        r = await db.execute(
            text(f"""
                SELECT COUNT(*), COUNT(*) FILTER (WHERE f.rating = 'up')
                FROM {schema}.chat_messages m
                JOIN {schema}.chat_message_feedback f ON f.message_id = m.id
                WHERE m.role = 'assistant' AND m.answer_kind = 'answer'
            """)
        )
        row = r.fetchone()
        rated = row[0] or 0
        positive = row[1] or 0
    except Exception:
        await db.rollback()
        return None

    negative = rated - positive
    status = _response_quality_status(rated, positive)
    satisfaction_pct = round(positive / rated * 100, 1) if rated > 0 else None

    return ResponseQualityCard(
        status=status,
        satisfactionPct=satisfaction_pct,
        positive=positive,
        negative=negative,
        rated=rated,
        total=total,
        recommendation=_RECOMMENDATIONS[status],
    )


async def _annotator_data(db: AsyncSession, tenant_id: str, user_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    task_count: str | None = None
    span_count: str | None = None
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

    total_spans, bar_pct, side_metrics_list, side_rows = await _annotator_side_panel(db, schema)

    remaining = max(DATASET_READINESS_ENTITY_THRESHOLD - total_spans, 0)
    if remaining > 0:
        side_meta = f"{remaining} more entities needed"
        side_bot = f"{DATASET_READINESS_ENTITY_THRESHOLD} entities unlocks training"
    else:
        side_meta = "Training threshold reached"
        side_bot = f"Training unlocked at {DATASET_READINESS_ENTITY_THRESHOLD} entities"

    stats = [
        _stat("Assigned tasks", task_count, "", "active" if task_count is not None else "service unavailable", "\u2014"),
        _stat("Entities Annotated", span_count, "", "active" if span_count is not None else "service unavailable", "\u2014"),
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
        sideMeta=side_meta,
        big=f"{round(bar_pct)}",
        bigUnit="% to training-ready",
        bar=bar_pct,
        sideMetrics=side_metrics_list,
        sideBot=side_bot,
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


async def _annotator_side_panel(db: AsyncSession, schema: str) -> tuple[int, float, list[SideMetric], list[SideRow]]:
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

    bar_pct = round(min(total_spans / DATASET_READINESS_ENTITY_THRESHOLD * 100, 100) if total_spans > 0 else 0, 1)
    side_metrics = [
        SideMetric(k="docs", v=str(doc_count)),
        SideMetric(k="types", v=str(type_count)),
        SideMetric(k="today", v=str(today_spans)),
    ]

    return total_spans, bar_pct, side_metrics, span_by_type


async def _business_user_data(db: AsyncSession, tenant_id: str, user_id: str) -> tuple[DashboardData, dict[str, bool]]:
    sources = _null_sources()
    schema = _tenant_schema(tenant_id)

    conversation_count: str | None = None
    message_count: str | None = None
    helpful_count: str | None = None

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.conversations WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        conversation_count = str(result.scalar())
        sources["conversations"] = True
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"""
                SELECT COUNT(*) FROM {schema}.chat_messages cm
                JOIN {schema}.conversations c ON c.id = cm.conversation_id
                WHERE c.user_id = :user_id AND cm.role = 'user'
            """),
            {"user_id": user_id},
        )
        message_count = str(result.scalar())
    except Exception:
        pass

    try:
        result = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.chat_message_feedback WHERE user_id = :user_id AND rating = 'up'"),
            {"user_id": user_id},
        )
        helpful_count = str(result.scalar())
        sources["feedback"] = True
    except Exception:
        pass

    conversation_rows: list[ActivityRow] = []
    try:
        conversation_rows = await _business_conversation_activity(db, schema, user_id)
    except Exception:
        conversation_rows = [
            ActivityRow(title="No conversations yet", sub="Conversations will appear here once you start chatting", tag="\u2014", tk="queued", go="chat"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="chat"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="chat"),
            ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="chat"),
        ]

    assistant_status, assistant_meta, assistant_healthy = await _fetch_assistant_health()
    sources["assistant_health"] = assistant_healthy
    avg_response_time = await _business_avg_response_time(db, schema, user_id)
    side_metrics_list = [
        SideMetric(k="status", v=assistant_status),
        SideMetric(k="updated", v=assistant_meta),
        SideMetric(k="resp time", v=avg_response_time),
    ]

    stats = [
        _stat("Conversations", conversation_count, "", "" if conversation_count is not None else "service unavailable", ""),
        _stat("Messages Sent", message_count, "", "" if message_count is not None else "service unavailable", ""),
        _stat("Responses Marked Helpful", helpful_count, "", "" if helpful_count is not None else "service unavailable", ""),
    ]

    data = DashboardData(
        kicker="Your AI assistant workspace",
        title=f"{conversation_count} conversations started." if conversation_count is not None else "No conversations yet.",
        line="Search, explore, and interact with your organization's knowledge through the AI assistant.",
        stats=stats,
        pTitle="Recent Conversations",
        pMeta="",
        pRows=conversation_rows,
        sideTop="AI Assistant Status",
        sideMeta=assistant_status,
        big=assistant_status,
        bigUnit="",
        bar=0,
        sideMetrics=side_metrics_list,
        sideBot="",
        sideRows=[],
    )
    return data, sources


async def _business_conversation_activity(db: AsyncSession, schema: str, user_id: str) -> list[ActivityRow]:
    rows: list[ActivityRow] = []
    result = await db.execute(
        text(f"""
            SELECT c.id, c.title, c.updated_at, c.created_at,
                   (SELECT COUNT(*) FROM {schema}.chat_messages cm WHERE cm.conversation_id = c.id) AS message_count
            FROM {schema}.conversations c
            WHERE c.user_id = :user_id
            ORDER BY COALESCE(c.updated_at, c.created_at) DESC
            LIMIT 4
        """),
        {"user_id": user_id},
    )
    for row in result:
        title = row.title or "New conversation"
        last_interaction = row.updated_at or row.created_at
        sub = f"{row.message_count} messages"
        if last_interaction is not None:
            sub = f"{last_interaction} \u00b7 {sub}"
        rows.append(ActivityRow(title=title, sub=sub, tag="conversation", tk="completed", go="chat", id=row.id))
    while len(rows) < 4:
        rows.append(ActivityRow(title="\u2014", sub="\u2014", tag="\u2014", tk="queued", go="chat"))
    return rows[:4]


async def _business_avg_response_time(db: AsyncSession, schema: str, user_id: str) -> str:
    try:
        result = await db.execute(
            text(f"""
                SELECT AVG(cm.response_time_ms) FROM {schema}.chat_messages cm
                JOIN {schema}.conversations c ON c.id = cm.conversation_id
                WHERE c.user_id = :user_id AND cm.role = 'assistant' AND cm.response_time_ms IS NOT NULL
            """),
            {"user_id": user_id},
        )
        avg_ms = result.scalar()
        if avg_ms is None:
            return "—"
        avg_ms = float(avg_ms)
        if avg_ms >= 1000:
            return f"{avg_ms / 1000:.1f}s"
        return f"{round(avg_ms)}ms"
    except Exception:
        return "—"


async def _fetch_assistant_health() -> tuple[str, str, bool]:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.chat_api_url}/health")
        if resp.status_code == 200:
            return "Online", now, True
        return "Offline", now, False
    except Exception:
        return "Offline", now, False


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
    auth_header = request.headers.get("Authorization")
    handler = _ROLE_DATA.get(role, _business_user_data)

    if role in ("annotator", "business_user"):
        data, sources = await handler(db, tenant_id, user_id)
    elif role == "system_admin":
        data, sources = await handler(db, tenant_id)
    elif role == "tenant_admin":
        data, sources = await handler(db, tenant_id, auth_header)
    else:
        data, sources = await handler(db, tenant_id)

    return DashboardSummaryResponse(data=data, sources=sources)


@router.get("/activity", response_model=DashboardActivityResponse)
async def get_dashboard_activity(
    db: AsyncSession = Depends(get_db),
    role: str = Depends(require_tenant_role),
    tenant_id: str = Depends(get_request_tenant_id),
):
    """Full pipeline activity history for tenant admins, including
    annotator and business-user activity, not just the last 24h."""
    if role != "tenant_admin":
        return DashboardActivityResponse(rows=[])

    schema = _tenant_schema(tenant_id)
    try:
        rows = await _tenant_curated_activity(db, schema, tenant_id, 200)
    except Exception:
        logger.exception("dashboard activity: full history fetch failed for schema %s", schema)
        rows = []
    return DashboardActivityResponse(rows=rows)
