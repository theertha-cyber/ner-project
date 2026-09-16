"""Trigger and status for LLM pre-labeling.

A separate endpoint from `/prelabel` rather than a mode flag on it (design.md Decision 1). The
keyword path is synchronous and returns its suggestions in the response body; this one is
asynchronous and returns a job handle. One endpoint with two response shapes chosen by a
parameter would be a worse contract than two endpoints with honest ones — and keeping them
separate means this change cannot regress the existing path by construction.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.annotation_service.api.v1.spans import get_session, get_tenant_id
from src.annotation_service.celery_app import celery_app
from src.shared.config import settings
from src.shared.entity_config_version import entity_config_fingerprint, load_active_entity_config
from src.shared.exceptions import NotFoundError

router = APIRouter(tags=["llm-prelabeling"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _content_hash(document_text: str) -> str:
    """Hashes the extracted text, not the stored file.

    The text is what is sent to the model and what offsets are measured against, so it is what
    a cached result is actually a result *of*. A re-OCR that changes the text changes this hash
    even where the uploaded file's checksum is unchanged."""
    return hashlib.sha256(document_text.encode("utf-8")).hexdigest()


async def _load_document_text(session: AsyncSession, schema: str, doc_id: str) -> str:
    """Every text span, in order — the same reconstruction `export.py` performs.

    Deliberately not the keyword path's `LIMIT 1`: that reads only the first span, so offsets
    on a multi-span document would be measured against page one while the exporter measures
    them against the whole document."""
    result = await session.execute(
        text(
            f"SELECT text FROM {schema}.document_text_spans "
            "WHERE document_id = :doc_id ORDER BY span_index"
        ),
        {"doc_id": doc_id},
    )
    return "".join(row[0] or "" for row in result.fetchall())


async def _replace_suggested_spans(
    session: AsyncSession, schema: str, doc_id: str, spans: list[dict]
) -> None:
    await session.execute(
        text(f"DELETE FROM {schema}.suggested_spans WHERE document_id = :doc_id"),
        {"doc_id": doc_id},
    )
    for span in spans:
        await session.execute(
            text(
                f"INSERT INTO {schema}.suggested_spans "
                "(id, document_id, entity_type, char_start, char_end, text_content, "
                " confidence, source) "
                "VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, "
                "        :confidence, :source)"
            ),
            {
                "id": str(uuid.uuid4()),
                "doc_id": doc_id,
                "entity_type": span["entity_type"],
                "char_start": span["char_start"],
                "char_end": span["char_end"],
                "text_val": span["text"],
                "confidence": span["confidence"],
                "source": span["source"],
            },
        )


def _coerce_json(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


@router.post("/api/v1/documents/{doc_id}/prelabel/llm", status_code=202)
async def trigger_llm_prelabel(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Enqueue LLM pre-labeling, or serve a cached result.

    Everything this does before returning is a hash, two indexed reads, and an enqueue — the
    provider call happens on the worker. The two 422s are checked here rather than on the worker
    so a caller learns immediately that the request could never have succeeded, instead of
    polling a job that was doomed at enqueue time."""
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    document_text = await _load_document_text(session, schema, doc_id)
    if not document_text.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "NO_TEXT", "message": "Document has no extracted text"},
        )

    entity_types = await load_active_entity_config(session, tenant_id)
    if not entity_types:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NO_ENTITY_TYPES",
                "message": "No entity types are configured for this tenant",
            },
        )

    content_hash = _content_hash(document_text)
    config_version = entity_config_fingerprint(entity_types)
    job_id = str(uuid.uuid4())

    # The cache key is (content hash, entity-config version), never the document hash alone: a
    # tenant who adds a QA pair or an entity type has changed what the prompt asks for, and
    # serving them the previous run's suggestions would silently ignore the edit they just made
    # (design.md Decision 5).
    cached = await session.execute(
        text(
            f"SELECT spans, counts FROM {schema}.llm_prelabel_jobs "
            "WHERE document_id = :doc_id AND content_hash = :content_hash "
            "  AND config_version = :config_version AND status = 'completed' "
            "ORDER BY completed_at DESC LIMIT 1"
        ),
        {"doc_id": doc_id, "content_hash": content_hash, "config_version": config_version},
    )
    cached_row = cached.fetchone()

    await session.execute(
        text(
            f"INSERT INTO {schema}.llm_prelabel_jobs "
            "(id, document_id, status, content_hash, config_version, served_from_cache, "
            " spans, counts, completed_at) "
            "VALUES (:id, :doc_id, :status, :content_hash, :config_version, :cached, "
            "        CAST(:spans AS JSONB), CAST(:counts AS JSONB), :completed_at)"
        ),
        {
            "id": job_id,
            "doc_id": doc_id,
            "status": "completed" if cached_row else "queued",
            "content_hash": content_hash,
            "config_version": config_version,
            "cached": bool(cached_row),
            "spans": json.dumps(_coerce_json(cached_row[0]) or []) if cached_row else None,
            "counts": json.dumps(_coerce_json(cached_row[1]) or {}) if cached_row else None,
            "completed_at": datetime.now(timezone.utc) if cached_row else None,
        },
    )

    if cached_row:
        # Re-materialised rather than assumed still present: a keyword pre-label run between the
        # two triggers replaces every suggestion for the document, and "served from cache" has
        # to mean the suggestions are there now, not that they once were.
        await _replace_suggested_spans(
            session, schema, doc_id, _coerce_json(cached_row[0]) or []
        )

    await session.commit()

    if not cached_row:
        celery_app.send_task(
            "run_llm_prelabel",
            args=[tenant_id, doc_id, job_id],
            queue=settings.annotation_llm_celery_queue,
        )

    return {
        "job_id": job_id,
        "status": "completed" if cached_row else "queued",
        "cached": bool(cached_row),
    }


@router.get("/api/v1/documents/{doc_id}/prelabel/llm/{job_id}")
async def get_llm_prelabel_job(
    doc_id: str,
    job_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Job status, and on completion the counts behind it.

    `counts` is not decoration: design.md flags the grounding drop rate as the main risk of the
    extractive-only contract, and a returned-vs-grounded ratio nobody can read is a risk nobody
    can see. The spans themselves are fetched through the existing
    `/spans?type=suggested` listing rather than duplicated here."""
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(
            f"SELECT id, status, served_from_cache, counts, error_message, created_at, "
            f"       completed_at FROM {schema}.llm_prelabel_jobs "
            "WHERE id = :id AND document_id = :doc_id LIMIT 1"
        ),
        {"id": job_id, "doc_id": doc_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("LLMPrelabelJob", job_id)

    return {
        "job_id": row[0],
        "status": row[1],
        "cached": row[2],
        "counts": _coerce_json(row[3]) or {},
        "error_message": row[4],
        "created_at": str(row[5]),
        "completed_at": str(row[6]) if row[6] else None,
    }
