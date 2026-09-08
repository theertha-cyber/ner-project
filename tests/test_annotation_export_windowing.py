"""Windowing in the annotation export.

Covers verification.md Spec Alignment rows 2-4 and 10 for change
`training-data-integrity`.

Export used to emit exactly one JSONL record per document, so a 600-word résumé became
one row that the training worker then truncated to its first ~90 words. Export now
emits one record per bounded, overlapping window of source tokens.
"""

import json
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.annotation_service.api.v1.export import WINDOW_OVERLAP_TOKENS, WINDOW_TOKENS

from tests.test_annotation_export_offsets import seed_document
from tests.test_annotation_workspace import (  # noqa: F401
    auth_header,
    client,
    cleanup_public,
    make_token,
    seeded_entity_types,
    seeded_tenant,
)


def numbered_document(token_count: int) -> tuple[str, list[tuple[int, int]]]:
    """Build text of `token_count` uniquely-named tokens plus each token's offsets.

    Tokens are separated by a newline rather than a space so that windowing is
    exercised on the same whitespace shape OCR actually produces.
    """
    offsets = []
    parts = []
    cursor = 0
    for i in range(token_count):
        if i:
            cursor += 1  # the "\n" separator
        token = f"tok{i}"
        offsets.append((cursor, cursor + len(token)))
        parts.append(token)
        cursor += len(token)
    return "\n".join(parts), offsets


def records_of(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.strip().split("\n") if line]


@pytest.mark.asyncio
async def test_long_document_produces_multiple_records(seeded_entity_types, client):
    """verification.md row 2."""
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    token_count = WINDOW_TOKENS * 2 + 5
    content, _offsets = numbered_document(token_count)
    await seed_document(schema, tid, content, [])

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    records = records_of(resp)
    assert len(records) > 1

    for record in records:
        assert len(record["tokens"]) == len(record["tags"])
        assert len(record["tokens"]) <= WINDOW_TOKENS

    covered = {tok for record in records for tok in record["tokens"]}
    assert covered == {f"tok{i}" for i in range(token_count)}


@pytest.mark.asyncio
async def test_consecutive_windows_overlap(seeded_entity_types, client):
    """verification.md row 3."""
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    content, _offsets = numbered_document(WINDOW_TOKENS + WINDOW_OVERLAP_TOKENS)
    await seed_document(schema, tid, content, [])

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    records = records_of(resp)
    assert len(records) >= 2

    first, second = records[0], records[1]
    assert first["tokens"][-WINDOW_OVERLAP_TOKENS:] == second["tokens"][:WINDOW_OVERLAP_TOKENS]
    assert first["tags"][-WINDOW_OVERLAP_TOKENS:] == second["tags"][:WINDOW_OVERLAP_TOKENS]


@pytest.mark.asyncio
async def test_boundary_entity_complete_in_one_window(seeded_entity_types, client):
    """verification.md row 4.

    The entity straddles the trailing edge of the first window — the hardest placement,
    where a no-overlap implementation would leave `B-` in one record and `I-` in the
    next and so manufacture two partial entities out of one real one.
    """
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    token_count = WINDOW_TOKENS * 2
    content, offsets = numbered_document(token_count)

    first_idx = WINDOW_TOKENS - 1
    span_start = offsets[first_idx][0]
    span_end = offsets[first_idx + 1][1]
    assert content[span_start:span_end] == f"tok{first_idx}\ntok{first_idx + 1}"

    await seed_document(
        schema,
        tid,
        content,
        [{"entity_type": "organization", "char_start": span_start, "char_end": span_end}],
    )

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    records = records_of(resp)

    first_token = f"tok{first_idx}"
    second_token = f"tok{first_idx + 1}"

    complete = [
        record for record in records
        if first_token in record["tokens"] and second_token in record["tokens"]
    ]
    assert complete, "no window contains both tokens of the boundary entity"

    record = complete[0]
    assert record["tags"][record["tokens"].index(first_token)] == "B-organization"
    assert record["tags"][record["tokens"].index(second_token)] == "I-organization"


@pytest.mark.asyncio
async def test_imported_rows_not_windowed(seeded_entity_types, client):
    """verification.md row 10.

    Imported rows arrive already row-sized and pre-tagged. Routing them through
    windowing would re-split data that was never a document in the first place, so the
    oversized row here must come back byte-for-byte.
    """
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    oversized_tokens = [f"imp{i}" for i in range(WINDOW_TOKENS * 3)]
    oversized_tags = ["O"] * len(oversized_tokens)
    rows = [
        (["Alpha", "Beta"], ["B-organization", "I-organization"]),
        (oversized_tokens, oversized_tags),
        (["Gamma"], ["O"]),
    ]

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        for idx, (tokens, tags) in enumerate(rows):
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.imported_annotations (id, tokens, tags, source_file, row_index) "
                    "VALUES (:id, :tokens, :tags, 'imported.jsonl', :row_index)"
                ),
                {"id": str(uuid.uuid4()), "tokens": tokens, "tags": tags, "row_index": idx},
            )
    await engine.dispose()

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    records = records_of(resp)

    # No documents were seeded, so every emitted line is an imported row.
    assert len(records) == 3
    assert records[1]["tokens"] == oversized_tokens
    assert records[1]["tags"] == oversized_tags
