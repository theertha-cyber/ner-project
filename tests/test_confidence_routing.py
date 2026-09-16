"""Confidence-based routing of extraction output.

Covers verification.md rows 4-7.

Three levels, deliberately. The threshold rule itself is a pure function and is tested as one —
boundary behaviour is the whole of Decision 1 and deserves assertions that cannot be confounded
by a database. The persistence is tested against a real tenant schema, because "recorded as
auto-accepted" is a claim about a row. And the no-second-inference-pass property (Decision 2,
Hallucination Risk 2) is tested by running the actual worker with a call-counting stub, because
that is the only level at which "it did not call model serving twice" is a fact rather than an
assertion about code someone read.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine as sync_create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.services.entity_normalizer import NormalizedEntity
from src.extraction_service.services.prediction_routing import (
    purge_expired_predictions,
    record_routed_predictions,
)
from src.shared.config import settings
from src.shared.confidence_routing import (
    DISPOSITION_ACCEPTED,
    DISPOSITION_QUEUED,
    is_base_model_version,
    is_below_business_threshold,
    route_prediction,
)
from tests.confidence_review_support import (
    ORG_END,
    ORG_START,
    add_document,
    add_run,
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


@pytest.fixture
def sync_engine():
    engine = sync_create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine, sync_engine):
    yield
    # Disposed before the drop: a sync connection still holding a row lock on a tenant table
    # deadlocks against `DROP SCHEMA ... CASCADE`, which needs an AccessExclusiveLock.
    sync_engine.dispose()
    await drop_test_schemas(engine)


def _entity(confidence, entity_type="organization", value="Acme Corp",
            char_start=ORG_START, char_end=ORG_END):
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=value.lower(),
        confidence=confidence,
        char_start=char_start,
        char_end=char_end,
    )


async def _routed_rows(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT entity_type, value, confidence, char_start, char_end, model_version, "
                f"       served_by_base_model, below_business_threshold, disposition "
                f"FROM {schema}.routed_predictions ORDER BY confidence DESC"
            )
        )
        return result.fetchall()


class TestThresholdRule:
    """The rule itself, before any storage. Boundary behaviour is what Decision 1 is about."""

    def test_at_or_above_the_threshold_is_accepted(self):
        assert route_prediction(0.95, 0.90) == DISPOSITION_ACCEPTED
        # Exactly at the threshold is not review work — the spec says "at or above".
        assert route_prediction(0.90, 0.90) == DISPOSITION_ACCEPTED

    def test_below_the_threshold_is_queued(self):
        assert route_prediction(0.62, 0.90) == DISPOSITION_QUEUED
        assert route_prediction(0.8999, 0.90) == DISPOSITION_QUEUED

    def test_the_business_question_is_asked_separately(self):
        """A prediction can be queued for review and still be business-facing, or accepted
        without review and still be hidden. The two thresholds do not imply each other."""
        # Queued for review (below 0.90) but above the business threshold (0.50): visible.
        assert route_prediction(0.62, 0.90) == DISPOSITION_QUEUED
        assert is_below_business_threshold(0.62, 0.50) is False
        # Below both: queued and hidden.
        assert is_below_business_threshold(0.30, 0.50) is True

    def test_the_base_model_is_recognised(self):
        assert is_base_model_version("0") is True
        assert is_base_model_version(None) is True
        assert is_base_model_version("3") is False


class TestHighConfidencePredictionIsAutoAccepted:
    """Row 4."""

    async def test_a_prediction_above_the_review_threshold_is_recorded_accepted(
        self, engine, sync_engine
    ):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            counts = record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.95)], "3", 0.90, 0.50
            )

        assert counts["accepted"] == 1
        assert counts["queued"] == 0

        rows = await _routed_rows(engine, tenant["schema"])
        assert len(rows) == 1
        assert rows[0][8] == DISPOSITION_ACCEPTED
        assert rows[0][2] == 0.95

    async def test_an_accepted_prediction_does_not_appear_in_the_review_queue(
        self, engine, sync_engine
    ):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.95)], "3", 0.90, 0.50
            )

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT COUNT(*) FROM {tenant['schema']}.routed_predictions "
                    "WHERE disposition = 'queued'"
                )
            )
            assert result.scalar() == 0


class TestLowConfidencePredictionEntersQueue:
    """Row 5."""

    async def test_a_prediction_below_the_review_threshold_is_queued_with_its_confidence(
        self, engine, sync_engine
    ):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            counts = record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.62)], "3", 0.90, 0.50
            )

        assert counts["queued"] == 1
        rows = await _routed_rows(engine, tenant["schema"])
        assert rows[0][8] == DISPOSITION_QUEUED
        # The spec names this number specifically: the recorded confidence is the prediction's,
        # not the threshold's and not a rounded stand-in.
        assert rows[0][2] == 0.62

    async def test_a_prediction_with_no_offsets_is_skipped_rather_than_queued(
        self, engine, sync_engine
    ):
        """Offsets are what a span is. A prediction without them could never become one, so
        queueing it would ask a reviewer to judge something that cannot be acted on."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)
        entity = _entity(0.62)
        entity.char_start = None
        entity.char_end = None

        with sync_engine.begin() as conn:
            counts = record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [entity], "3", 0.90, 0.50
            )

        assert counts["skipped"] == 1
        assert await _routed_rows(engine, tenant["schema"]) == []


