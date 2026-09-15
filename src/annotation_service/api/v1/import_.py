import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.tenant_schema import schema_for_tenant as _schema

from src.annotation_service.api.v1._rbac import require_tenant_admin

router = APIRouter(tags=["annotation-import"])


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def generate_uuid():
    return str(uuid.uuid4())


def strip_bio_prefix(tag: str) -> str:
    if tag.startswith("B-") or tag.startswith("I-"):
        return tag[2:]
    return tag


def _strip_null_bytes(value: str) -> str:
    # Postgres text columns reject 0x00 regardless of encoding; source files
    # (e.g. PDF-to-text extractions) sometimes embed stray null bytes.
    return value.replace("\x00", "")


def parse_jsonl(content: str) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "PARSE_ERROR", "message": f"Invalid JSON at line {i}: {exc.msg}"},
            )
        if not isinstance(obj, dict):
            raise HTTPException(
                status_code=422,
                detail={"code": "PARSE_ERROR", "message": f"Line {i}: expected a JSON object, got {type(obj).__name__}"},
            )
        tokens = obj.get("tokens")
        tags = obj.get("tags")
        if not isinstance(tokens, list) or not isinstance(tags, list):
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": f"Line {i}: 'tokens' and 'tags' must be arrays"},
            )
        if len(tokens) != len(tags):
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": f"Line {i}: 'tokens' and 'tags' must have equal length"},
            )
        tokens = [_strip_null_bytes(t) if isinstance(t, str) else t for t in tokens]
        rows.append({"tokens": tokens, "tags": tags})
    if not rows:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "File contains no valid annotation rows"},
        )
    return rows


def parse_conll(content: str) -> list[dict]:
    rows: list[dict] = []
    sentences = content.strip().split("\n\n")
    for sent_idx, sentence in enumerate(sentences, start=1):
        stripped = sentence.strip()
        if not stripped:
            continue
        tokens: list[str] = []
        tags: list[str] = []
        for line_idx, line in enumerate(stripped.split("\n"), start=1):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "PARSE_ERROR", "message": f"CoNLL line {line_idx} in sentence {sent_idx}: expected token and tag separated by tab"},
                )
            tokens.append(_strip_null_bytes(parts[0].strip()))
            tags.append(parts[1].strip())
        if tokens:
            rows.append({"tokens": tokens, "tags": tags})
    if not rows:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "File contains no valid annotation rows"},
        )
    return rows


