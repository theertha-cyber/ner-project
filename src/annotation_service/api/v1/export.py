import json
import re
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi.responses import PlainTextResponse
from src.shared.tenant_schema import schema_for_tenant as _schema

router = APIRouter(tags=["export"])

# Manual, Automated, and Import are independent workflows (manual-training-data-source-
# scoping) — a training job scoped to one of these trains only on that workflow's data.
SOURCE_MANUAL = "manual"
SOURCE_AUTOMATED = "automated"
SOURCE_IMPORT = "import"
VALID_SOURCES = (SOURCE_MANUAL, SOURCE_AUTOMATED, SOURCE_IMPORT)


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


_TOKEN_RE = re.compile(r"\S+")

# Window sizing. Both values are measured against the real corpus (553 résumé
# documents in `annotations.jsonl`), not guessed — see the change's tasks.md § 1.3.
#
# WINDOW_TOKENS pairs with the training worker's DEFAULT_MAX_SEQ_LENGTH (512, BERT's
# positional-embedding hard limit). Subword expansion under `dslim/bert-base-NER`
# measured over that corpus is mean 1.99 and max 3.64 subwords per source token; 128
# source tokens therefore has an allowance of (512 - 2 specials) / 128 = 3.98 subwords
# per token, above the observed worst case. The two constants are derived from one
# another: change one and the other must be re-derived.
WINDOW_TOKENS = 128

# Overlap must exceed the longest entity in the corpus so a single entity can never be
# split across every window it appears in. The longest observed entity is 58 source
# tokens (p95 = 5, p99 = 7), so 64 clears it with margin while staying a clean half of
# the window.
WINDOW_OVERLAP_TOKENS = 64


def _window_ranges(token_count: int) -> list[tuple[int, int]]:
    """Index ranges of the windows covering `token_count` tokens.

    A document within the budget yields exactly one window, preserving the previous
    one-record-per-short-document behaviour.
    """
    if token_count <= WINDOW_TOKENS:
        return [(0, token_count)]
    stride = WINDOW_TOKENS - WINDOW_OVERLAP_TOKENS
    ranges = []
    start = 0
    while start < token_count:
        end = min(start + WINDOW_TOKENS, token_count)
        ranges.append((start, end))
        if end == token_count:
            break
        start += stride
    return ranges


def _tokenize_with_offsets(text_val: str) -> list[tuple[str, int, int]]:
    """Yield `(token, char_start, char_end)` for every whitespace-delimited token.

    Tokenisation and offset derivation are one pass on purpose. They used to be two:
    tokens came from `str.split()` (which splits on any whitespace run) while offsets
    came from a walk that advanced past exactly one `" "`. Any newline, tab or repeated
    space desynchronised the two permanently, so every token after the first such
    separator carried another token's tag. Deriving both from the same match makes that
    class of drift structurally impossible rather than arithmetically fixed.
    """
    return [(m.group(), m.start(), m.end()) for m in _TOKEN_RE.finditer(text_val)]


def _bio_tags_from_offsets(
    tokens_with_offsets: list[tuple[str, int, int]],
    spans: list[dict],
    entity_types_filter: set[str] | None,
) -> list[str]:
    """Derive BIO tags purely from each span's `char_start`/`char_end`.

    The stored `bio_tags` column is deliberately not consulted: it is written by
    `spans.py` using the same single-space assumption this module just removed, so it
    is a second independently-drifting source. Span offsets are what the annotator
    actually drew, so they are the authority.
    """
    tags = ["O"] * len(tokens_with_offsets)
    for idx, (_token, token_start, token_end) in enumerate(tokens_with_offsets):
        for span in spans:
            if entity_types_filter and span["entity_type"] not in entity_types_filter:
                continue
            if not (token_end > span["char_start"] and token_start < span["char_end"]):
                continue
            if token_start <= span["char_start"] < token_end:
                tags[idx] = f"B-{span['entity_type']}"
            elif tags[idx] == "O":
                tags[idx] = f"I-{span['entity_type']}"
            break
    return tags


