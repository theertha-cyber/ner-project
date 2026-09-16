"""Below-threshold predictions are retained for routing, invisibly to business consumers.

Covers verification.md rows 2-3. Row 1, the pre-existing filtering regression, lives in
`tests/test_extract_confidence_threshold.py` and is unchanged by this change — it guards the
ad-hoc `/extract` endpoint, which still filters exactly as it did.

Row 3 is the narrowed guarantee from design.md Decision 15. The original scenario assumed the
document-backed path filtered `document_entities` on `settings.confidence_threshold`; it does
not, and never has, so "exactly 3 of 5 are returned" was never true of that path. What this
change actually guarantees — and what is tested here — is that retention happens somewhere no
business-facing surface reads, so turning routing on changes nothing a consumer receives.

That is tested by running the same document twice, once with routing suppressed and once with it
enabled, and comparing what landed in `document_entities`. Comparing two real runs is stronger
than asserting a count: a filter accidentally introduced anywhere in the write path would show up
as a difference between the runs, whatever its threshold happened to be.
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

from src.shared.config import settings
from tests.confidence_review_support import (
    add_document,
    drop_test_schemas,
    make_tenant,
)

# Five predictions over one sentence: three comfortably above the 0.50 business threshold and
# two below it. The two below are the ones this change stops discarding.
PREDICTIONS = [
    {"token": "Jane", "label": "B-person_name", "confidence": 0.97},
    {"token": "Roe", "label": "I-person_name", "confidence": 0.93},
    {"token": "Acme", "label": "B-organization", "confidence": 0.88},
    {"token": "Corp", "label": "I-organization", "confidence": 0.81},
    {"token": "Chennai", "label": "B-location", "confidence": 0.30},
]
DOC_TEXT = "Jane Roe works at Acme Corp in Chennai"


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


class _Response:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"predictions": PREDICTIONS, "model_version": "3"}


async def _prepare(engine, sync_engine):
    """A tenant with the worker's full table set and one processed document."""
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant, document_text=DOC_TEXT)
    schema = tenant["schema"]
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
    return tenant, doc_id


def _run_extraction(monkeypatch, sync_engine, tenant, doc_id, run_id):
    from src.extraction_service import worker as worker_module

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {tenant['schema']}.extraction_runs "
                "(id, tenant_id, document_id, status, started_at, total_documents) "
                "VALUES (:id, :tid, :doc, 'running', NOW(), 1)"
            ),
            {"id": run_id, "tid": tenant["tid"], "doc": doc_id},
        )

    monkeypatch.setattr(
        worker_module.requests, "post", lambda url, **kwargs: _Response()
    )
    monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
    monkeypatch.setattr(worker_module, "_get_active_model_version", lambda _tid: "3")
    worker_module.run_batch_extraction.run(tenant["tid"], run_id, [doc_id])