async def get_known_entity_types_lower(session: AsyncSession, tenant_id: str) -> set[str]:
    result = await session.execute(
        text("SELECT LOWER(name) FROM public.entity_definitions WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    return {row[0] for row in result.fetchall()}


def compute_entity_type_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        seen_in_row: set[str] = set()
        for tag in row["tags"]:
            if tag != "O":
                base = strip_bio_prefix(tag)
                if base not in seen_in_row:
                    seen_in_row.add(base)
                    counts[base] = counts.get(base, 0) + 1
    return counts


ACCEPTED_MIME_TYPES = {
    "application/json",
    "application/jsonl",
    "text/plain",
    "application/octet-stream",
}
MAX_FILE_SIZE = 50 * 1024 * 1024


def _row_unknown_types(tags: list[str], known_lower: set[str]) -> set[str]:
    unknown: set[str] = set()
    for tag in tags:
        if tag != "O":
            base = strip_bio_prefix(tag)
            if base.lower() not in known_lower:
                unknown.add(base)
    return unknown


async def _unmapped_types_for_file(
    session: AsyncSession, schema: str, source_file: str, known_lower: set[str]
) -> dict[str, int]:
    """Unique unknown base types still referenced by this file's pending rows, with the
    number of rows each appears in — the same shape the import-time response uses, so the
    UI can offer a bulk "create all as new types" action after the fact."""
    rows = await session.execute(
        text(
            f"SELECT tags FROM {schema}.imported_annotations "
            "WHERE source_file = :f AND pending_mapping = TRUE"
        ),
        {"f": source_file},
    )
    counts: dict[str, int] = {}
    for (tags,) in rows.fetchall():
        for t in _row_unknown_types(list(tags), known_lower):
            counts[t] = counts.get(t, 0) + 1
    return counts


async def _refresh_import_header(session: AsyncSession, schema: str, source_file: str) -> bool:
    """Recompute a file's pending count and set `training_eligible_at` when it hits zero.
    Returns whether the file is now training-eligible."""
    pending = await session.execute(
        text(
            f"SELECT COUNT(*) FROM {schema}.imported_annotations "
            "WHERE source_file = :f AND pending_mapping = TRUE"
        ),
        {"f": source_file},
    )
    pending_count = int(pending.scalar() or 0)
    if pending_count == 0:
        await session.execute(
            text(
                f"UPDATE {schema}.annotation_imports "
                "SET training_eligible_at = COALESCE(training_eligible_at, NOW()) "
                "WHERE source_file = :f"
            ),
            {"f": source_file},
        )
        return True
    await session.execute(
        text(
            f"UPDATE {schema}.annotation_imports SET training_eligible_at = NULL "
            "WHERE source_file = :f"
        ),
        {"f": source_file},
    )
    return False


@router.post("/api/v1/annotation-import", status_code=201)
async def import_annotations(
    file: UploadFile,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    content_type = file.content_type or ""
    if content_type and content_type not in ACCEPTED_MIME_TYPES and not content_type.endswith("+json"):
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_MEDIA_TYPE", "message": f"Unsupported MIME type: {content_type}"},
        )

    raw = await file.read()
    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"File exceeds maximum size of 50MB"},
        )

    content = raw.decode("utf-8")

    filename = file.filename or "unknown"
    is_conll = filename.endswith(".txt") or not (filename.endswith(".json") or filename.endswith(".jsonl"))

    if is_conll:
        rows = parse_conll(content)
    else:
        rows = parse_jsonl(content)

    known_lower = await get_known_entity_types_lower(session, tenant_id)

    # Every parsed row is stored. A row whose tags reference a type the tenant has not
    # defined is stored `pending_mapping = TRUE` rather than dropped — it is resolved by
    # the type-map endpoint, never lost (spec: "held, not dropped").
    unmapped: dict[str, int] = {}
    usable_rows: list[dict] = []
    pending_count = 0
    for idx, row in enumerate(rows):
        row_unknown = _row_unknown_types(row["tags"], known_lower)
        is_pending = bool(row_unknown)
        if is_pending:
            pending_count += 1
            for t in row_unknown:
                unmapped[t] = unmapped.get(t, 0) + 1
        else:
            usable_rows.append(row)
        await session.execute(
            text(
                f"INSERT INTO {schema}.imported_annotations "
                "(id, tokens, tags, source_file, row_index, pending_mapping) "
                "VALUES (:id, :tokens, :tags, :source_file, :row_index, :pending)"
            ),
            {
                "id": generate_uuid(),
                "tokens": row["tokens"],
                "tags": row["tags"],
                "source_file": filename,
                "row_index": idx,
                "pending": is_pending,
            },
        )

    await session.execute(
        text(
            f"INSERT INTO {schema}.annotation_imports (source_file, row_count) "
            "VALUES (:f, :n) "
            "ON CONFLICT (source_file) DO UPDATE SET row_count = "
            f"  (SELECT COUNT(*) FROM {schema}.imported_annotations WHERE source_file = :f)"
        ),
        {"f": filename, "n": len(rows)},
    )
    await _refresh_import_header(session, schema, filename)
    await session.commit()

    entity_type_counts = compute_entity_type_counts(usable_rows)

    return {
        "source_file": filename,
        # Rows stored and immediately usable (no unmapped type).
        "imported_count": len(usable_rows),
        "pending_count": pending_count,
        "unmapped_types": [
            {"type": t, "row_count": n} for t, n in sorted(unmapped.items())
        ],
        # Retained for genuinely unparseable rows; parse errors currently 422 upstream.
        "warnings": [],
        # Back-compat: was the count of dropped rows, now the count held pending mapping.
        "skipped_count": pending_count,
        "entity_type_counts": entity_type_counts,
    }