@router.get("/api/v1/annotation-export")
async def export_annotations(
    entity_types: str | None = Query(None, alias="entity_types"),
    document_ids: str | None = Query(None, alias="document_ids"),
    source: str | None = Query(
        None,
        description=(
            "Restrict the export to one workflow's data: 'manual' (spans with no "
            "span_batch_provenance row), 'automated' (spans promoted from a batch), or "
            "'import' (imported_annotations rows only). Omit for every source combined."
        ),
    ),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    if source is not None and source not in VALID_SOURCES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_SOURCE",
                "message": f"source must be one of {list(VALID_SOURCES)}",
            },
        )

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

    # Import lives in a wholly separate table (`imported_annotations`) and never becomes a
    # `spans` row, so scoping to 'import' skips the spans query entirely rather than filtering
    # it to zero rows.
    if doc_ids and source != SOURCE_IMPORT:
        # A span with a `span_batch_provenance` row was promoted from an accepted automated
        # batch; every other confirmed span is manual (workspace / review-queue). Same
        # distinction `accumulation.py`'s `by_source` breakdown already uses.
        if source == SOURCE_AUTOMATED:
            provenance_join = f"JOIN {schema}.span_batch_provenance bp ON bp.span_id = sp.id"
        elif source == SOURCE_MANUAL:
            provenance_join = (
                f"LEFT JOIN {schema}.span_batch_provenance bp ON bp.span_id = sp.id"
            )
        else:
            provenance_join = ""
        source_clause = ""
        if source == SOURCE_MANUAL:
            source_clause = " AND bp.span_id IS NULL"

        spans_result = await session.execute(
            text(
                f"SELECT sp.document_id, sp.entity_type, sp.char_start, sp.char_end "
                f"FROM {schema}.spans sp {provenance_join} "
                f"WHERE sp.document_id = ANY(:ids){source_clause} "
                "ORDER BY sp.document_id, sp.char_start"
            ),
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
            })

        for d_id in doc_ids:
            text_val = text_by_doc[d_id]
            tokens_with_offsets = _tokenize_with_offsets(text_val)
            doc_spans = spans_by_doc.get(d_id, [])

            tokens = [t for t, _s, _e in tokens_with_offsets]
            tags = _bio_tags_from_offsets(tokens_with_offsets, doc_spans, type_filter_set)

            # Tokens and tags are sliced with the same index range so they cannot
            # desynchronise: one range, applied to both.
            for win_start, win_end in _window_ranges(len(tokens)):
                lines.append(json.dumps({
                    "tokens": tokens[win_start:win_end],
                    "tags": tags[win_start:win_end],
                }))

    # Imported rows join the training set only from files that are training-eligible
    # (every row imported, no unmapped type) and only for rows not still pending a type
    # mapping. Tagged with a source marker so a consumer can tell them from span-derived
    # rows (import-annotation-training-eligibility change). Skipped entirely when scoped to
    # 'manual' or 'automated' — imports are a third, independent workflow, not a fallback.
    if source in (None, SOURCE_IMPORT):
        imported_result = await session.execute(
            text(
                f"SELECT ia.tokens, ia.tags FROM {schema}.imported_annotations ia "
                f"LEFT JOIN {schema}.annotation_imports ai ON ai.source_file = ia.source_file "
                "WHERE ia.pending_mapping = FALSE "
                # A file with a header contributes only once it is training-eligible; rows with
                # no header at all are legacy imports (predating the header table) and stay in.
                "AND (ai.source_file IS NULL OR ai.training_eligible_at IS NOT NULL) "
                "ORDER BY ia.source_file, ia.row_index"
            ),
        )
        for ir in imported_result.fetchall():
            tokens = list(ir[0])
            tags = list(ir[1])
            if type_filter_set:
                tags = [
                    t if t == "O" or (t.startswith("B-") or t.startswith("I-")) and t[2:] in type_filter_set else "O"
                    for t in tags
                ]
            lines.append(json.dumps({"tokens": tokens, "tags": tags, "source": "import"}))

    return PlainTextResponse("\n".join(lines) + "\n", media_type="application/jsonl")
