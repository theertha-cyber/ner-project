"""Review outcomes becoming confirmed spans.

Covers verification.md rows 13-17.

Two of these rows are about what must *not* happen, and they are the reason this file exists
separately from `test_review_queue.py`. Row 16 asserts that the existing value-level correction
flow is not a source of spans, and row 17 asserts that a span created here is distinguishable
from one created by manual annotation or by change 4's batch acceptance. Both are properties of
the span store rather than of the endpoint, so they are checked against the tables directly.
"""

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
    DOCUMENT_TEXT,
    ORG_END,
    ORG_START,
    add_document,
    add_prediction,
    add_run,
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


async def _queued(engine, **kwargs):
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id)
    pred_id = await add_prediction(engine, tenant, run_id, doc_id, **kwargs)
    return tenant, doc_id, pred_id


async def _resolve(tenant, pred_id, body):
    async with await _client() as client:
        return await client.post(
            f"/api/v1/review-queue/{pred_id}/resolve",
            json=body,
            headers=auth_header(tenant["tid"]),
        )


async def _spans(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT id, entity_type, char_start, char_end, text_content, confidence, bio_tags "
                f"FROM {schema}.spans ORDER BY char_start, char_end"
            )
        )
        return result.fetchall()


class TestConfirmedOutcomeCreatesSpan:
    """Row 13."""

    async def test_a_confirmed_outcome_creates_a_span_at_the_predicted_offsets(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        resp = await _resolve(tenant, pred_id, {"outcome": "confirmed"})
        assert resp.status_code == 200, resp.text

        rows = await _spans(engine, tenant["schema"])
        assert len(rows) == 1
        _, entity_type, char_start, char_end, text_content, confidence, bio_tags = rows[0]
        assert (entity_type, char_start, char_end) == ("organization", ORG_START, ORG_END)
        # Sliced from the document, never taken from the caller.
        assert text_content == DOCUMENT_TEXT[ORG_START:ORG_END] == "Acme Corp"
        # The reviewer's certainty, not the model's 0.62 — a person has now judged this span.
        assert confidence == 1.0
        assert bio_tags == ["B-organization", "I-organization"]

    async def test_the_span_is_linked_to_the_outcome_that_produced_it(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)
        await _resolve(tenant, pred_id, {"outcome": "confirmed"})

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT p.span_id, p.model_version, p.served_by_base_model, o.outcome "
                    f"FROM {tenant['schema']}.span_review_provenance p "
                    f"JOIN {tenant['schema']}.review_outcomes o ON o.id = p.outcome_id"
                )
            )
            rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0][1] == "3"
        assert rows[0][2] is False
        assert rows[0][3] == "confirmed"


class TestCorrectedOutcomeUsesCorrectedOffsets:
    """Row 14."""

    async def test_a_corrected_outcome_creates_a_span_at_the_corrected_offsets(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        resp = await _resolve(
            tenant, pred_id, {"outcome": "corrected", "char_start": ORG_START, "char_end": 50}
        )
        assert resp.status_code == 200, resp.text

        rows = await _spans(engine, tenant["schema"])
        assert len(rows) == 1, "exactly one span, at the corrected offsets"
        _, _, char_start, char_end, text_content, _, _ = rows[0]
        assert (char_start, char_end) == (ORG_START, 50)
        assert text_content == DOCUMENT_TEXT[ORG_START:50]

    async def test_no_span_exists_at_the_original_offsets(self, engine):
        """The spec is explicit that the original span must not also exist — a correction that
        left the prediction's span behind would put both readings into the training set."""
        tenant, doc_id, pred_id = await _queued(engine)

        await _resolve(
            tenant, pred_id, {"outcome": "corrected", "char_start": ORG_START, "char_end": 50}
        )

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {tenant['schema']}.spans "
                    "WHERE char_start = :cs AND char_end = :ce"
                ),
                {"cs": ORG_START, "ce": ORG_END},
            )
            assert result.scalar() == 0

    async def test_a_corrected_entity_type_is_carried_onto_the_span(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        await _resolve(tenant, pred_id, {"outcome": "corrected", "entity_type": "institution"})

        rows = await _spans(engine, tenant["schema"])
        assert rows[0][1] == "institution"
        assert rows[0][6] == ["B-institution", "I-institution"]


class TestRejectedOutcomeCreatesNoSpan:
    """Row 15."""

    async def test_a_rejected_outcome_creates_no_span(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        resp = await _resolve(tenant, pred_id, {"outcome": "rejected"})

        assert resp.status_code == 200, resp.text
        assert await _spans(engine, tenant["schema"]) == []


class TestValueCorrectionDoesNotProduceSpan:
    """Row 16.

    The task list requires this test to supply a `corrected_value` that does **not** match the
    document text at the prediction's offsets. `Acme Corporation` is 16 characters against the
    9 the document actually holds at 36-45, so if anything ever derived a span by searching the
    document for the corrected value, or by pairing that value with the original offsets, the
    result would be a span whose text is not what the document says — the "answer is not in the
    text" failure change 1 exists to prevent.
    """

    CORRECTED_VALUE = "Acme Corporation"

    async def test_a_corrected_value_produces_no_span(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)
        schema = tenant["schema"]

        assert self.CORRECTED_VALUE not in DOCUMENT_TEXT, (
            "the corrected value must not be findable in the document, or this test would pass "
            "for the wrong reason"
        )
        assert DOCUMENT_TEXT[ORG_START:ORG_END] != self.CORRECTED_VALUE

        # The existing value-level correction flow: an extracted entity whose corrected value is
        # a normalisation of what the text says, not a statement about where the entity is.
        async with engine.begin() as conn:
            run_id = await add_run_inline(conn, schema, tenant["tid"], doc_id)
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.extracted_entities "
                    "(id, run_id, document_id, entity_id, value, confidence, review_status, "
                    " corrected_value, corrected_by) "
                    "VALUES (:id, :run_id, :doc_id, 'organization', 'Acme Corp', 0.62, "
                    "        'corrected', :corrected, 'test-reviewer')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "doc_id": doc_id,
                    "corrected": self.CORRECTED_VALUE,
                },
            )

        # Now process review outcomes for the tenant. Nothing about the value correction above
        # should reach the span store.
        await _resolve(tenant, pred_id, {"outcome": "confirmed"})

        rows = await _spans(engine, schema)
        assert len(rows) == 1, "only the reviewed prediction produced a span"
        assert rows[0][4] == "Acme Corp", "the span says what the document says"
        assert rows[0][4] != self.CORRECTED_VALUE

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.spans WHERE text_content = :value"
                ),
                {"value": self.CORRECTED_VALUE},
            )
            assert result.scalar() == 0, "no span was derived from the corrected value"

    async def test_the_value_correction_flow_is_left_intact(self, engine):
        """Task 8.3's backend half: the existing flow keeps working for its own purpose. This
        change does not replace it, it declines to read it."""
        tenant, doc_id, pred_id = await _queued(engine)
        schema = tenant["schema"]

        async with engine.begin() as conn:
            run_id = await add_run_inline(conn, schema, tenant["tid"], doc_id)
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.extracted_entities "
                    "(id, run_id, document_id, entity_id, value, confidence, review_status, "
                    " corrected_value, corrected_by) "
                    "VALUES (:id, :run_id, :doc_id, 'organization', 'Acme Corp', 0.62, "
                    "        'corrected', :corrected, 'test-reviewer')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "doc_id": doc_id,
                    "corrected": self.CORRECTED_VALUE,
                },
            )

        await _resolve(tenant, pred_id, {"outcome": "confirmed"})

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT corrected_value, review_status FROM {schema}.extracted_entities"
                )
            )
            rows = result.fetchall()
        assert rows == [(self.CORRECTED_VALUE, "corrected")], (
            "review resolution neither reads nor disturbs the value-correction record"
        )


