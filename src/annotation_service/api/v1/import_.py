import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

router = APIRouter(tags=["annotation-import"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


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
            tokens.append(parts[0].strip())
            tags.append(parts[1].strip())
        if tokens:
            rows.append({"tokens": tokens, "tags": tags})
    if not rows:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "File contains no valid annotation rows"},
        )
    return rows


async def validate_entity_types(session: AsyncSession, tenant_id: str, rows: list[dict]) -> None:
    unique_types: set[str] = set()
    for row in rows:
        for tag in row["tags"]:
            if tag != "O":
                unique_types.add(strip_bio_prefix(tag))

    if not unique_types:
        return

    result = await session.execute(
        text("SELECT name FROM public.entity_definitions WHERE tenant_id = :tenant_id AND name = ANY(:names)"),
        {"tenant_id": tenant_id, "names": list(unique_types)},
    )
    known = {row[0] for row in result.fetchall()}
    unknown = unique_types - known
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNKNOWN_ENTITY_TYPES",
                "message": f"Unrecognized entity type(s): {', '.join(sorted(unknown))}",
                "unknown_types": sorted(unknown),
            },
        )


ACCEPTED_MIME_TYPES = {
    "application/json",
    "application/jsonl",
    "text/plain",
    "application/octet-stream",
}
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("/api/v1/annotation-import", status_code=201)
async def import_annotations(
    file: UploadFile,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
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

    await validate_entity_types(session, tenant_id, rows)

    for idx, row in enumerate(rows):
        await session.execute(
            text(f"""
                INSERT INTO {schema}.imported_annotations (id, tokens, tags, source_file, row_index)
                VALUES (:id, :tokens, :tags, :source_file, :row_index)
            """),
            {
                "id": generate_uuid(),
                "tokens": row["tokens"],
                "tags": row["tags"],
                "source_file": filename,
                "row_index": idx,
            },
        )

    await session.commit()

    return {"imported_count": len(rows)}
