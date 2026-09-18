"""Source-scoped exports for `manual-training-data-source-scoping`.

Manual, Automated, and Import are independent workflows: a training job scoped to one must
train only on that workflow's data, never a blend. This exercises the `source` query param on
`/api/v1/annotation-export`: 'manual' spans have no `span_batch_provenance` row, 'automated'
spans do (promoted from an accepted batch — same distinction `test_review_outcomes.py` already
relies on for the batch-vs-individual-review split), and 'import' pulls exclusively from
`imported_annotations`, a wholly separate table that spans never touch.

Built on `confidence_review_support`'s tenant/document fixtures rather than duplicating them;
`imported_annotations` is the one table those fixtures don't create (nothing there currently
exercises import), so it is added locally, scoped to each test's own throwaway schema.
"""

import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.shared.config import settings
from tests.confidence_review_support import (
    add_document,
    auth_header,
    drop_test_schemas,
    make_tenant,
)


@pytest.fixture
async def engine():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    await drop_test_schemas(engine)


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _add_span(
    engine, tenant, doc_id, text_content, entity_type, char_start, char_end, *, promoted: bool
) -> str:
    """One confirmed span, optionally with a `span_batch_provenance` row.

    A row means the span was promoted from an accepted automated batch; its absence is every
    individually-reviewed span (manual annotation, review queue) — the same rule
    `/api/v1/annotation-export`'s `source` filter reads.
    """
    schema = tenant["schema"]
    span_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content) "
                "VALUES (:sid, :doc_id, :etype, :start, :end, :content)"
            ),
            {
                "sid": span_id,
                "doc_id": doc_id,
                "etype": entity_type,
                "start": char_start,
                "end": char_end,
                "content": text_content[char_start:char_end],
            },
        )
        if promoted:
            batch_id = str(uuid.uuid4())
            acceptance_id = str(uuid.uuid4())
            await conn.execute(
                text(f"INSERT INTO {schema}.prelabel_batches (id, status) VALUES (:id, 'completed')"),
                {"id": batch_id},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.batch_acceptance_records "
                    "(id, batch_id, sampled_document_ids, sample_size, sampled, agreement_threshold, decision) "
                    "VALUES (:id, :batch_id, '[]'::jsonb, 0, false, 0.9, 'accepted')"
                ),
                {"id": acceptance_id, "batch_id": batch_id},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.span_batch_provenance (span_id, batch_id, acceptance_id) "
                    "VALUES (:span_id, :batch_id, :acceptance_id)"
                ),
                {"span_id": span_id, "batch_id": batch_id, "acceptance_id": acceptance_id},
            )
    return span_id


async def _add_imported_row(engine, tenant, tokens: list[str], tags: list[str]) -> None:
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {schema}.imported_annotations (
                    id VARCHAR PRIMARY KEY,
                    tokens TEXT[] NOT NULL,
                    tags TEXT[] NOT NULL,
                    source_file VARCHAR NOT NULL,
                    row_index INTEGER NOT NULL,
                    pending_mapping BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(
            text(
                f"INSERT INTO {schema}.imported_annotations "
                "(id, source_file, row_index, tokens, tags, pending_mapping) "
                "VALUES (:id, 'scope-test.jsonl', 0, :tokens, :tags, FALSE)"
            ),
            {"id": str(uuid.uuid4()), "tokens": tokens, "tags": tags},
        )


def _records(resp) -> list[dict]:
    return [json.loads(line) for line in resp.text.strip().split("\n") if line]


CONTENT = "Acme Corp hired Globex Inc"


async def _seed_two_orgs(engine, tenant):
    """One manually-confirmed span ('Acme Corp') and one automated-promoted span
    ('Globex Inc') on the same document — the fixture every source-scope test in this
    file starts from."""
    doc_id = await add_document(engine, tenant, document_text=CONTENT, purpose="training")
    await _add_span(engine, tenant, doc_id, CONTENT, "organization", 0, 9, promoted=False)
    await _add_span(engine, tenant, doc_id, CONTENT, "organization", 16, 26, promoted=True)
    return doc_id


@pytest.mark.asyncio
async def test_manual_source_excludes_automated_promoted_spans(engine):
    tenant = await make_tenant(engine)
    await _seed_two_orgs(engine, tenant)

    async with await _client() as client:
        resp = await client.get(
            "/api/v1/annotation-export",
            params={"source": "manual"},
            headers=auth_header(tenant["tid"]),
        )

    assert resp.status_code == 200
    record = _records(resp)[0]
    acme_idx = record["tokens"].index("Acme")
    globex_idx = record["tokens"].index("Globex")
    assert record["tags"][acme_idx] == "B-organization"
    assert record["tags"][globex_idx] == "O"


@pytest.mark.asyncio
async def test_automated_source_includes_only_promoted_spans(engine):
    tenant = await make_tenant(engine)
    await _seed_two_orgs(engine, tenant)

    async with await _client() as client:
        resp = await client.get(
            "/api/v1/annotation-export",
            params={"source": "automated"},
            headers=auth_header(tenant["tid"]),
        )

    assert resp.status_code == 200
    record = _records(resp)[0]
    acme_idx = record["tokens"].index("Acme")
    globex_idx = record["tokens"].index("Globex")
    assert record["tags"][acme_idx] == "O"
    assert record["tags"][globex_idx] == "B-organization"


@pytest.mark.asyncio
async def test_import_source_returns_only_imported_rows_and_skips_spans(engine):
    tenant = await make_tenant(engine)
    await _seed_two_orgs(engine, tenant)
    await _add_imported_row(engine, tenant, ["Imported", "Person"], ["B-person_name", "I-person_name"])

    async with await _client() as client:
        resp = await client.get(
            "/api/v1/annotation-export",
            params={"source": "import"},
            headers=auth_header(tenant["tid"]),
        )

    assert resp.status_code == 200
    records = _records(resp)
    assert len(records) == 1
    assert records[0]["tokens"] == ["Imported", "Person"]
    assert records[0]["source"] == "import"


@pytest.mark.asyncio
async def test_omitted_source_combines_everything(engine):
    tenant = await make_tenant(engine)
    await _seed_two_orgs(engine, tenant)
    await _add_imported_row(engine, tenant, ["Imported", "Person"], ["B-person_name", "I-person_name"])

    async with await _client() as client:
        resp = await client.get("/api/v1/annotation-export", headers=auth_header(tenant["tid"]))

    assert resp.status_code == 200
    records = _records(resp)
    # The span-derived document record plus the imported row.
    assert len(records) == 2
    all_tokens = [tok for r in records for tok in r["tokens"]]
    assert "Acme" in all_tokens
    assert "Globex" in all_tokens
    assert "Imported" in all_tokens


@pytest.mark.asyncio
async def test_invalid_source_is_rejected(engine):
    tenant = await make_tenant(engine)

    async with await _client() as client:
        resp = await client.get(
            "/api/v1/annotation-export",
            params={"source": "bogus"},
            headers=auth_header(tenant["tid"]),
        )

    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_SOURCE"