class TestReviewThresholdIsIndependent:
    """Row 6."""

    async def test_moving_the_review_threshold_does_not_move_the_extraction_threshold(
        self, engine, sync_engine
    ):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)
        entities = [_entity(0.95), _entity(0.85, char_start=0, char_end=8, value="Jane Roe")]

        # Review threshold 0.90: one accepted, one queued.
        with sync_engine.begin() as conn:
            first = record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, entities, "3", 0.90, 0.50
            )
        assert (first["accepted"], first["queued"]) == (1, 1)

        # Review threshold 0.80: both accepted. The business threshold never moved.
        with sync_engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {tenant['schema']}.routed_predictions"))
            second = record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, entities, "3", 0.80, 0.50
            )
        assert (second["accepted"], second["queued"]) == (2, 0)

        # What the business sees is a function of the business threshold alone, and it did not
        # change across the two runs.
        assert first["below_business_threshold"] == second["below_business_threshold"] == 0
        assert settings.confidence_threshold == 0.50, (
            "the business-facing threshold is not touched by routing"
        )

    async def test_the_two_thresholds_are_separate_settings(self):
        """The structural half of Hallucination Risk 1: two distinct configuration values
        exist, and routing reads the new one."""
        assert hasattr(settings, "confidence_threshold")
        assert hasattr(settings, "review_confidence_threshold")
        assert settings.confidence_threshold != settings.review_confidence_threshold, (
            "shipping them equal would hide a conflation this test exists to catch"
        )


class TestRoutedPredictionsRecordModelVersion:
    """Row 7."""

    async def test_every_routed_prediction_records_the_serving_model_version(
        self, engine, sync_engine
    ):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            record_routed_predictions(
                conn,
                tenant["schema"],
                run_id,
                doc_id,
                [_entity(0.95), _entity(0.62, char_start=0, char_end=8, value="Jane Roe")],
                "3",
                0.90,
                0.50,
            )

        rows = await _routed_rows(engine, tenant["schema"])
        assert len(rows) == 2
        assert {row[5] for row in rows} == {"3"}, "the spec's version 3, on every routed row"
        assert {row[6] for row in rows} == {False}, "version 3 is not the base model"

    async def test_base_model_predictions_are_recorded_distinctly(self, engine, sync_engine):
        """ADR-008: version 0 is the base-model fallback. Recorded, but flagged, so accumulation
        can exclude it without re-deriving the fact later."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="0")

        with sync_engine.begin() as conn:
            record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.62)], "0", 0.90, 0.50
            )

        rows = await _routed_rows(engine, tenant["schema"])
        assert rows[0][5] == "0"
        assert rows[0][6] is True


class TestRetentionBound:
    """Decision 11's age half. The resolution half is covered in `test_review_queue.py`."""

    async def test_predictions_older_than_the_bound_are_purged(self, engine, sync_engine):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.62)], "3", 0.90, 0.50
            )
            conn.execute(
                text(
                    f"UPDATE {tenant['schema']}.routed_predictions "
                    "SET created_at = NOW() - INTERVAL '120 days'"
                )
            )
            purged = purge_expired_predictions(conn, tenant["schema"], 90)

        assert purged == 1
        assert await _routed_rows(engine, tenant["schema"]) == []

    async def test_predictions_inside_the_bound_survive(self, engine, sync_engine):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)

        with sync_engine.begin() as conn:
            record_routed_predictions(
                conn, tenant["schema"], run_id, doc_id, [_entity(0.62)], "3", 0.90, 0.50
            )
            purged = purge_expired_predictions(conn, tenant["schema"], 90)

        assert purged == 0
        assert len(await _routed_rows(engine, tenant["schema"])) == 1


