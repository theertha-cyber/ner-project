"""Token/tag alignment in the annotation export.

Covers verification.md Spec Alignment rows 5-7 for change `training-data-integrity`.

The defect these tests pin down: `_tokenize` splits on any whitespace run, but the
offset walk that assigns BIO tags advanced past exactly one `" "`. After the first
newline, tab, or repeated space every subsequent token's computed offsets drift and
tags attach to the wrong tokens. OCR'd documents are multi-line by nature, so this
was the normal case rather than an edge case.
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

# Reuse the annotation-workspace tenant fixtures rather than restating the schema DDL.
from tests.test_annotation_workspace import (  # noqa: F401
    auth_header,
    client,
    cleanup_public,
    make_token,
    seeded_entity_types,
    seeded_tenant,
)


async def seed_document(schema: str, tid: str, text_content: str, spans: list[dict]) -> str:
    """Insert one document with `text_content` and the given confirmed spans.

    Each span dict takes `entity_type`, `char_start`, `char_end` and optionally
    `bio_tags` (the stored column, deliberately settable to a wrong value).
    """
    doc_id = str(uuid.uuid4())
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, content_type, file_size, status, purpose) "
                "VALUES (:id, :tid, 'offsets.txt', 'text/plain', 100, 'processed', 'training')"
            ),
            {"id": doc_id, "tid": tid},
        )
        await conn.execute(
            text(
                f'INSERT INTO {schema}.document_text_spans (id, document_id, span_index, "text", char_start, char_end, page_number) '
                "VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)"
            ),
            {
                "sid": str(uuid.uuid4()),
                "doc_id": doc_id,
                "txt": text_content,
                "length": len(text_content),
            },
        )
        for span in spans:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence, bio_tags) "
                    "VALUES (:sid, :doc_id, :etype, :start, :end, :content, 1.0, :bio)"
                ),
                {
                    "sid": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "etype": span["entity_type"],
                    "start": span["char_start"],
                    "end": span["char_end"],
                    "content": text_content[span["char_start"]:span["char_end"]],
                    "bio": span.get("bio_tags"),
                },
            )
    await engine.dispose()
    return doc_id


def only_record(resp) -> dict:
    lines = [line for line in resp.text.strip().split("\n") if line]
    assert len(lines) == 1, f"Expected exactly one exported record, got {len(lines)}"
    return json.loads(lines[0])


def tag_of(record: dict, token: str) -> str:
    assert token in record["tokens"], f"{token!r} not in {record['tokens']}"
    return record["tags"][record["tokens"].index(token)]


@pytest.mark.asyncio
async def test_tags_align_across_newline(seeded_entity_types, client):
    """verification.md row 5.

    The exact case verified by hand in the proposal: with a newline separator the old
    walk computed `"Acme"` at offsets (15, 19), which is the substring `"at A"`.
    """
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    content = "John Doe\nworks at Acme Corp"
    assert content[18:27] == "Acme Corp"
    await seed_document(
        schema,
        tid,
        content,
        [{"entity_type": "organization", "char_start": 18, "char_end": 27}],
    )

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    record = only_record(resp)
    assert record["tokens"] == ["John", "Doe", "works", "at", "Acme", "Corp"]
    assert tag_of(record, "Acme") == "B-organization"
    assert tag_of(record, "Corp") == "I-organization"
    assert tag_of(record, "works") == "O"
    assert tag_of(record, "at") == "O"


@pytest.mark.asyncio
async def test_tags_align_across_tabs_and_double_spaces(seeded_entity_types, client):
    """verification.md row 6.

    Establishes the defect is whitespace-general, not newline-specific — a fix that
    only special-cases `\\n` passes row 5 and fails here.
    """
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    content = "John  Doe\tworks at Acme Corp"
    assert content[19:28] == "Acme Corp"
    await seed_document(
        schema,
        tid,
        content,
        [{"entity_type": "organization", "char_start": 19, "char_end": 28}],
    )

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    record = only_record(resp)
    assert record["tokens"] == ["John", "Doe", "works", "at", "Acme", "Corp"]
    assert tag_of(record, "Acme") == "B-organization"
    assert tag_of(record, "Corp") == "I-organization"
    organization_tagged = [
        tok for tok, tag in zip(record["tokens"], record["tags"]) if tag.endswith("organization")
    ]
    assert organization_tagged == ["Acme", "Corp"]


@pytest.mark.asyncio
async def test_stored_bio_tags_ignored(seeded_entity_types, client):
    """verification.md row 7.

    The stored `bio_tags` column is itself derived from the same drifting offset walk
    (in `spans.py`), so export must not consult it. The stored value here deliberately
    disagrees with the span's character offsets; the offsets must win.
    """
    tid = seeded_entity_types["tid"]
    schema = seeded_entity_types["schema"]

    content = "John Doe\nworks at Acme Corp"
    await seed_document(
        schema,
        tid,
        content,
        [
            {
                "entity_type": "organization",
                "char_start": 18,
                "char_end": 27,
                # Deliberately wrong: claims a three-token entity of a different type.
                "bio_tags": ["B-location", "I-location", "I-location"],
            }
        ],
    )

    resp = await client.get("/api/v1/annotation-export", headers=auth_header(make_token(tid)))

    assert resp.status_code == 200
    record = only_record(resp)
    assert tag_of(record, "Acme") == "B-organization"
    assert tag_of(record, "Corp") == "I-organization"
    assert not any(tag.endswith("location") for tag in record["tags"])