async def _document_entities(engine, schema):
    """What a business consumer sees. `document_entities` is what `chat_api`'s entity resolver,
    its SQL generator, and `document_service` read."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT entity_type, entity_value, confidence, char_start, char_end "
                f"FROM {schema}.document_entities ORDER BY char_start, entity_type"
            )
        )
        return result.fetchall()


async def _routed(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT entity_type, value, confidence, char_start, char_end, model_version, "
                f"       below_business_threshold, disposition "
                f"FROM {schema}.routed_predictions ORDER BY char_start"
            )
        )
        return result.fetchall()


class TestBelowThresholdPredictionsRetained:
    """Row 2."""

    async def test_below_threshold_predictions_retained(
        self, engine, sync_engine, monkeypatch
    ):
        """The 0.30 prediction survives the run, with everything routing and review need."""
        tenant, doc_id = await _prepare(engine, sync_engine)
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)

        _run_extraction(monkeypatch, sync_engine, tenant, doc_id, str(uuid.uuid4()))

        rows = await _routed(engine, tenant["schema"])
        below = [r for r in rows if r[6] is True]
        assert below, "the below-business-threshold prediction was retained, not discarded"

        entity_type, value, confidence, char_start, char_end, model_version = below[0][:6]
        # Everything the spec names: type, value, confidence, offsets, model version.
        assert entity_type == "location"
        assert value == "Chennai"
        assert confidence == pytest.approx(0.30)
        assert DOC_TEXT[char_start:char_end] == "Chennai"
        assert model_version == "3"

    async def test_a_retained_prediction_is_available_to_routing(
        self, engine, sync_engine, monkeypatch
    ):
        """Retention is only useful if the prediction is routable. At a review threshold of
        0.90 the 0.30 prediction is queued — which is the point: the cases the model is least
        sure about are the ones most worth learning from."""
        tenant, doc_id = await _prepare(engine, sync_engine)
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)

        _run_extraction(monkeypatch, sync_engine, tenant, doc_id, str(uuid.uuid4()))

        rows = await _routed(engine, tenant["schema"])
        below = [r for r in rows if r[6] is True]
        assert below[0][7] == "queued"

    async def test_the_two_thresholds_are_recorded_independently(
        self, engine, sync_engine, monkeypatch
    ):
        """`below_business_threshold` and `disposition` answer different questions, and a
        prediction can be one without the other. `Acme Corp` here is above the business
        threshold (visible) but below the review threshold (queued)."""
        tenant, doc_id = await _prepare(engine, sync_engine)
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)

        _run_extraction(monkeypatch, sync_engine, tenant, doc_id, str(uuid.uuid4()))

        rows = await _routed(engine, tenant["schema"])
        org = [r for r in rows if r[0] == "organization"]
        assert org, rows
        assert org[0][6] is False, "above the business threshold: business-facing"
        assert org[0][7] == "queued", "below the review threshold: review work"


class TestRetainedPredictionsHiddenFromConsumers:
    """Row 3, as narrowed by design.md Decision 15."""

    async def test_retained_predictions_hidden_from_consumers(
        self, engine, sync_engine, monkeypatch
    ):
        """The same document, run twice: once with routing suppressed, once with it enabled.
        What a business consumer sees must be identical.

        Routing is suppressed by patching `record_routed_predictions` to a no-op rather than by
        a configuration flag, because no such flag exists — and inventing one to make a test
        pass would be inventing the very coupling this test is checking is absent.
        """
        from src.extraction_service import worker as worker_module

        tenant, doc_id = await _prepare(engine, sync_engine)
        schema = tenant["schema"]
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)

        # Run 1: routing suppressed.
        monkeypatch.setattr(
            worker_module,
            "record_routed_predictions",
            lambda *a, **k: {"accepted": 0, "queued": 0, "below_business_threshold": 0, "skipped": 0},
        )
        _run_extraction(monkeypatch, sync_engine, tenant, doc_id, str(uuid.uuid4()))
        without_routing = await _document_entities(engine, schema)
        assert await _routed(engine, schema) == [], "routing really was suppressed"

        # Run 2: routing enabled. `extracted_entities` is cleared first because it is the
        # idempotency ledger `get_already_extracted` joins against — leaving run 1's rows would
        # make the worker skip this document entirely, and the comparison below would compare
        # run 1's output against itself and pass without testing anything.
        with sync_engine.begin() as conn:
            conn.execute(
                text(f"DELETE FROM {schema}.extracted_entities WHERE document_id = :doc"),
                {"doc": doc_id},
            )

        monkeypatch.undo()
        monkeypatch.setattr(settings, "confidence_threshold", 0.50)
        monkeypatch.setattr(settings, "review_confidence_threshold", 0.90)
        _run_extraction(monkeypatch, sync_engine, tenant, doc_id, str(uuid.uuid4()))
        with_routing = await _document_entities(engine, schema)

        assert without_routing == with_routing, (
            "routing changed what a business consumer sees; it must not"
        )
        assert await _routed(engine, schema), "run 2 did route"

    async def test_no_business_surface_reads_the_routing_store(self):
        """The structural half: `routed_predictions` is named by the extraction worker and its
        routing module, and by `annotation_service`'s review surface — and by nothing that
        serves a business consumer.

        Grepped rather than asserted about behaviour because the guarantee is about absence, and
        absence is not observable from any one response. A new reader appearing in `chat_api`,
        `analytics_service`, or the entity projection is exactly the regression this catches.
        """
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1] / "src"
        readers = sorted(
            str(path.relative_to(root)).replace("\\", "/")
            for path in root.rglob("*.py")
            if "routed_predictions" in path.read_text(encoding="utf-8", errors="ignore")
        )

        allowed = {
            # Writes the store.
            "extraction_service/services/prediction_routing.py",
            "extraction_service/worker.py",
            # Reads it to present review work, and deletes a prediction once its outcome is
            # recorded (design.md Decision 11). Both are the review surface, not a business one.
            "annotation_service/api/v1/review_queue.py",
            "annotation_service/services/review_resolution.py",
            # Draws the audit sample over the auto-accepted part of the store.
            "annotation_service/services/audit_sampling.py",
            # The LLM review route reads the queue to work it.
            "annotation_service/worker.py",
        }
        unexpected = set(readers) - allowed
        assert not unexpected, (
            f"the routing store gained a reader outside routing and review: {sorted(unexpected)}"
        )

        business_surfaces = ("chat_api/", "analytics_service/", "document_service/")
        assert not [r for r in readers if r.startswith(business_surfaces)], (
            "a business-facing service reads the routing store"
        )