@router.get("/api/v1/annotation-imports")
async def list_import_files(
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """One row per imported file: its size, how many rows still need a type mapping,
    whether it is training-eligible, and the resolved type map."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    rows = await session.execute(
        text(
            f"SELECT ai.source_file, ai.row_count, ai.type_map, ai.training_eligible_at, "
            f"  (SELECT COUNT(*) FROM {schema}.imported_annotations x "
            f"   WHERE x.source_file = ai.source_file AND x.pending_mapping = TRUE) AS pending, "
            f"  (SELECT COUNT(*) FROM {schema}.imported_annotations x "
            f"   WHERE x.source_file = ai.source_file AND x.reviewed = TRUE) AS reviewed "
            f"FROM {schema}.annotation_imports ai ORDER BY ai.created_at DESC"
        )
    )
    rows = rows.fetchall()
    known_lower = await get_known_entity_types_lower(session, tenant_id) if any(r[4] for r in rows) else set()

    files = []
    for r in rows:
        type_map = r[2]
        if isinstance(type_map, str):
            type_map = json.loads(type_map)
        pending_count = int(r[4] or 0)
        unmapped_types = (
            await _unmapped_types_for_file(session, schema, r[0], known_lower)
            if pending_count
            else {}
        )
        files.append(
            {
                "source_file": r[0],
                "row_count": r[1],
                "type_map": type_map or {},
                "training_eligible": r[3] is not None,
                "training_eligible_at": r[3].isoformat() if r[3] else None,
                "pending_count": pending_count,
                "reviewed_count": int(r[5] or 0),
                "unmapped_types": [
                    {"type": t, "row_count": n} for t, n in sorted(unmapped_types.items())
                ],
            }
        )
    return {"files": files}


@router.post("/api/v1/annotation-imports/{source_file}/type-map", status_code=201)
async def map_import_types(
    source_file: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Resolve a file's unmapped entity types. Each key maps a stored (unknown) type to
    either an existing entity type (`{"to": "<name>"}`) or a new one (`{"create": true}`),
    which is created through the entity-config API with `provenance = 'imported'`. Affected
    rows' tags are rewritten (BIO-prefix preserved); when no unmapped type remains the file
    becomes training-eligible."""
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    mapping = body.get("mapping") if isinstance(body.get("mapping"), dict) else body
    if not isinstance(mapping, dict) or not mapping:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "A non-empty type mapping is required"},
        )

    exists = await session.execute(
        text(f"SELECT 1 FROM {schema}.annotation_imports WHERE source_file = :f"),
        {"f": source_file},
    )
    if not exists.fetchone():
        raise HTTPException(status_code=404, detail="Imported file not found")

    from src.gateway.services.entity_service import EntityService

    known_lower = await get_known_entity_types_lower(session, tenant_id)
    applied: dict[str, dict] = {}

    for src_type, spec in mapping.items():
        spec = spec or {}
        if spec.get("create"):
            await EntityService(session).create_entity_type(
                tenant_id,
                {"name": src_type, "provenance": "imported", "provenance_ref": source_file},
            )
            target = src_type
            applied[src_type] = {"to": target, "created": True}
        else:
            target = spec.get("to")
            if not target or target.lower() not in (
                known_lower | {a["to"].lower() for a in applied.values()}
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "UNKNOWN_TARGET_TYPE",
                        "message": f"Target entity type '{target}' for '{src_type}' is not defined",
                    },
                )
            applied[src_type] = {"to": target, "created": False}

        # Rewrite tags on rows of this file that reference `src_type` (whole base type,
        # BIO prefix preserved).
        file_rows = await session.execute(
            text(
                f"SELECT id, tags FROM {schema}.imported_annotations WHERE source_file = :f"
            ),
            {"f": source_file},
        )
        for row_id, tags in file_rows.fetchall():
            new_tags = []
            changed = False
            for tag in list(tags):
                if tag != "O" and strip_bio_prefix(tag) == src_type:
                    prefix = tag[:2] if tag[:2] in ("B-", "I-") else ""
                    new_tags.append(f"{prefix}{target}")
                    changed = True
                else:
                    new_tags.append(tag)
            if changed:
                await session.execute(
                    text(
                        f"UPDATE {schema}.imported_annotations SET tags = :tags WHERE id = :id"
                    ),
                    {"tags": new_tags, "id": row_id},
                )

    # A row is still pending if any of its tags remain unknown after this mapping.
    refreshed_known = await get_known_entity_types_lower(session, tenant_id)
    all_rows = await session.execute(
        text(f"SELECT id, tags FROM {schema}.imported_annotations WHERE source_file = :f"),
        {"f": source_file},
    )
    for row_id, tags in all_rows.fetchall():
        still_pending = bool(_row_unknown_types(list(tags), refreshed_known))
        await session.execute(
            text(
                f"UPDATE {schema}.imported_annotations SET pending_mapping = :p WHERE id = :id"
            ),
            {"p": still_pending, "id": row_id},
        )

    # Merge into the header's type_map and recompute eligibility.
    header = await session.execute(
        text(f"SELECT type_map FROM {schema}.annotation_imports WHERE source_file = :f"),
        {"f": source_file},
    )
    existing_map = header.scalar()
    if isinstance(existing_map, str):
        existing_map = json.loads(existing_map)
    merged = {**(existing_map or {}), **applied}
    await session.execute(
        text(
            f"UPDATE {schema}.annotation_imports SET type_map = CAST(:m AS JSONB) "
            "WHERE source_file = :f"
        ),
        {"m": json.dumps(merged), "f": source_file},
    )
    eligible = await _refresh_import_header(session, schema, source_file)
    await session.commit()

    return {"source_file": source_file, "type_map": merged, "training_eligible": eligible}
