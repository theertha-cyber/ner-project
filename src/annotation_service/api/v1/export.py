import json
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["export"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def get_tenant_id(request: Request) -> str:
    from fastapi import HTTPException
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


def _tokenize(text_val: str) -> list[str]:
    return text_val.split()


def _bio_tags(tokens: list[str], spans: list[dict], entity_types_filter: set[str] | None, text_val: str = "") -> list[str]:
    tags = ["O"] * len(tokens)
    char_offset = 0
    for i, token in enumerate(tokens):
        token_start = char_offset
        token_end = char_offset + len(token)
        for span in spans:
            if entity_types_filter and span["entity_type"] not in entity_types_filter:
                continue
            if span["char_start"] <= token_start < span["char_end"] or span["char_start"] < token_end <= span["char_end"]:
                if token_start == span["char_start"]:
                    tags[i] = f"B-{span['entity_type']}"
                elif tags[i] == "O":
                    tags[i] = f"I-{span['entity_type']}"
                break
        char_offset = token_start + len(token)
        if text_val and char_offset < len(text_val) and text_val[char_offset] == " ":
            char_offset += 1
    return tags


@router.get("/api/v1/annotation-export")
async def export_annotations(
    entity_types: str | None = Query(None, alias="entity_types"),
    document_ids: str | None = Query(None, alias="document_ids"),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    type_filter_set: set[str] | None = None
    if entity_types:
        type_filter_set = set(et.strip() for et in entity_types.split(","))

    if document_ids:
        ids = [did.strip() for did in document_ids.split(",")]
        result = await session.execute(
            text(f"SELECT document_id, text FROM {schema}.document_text_spans WHERE document_id = ANY(:ids) ORDER BY document_id, span_index"),
            {"ids": ids},
        )
    else:
        result = await session.execute(
            text(f"SELECT document_id, text FROM {schema}.document_text_spans ORDER BY document_id, span_index"),
        )

    rows = result.fetchall()

    text_by_doc: dict[str, str] = {}
    for r in rows:
        doc_id = r[0]
        if doc_id not in text_by_doc:
            text_by_doc[doc_id] = ""
        text_by_doc[doc_id] += (r[1] or "")

    doc_ids = list(text_by_doc.keys())

    lines: list[str] = []

    if doc_ids:
        spans_result = await session.execute(
            text(f"SELECT document_id, entity_type, char_start, char_end, bio_tags FROM {schema}.spans WHERE document_id = ANY(:ids) ORDER BY document_id, char_start"),
            {"ids": doc_ids},
        )
        spans_rows = spans_result.fetchall()

        spans_by_doc: dict[str, list[dict]] = {}
        for sr in spans_rows:
            d_id = sr[0]
            if d_id not in spans_by_doc:
                spans_by_doc[d_id] = []
            spans_by_doc[d_id].append({
                "entity_type": sr[1],
                "char_start": sr[2],
                "char_end": sr[3],
                "bio_tags": sr[4],
            })

        for d_id in doc_ids:
            text_val = text_by_doc[d_id]
            tokens = _tokenize(text_val)
            doc_spans = spans_by_doc.get(d_id, [])

            span_token_counters: dict[int, int] = {}
            tags = ["O"] * len(tokens)
            char_offset = 0
            for idx, token in enumerate(tokens):
                token_start = char_offset
                token_end = char_offset + len(token)
                char_offset = token_end
                if char_offset < len(text_val) and text_val[char_offset] == " ":
                    char_offset += 1
                for span_idx, span in enumerate(doc_spans):
                    if type_filter_set and span["entity_type"] not in type_filter_set:
                        continue
                    if not (token_end > span["char_start"] and token_start < span["char_end"]):
                        continue
                    stored = span["bio_tags"]
                    if stored:
                        counter = span_token_counters.get(span_idx, 0)
                        if counter < len(stored):
                            tags[idx] = stored[counter]
                        span_token_counters[span_idx] = counter + 1
                    else:
                        if token_start == span["char_start"]:
                            tags[idx] = f"B-{span['entity_type']}"
                        elif tags[idx] == "O":
                            tags[idx] = f"I-{span['entity_type']}"
                    break

            lines.append(json.dumps({"tokens": tokens, "tags": tags}))

    imported_result = await session.execute(
        text(f"SELECT tokens, tags FROM {schema}.imported_annotations ORDER BY source_file, row_index"),
    )
    for ir in imported_result.fetchall():
        tokens = list(ir[0])
        tags = list(ir[1])
        if type_filter_set:
            tags = [
                t if t == "O" or (t.startswith("B-") or t.startswith("I-")) and t[2:] in type_filter_set else "O"
                for t in tags
            ]
        lines.append(json.dumps({"tokens": tokens, "tags": tags}))

    return PlainTextResponse("\n".join(lines) + "\n", media_type="application/jsonl")