class TestNoSecondInferencePass:
    """Decision 2 and Hallucination Risk 2, at the only level where it is a fact.

    Runs the real worker over one document with a call-counting stub in place of model serving.
    Routing consumes what that single call produced; a second inference path — however
    reasonable it looked in isolation — would show up here as a second POST.
    """

    async def test_routing_adds_no_model_serving_call(self, engine, sync_engine, monkeypatch):
        from src.extraction_service import worker as worker_module

        tenant = await make_tenant(engine)
        tid, schema = tenant["tid"], tenant["schema"]
        doc_id = await add_document(engine, tenant)
        run_id = str(uuid.uuid4())

        # The worker's own tables, beyond what the support module creates.
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    f"ALTER TABLE {schema}.extraction_runs "
                    "ADD COLUMN IF NOT EXISTS total_documents INTEGER NOT NULL DEFAULT 0, "
                    "ADD COLUMN IF NOT EXISTS processed_count INTEGER NOT NULL DEFAULT 0, "
                    "ADD COLUMN IF NOT EXISTS skipped_count INTEGER NOT NULL DEFAULT 0, "
                    "ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0, "
                    "ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only', "
                    "ADD COLUMN IF NOT EXISTS postprocess_model TEXT, "
                    "ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT, "
                    "ADD COLUMN IF NOT EXISTS postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {schema}.model_versions "
                    "(tenant_id VARCHAR, version INTEGER, version_number INTEGER, status VARCHAR)"
                )
            )
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {schema}.document_entities ("
                    " id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,"
                    " entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL,"
                    " confidence DOUBLE PRECISION NOT NULL, page_number INTEGER,"
                    " char_start INTEGER, char_end INTEGER,"
                    " created_at TIMESTAMPTZ NOT NULL DEFAULT now(), value_kind TEXT,"
                    " value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,"
                    " value_unit TEXT, value_date DATE, value_date_high DATE,"
                    " source_entity_value TEXT, source_entity_type TEXT,"
                    " postprocess_status TEXT NOT NULL DEFAULT 'not_applied',"
                    " postprocess_model TEXT, postprocess_prompt_version TEXT,"
                    " postprocess_at TIMESTAMPTZ,"
                    " extraction_schema_version INTEGER NOT NULL DEFAULT 1,"
                    " occurrence_count INTEGER NOT NULL DEFAULT 1)"
                )
            )
            conn.execute(
                text(
                    f"INSERT INTO {schema}.extraction_runs "
                    "(id, tenant_id, document_id, status, started_at, total_documents) "
                    "VALUES (:id, :tid, :doc, 'running', NOW(), 1)"
                ),
                {"id": run_id, "tid": tid, "doc": doc_id},
            )

        calls = []

        class _Response:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "predictions": [
                        {"token": "Acme", "label": "B-organization", "confidence": 0.95},
                        {"token": "Corp", "label": "I-organization", "confidence": 0.62},
                    ],
                    "model_version": "3",
                }

        def counting_post(url, headers=None, json=None, timeout=None):
            calls.append(url)
            return _Response()

        monkeypatch.setattr(worker_module.requests, "post", counting_post)
        monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda _tid: "3")
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)

        worker_module.run_batch_extraction.run(tid, run_id, [doc_id])

        assert len(calls) == 1, (
            f"routing must consume the run's own predictions, not re-infer; saw {calls}"
        )

        rows = await _routed_rows(engine, schema)
        assert rows, "the run routed what it extracted"
        # `aggregate_confidence` takes the minimum across the span's tokens, so the two-token
        # `Acme Corp` span carries 0.62 and is queued — not 0.95 and accepted (Decision 8).
        assert rows[0][2] == 0.62
        assert rows[0][8] == DISPOSITION_QUEUED
        assert rows[0][5] == "3"