async def add_run_inline(conn, schema, tenant_id, doc_id, model_version="3"):
    run_id = str(uuid.uuid4())
    await conn.execute(
        text(
            f"INSERT INTO {schema}.extraction_runs "
            "(id, tenant_id, document_id, model_version, status) "
            "VALUES (:id, :tid, :doc_id, :mv, 'completed')"
        ),
        {"id": run_id, "tid": tenant_id, "doc_id": doc_id, "mv": model_version},
    )
    return run_id


class TestSpanOriginIsRecorded:
    """Row 17: three origins, all distinguishable."""

    async def test_production_review_spans_are_distinguishable_from_the_other_two(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)
        schema = tenant["schema"]

        # 1. Manual annotation: an ordinary span with no provenance row in either table. This is
        #    what every span predating changes 4 and 5 is.
        manual_id = str(uuid.uuid4())
        # 2. Batch acceptance: change 4's `span_batch_provenance`.
        batch_span_id = str(uuid.uuid4())
        batch_id = str(uuid.uuid4())
        acceptance_id = str(uuid.uuid4())
        async with engine.begin() as conn:
            for span_id, start, end, value in (
                (manual_id, 0, 8, "Jane Roe"),
                (batch_span_id, 48, 55, "Chennai"),
            ):
                await conn.execute(
                    text(
                        f"INSERT INTO {schema}.spans "
                        "(id, document_id, entity_type, char_start, char_end, text_content, "
                        " confidence) "
                        "VALUES (:id, :doc, 'person_name', :cs, :ce, :txt, 1.0)"
                    ),
                    {"id": span_id, "doc": doc_id, "cs": start, "ce": end, "txt": value},
                )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.prelabel_batches (id, status) "
                    "VALUES (:id, 'completed')"
                ),
                {"id": batch_id},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.batch_acceptance_records "
                    "(id, batch_id, sampled_document_ids, sample_size, sampled, "
                    " agreement_threshold, decision) "
                    "VALUES (:id, :batch, '[]'::jsonb, 1, false, 1.0, 'accepted')"
                ),
                {"id": acceptance_id, "batch": batch_id},
            )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.span_batch_provenance "
                    "(span_id, batch_id, acceptance_id) VALUES (:s, :b, :a)"
                ),
                {"s": batch_span_id, "b": batch_id, "a": acceptance_id},
            )

        # 3. Production review.
        await _resolve(tenant, pred_id, {"outcome": "confirmed"})

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT s.id, "
                    f"       (r.span_id IS NOT NULL) AS from_review, "
                    f"       (b.span_id IS NOT NULL) AS from_batch "
                    f"FROM {schema}.spans s "
                    f"LEFT JOIN {schema}.span_review_provenance r ON r.span_id = s.id "
                    f"LEFT JOIN {schema}.span_batch_provenance b ON b.span_id = s.id"
                )
            )
            origins = {row[0]: (row[1], row[2]) for row in result.fetchall()}

        assert len(origins) == 3
        assert origins[manual_id] == (False, False), "manual annotation: neither provenance row"
        assert origins[batch_span_id] == (False, True), "batch acceptance"
        review_ids = [sid for sid, flags in origins.items() if flags == (True, False)]
        assert len(review_ids) == 1, "production review is distinguishable from both others"
        assert review_ids[0] not in (manual_id, batch_span_id)
