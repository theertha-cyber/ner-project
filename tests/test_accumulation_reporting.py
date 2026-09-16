"""Accumulation reporting, and the training run it must never start.

Covers verification.md rows 18-20.

Row 20 is the one that matters most. Every other test here checks a number; that one checks an
absence — that nothing in this change creates, enqueues, schedules, or notifies to start a
training job as the figure grows. It is the single most likely unwanted addition
(verification.md Risk 5, task 6.4), and absence is not observable from any one response, so it
is checked twice: behaviourally, by growing the figure with a Celery `send_task` spy installed,
and structurally, by parsing this change's own modules for a training enqueue.
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


async def _promote_model(engine, tenant, version):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {tenant['schema']}.model_versions "
                "(id, tenant_id, version, status, active_flag) "
                "VALUES (:id, :tid, :v, 'promoted', true)"
            ),
            {"id": str(uuid.uuid4()), "tid": tenant["tid"], "v": version},
        )


async def _review_spans(engine, tenant, doc_id, run_id, count, *, model_version="3",
                        base_model=False):
    """`count` production-review spans, created the way review creates them.

    Created by resolving real queued predictions through the endpoint rather than by inserting
    spans and provenance rows directly. Inserting them by hand would let this file agree with
    itself about a shape the endpoint might not produce.
    """
    for index in range(count):
        pred_id = await add_prediction(
            engine,
            tenant,
            run_id,
            doc_id,
            char_start=ORG_START,
            char_end=ORG_END,
            model_version=model_version,
            served_by_base_model=base_model,
        )
        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )
        assert resp.status_code == 200, resp.text


async def _accumulation(tenant):
    async with await _client() as client:
        resp = await client.get(
            "/api/v1/review-accumulation", headers=auth_header(tenant["tid"])
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAccumulationAgainstCurrentVersion:
    """Row 18."""

    async def test_accumulation_against_current_version(self, engine):
        """The spec's scenario at a smaller count: spans created by production review of
        version-3 predictions are reported against version 3."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await _promote_model(engine, tenant, 3)
        await _review_spans(engine, tenant, doc_id, run_id, 4, model_version="3")

        report = await _accumulation(tenant)

        assert report["model_version"] == "3"
        assert report["spans_accumulated"] == 4

    async def test_spans_from_an_older_version_do_not_count(self, engine):
        """Accumulation is a delta since the *current* version was trained. A span reviewed
        when version 2 was serving is evidence about version 2, and was already available when
        version 3 was trained."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        old_run = await add_run(engine, tenant, doc_id, model_version="2")
        new_run = await add_run(engine, tenant, doc_id, model_version="3")
        await _promote_model(engine, tenant, 3)

        await _review_spans(engine, tenant, doc_id, old_run, 5, model_version="2")
        await _review_spans(engine, tenant, doc_id, new_run, 2, model_version="3")

        report = await _accumulation(tenant)

        assert report["model_version"] == "3"
        assert report["spans_accumulated"] == 2, "only the version-3 delta"

    async def test_spans_a_training_run_consumed_are_no_longer_accumulation(self, engine):
        """`span_training_consumption` is written by the training worker when a run consumes
        spans; nothing in this change writes it. The exclusion is defined here anyway, because
        "not yet trained on" has to mean something before the first row exists as well as
        after — with the table empty it is a no-op, which is the correct behaviour today."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await _promote_model(engine, tenant, 3)
        await _review_spans(engine, tenant, doc_id, run_id, 3, model_version="3")

        assert (await _accumulation(tenant))["spans_accumulated"] == 3

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {tenant['schema']}.span_training_consumption "
                    "(span_id, model_version, training_job_id) "
                    f"SELECT id, '4', 'job-1' FROM {tenant['schema']}.spans LIMIT 2"
                )
            )

        assert (await _accumulation(tenant))["spans_accumulated"] == 1

    async def test_the_figure_is_not_presented_as_readiness(self, engine):
        """ADR-010: readiness is per entity type at its own threshold, and is a different
        quantity. The response says so in words, and carries no readiness field to be mistaken
        for one."""
        tenant = await make_tenant(engine)
        await _promote_model(engine, tenant, 3)

        report = await _accumulation(tenant)

        assert report["kind"] == "accumulation_since_training"
        assert "not a dataset readiness measure" in report["note"]
        forbidden = {"ready", "readiness", "threshold", "entities_per_type", "is_ready"}
        assert not forbidden & set(report), (
            f"the accumulation response carries readiness-shaped fields: {forbidden & set(report)}"
        )


class TestBaseModelSpansExcluded:
    """Row 19."""

    async def test_base_model_spans_excluded(self, engine):
        """A tenant with no trained model is served by the base model (ADR-008). Those spans
        are real and are recorded, but they say nothing about whether retraining this tenant's
        model would help, so they are not accumulation against a tenant version."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="0")
        # No promoted model version: the base model is serving.
        await _review_spans(
            engine, tenant, doc_id, run_id, 3, model_version="0", base_model=True
        )

        report = await _accumulation(tenant)

        assert report["spans_accumulated"] == 0
        assert report["spans_from_base_model"] == 3, "recorded distinctly, not discarded"
        assert report["model_version"] is None, (
            "there is no tenant-trained version for the figure to be a delta against"
        )

    async def test_base_model_spans_do_not_inflate_a_tenant_figure(self, engine):
        """The mixed case: a tenant on version 3 that also has spans from an earlier
        base-model period. The two must not be added together."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        base_run = await add_run(engine, tenant, doc_id, model_version="0")
        v3_run = await add_run(engine, tenant, doc_id, model_version="3")
        await _promote_model(engine, tenant, 3)

        await _review_spans(
            engine, tenant, doc_id, base_run, 5, model_version="0", base_model=True
        )
        await _review_spans(engine, tenant, doc_id, v3_run, 2, model_version="3")

        report = await _accumulation(tenant)

        assert report["spans_accumulated"] == 2
        assert report["spans_from_base_model"] == 5


class TestAccumulationTriggersNoTraining:
    """Row 20, and task 6.4."""

    async def test_accumulation_triggers_no_training(self, engine, monkeypatch):
        """The figure grows; nothing is created, queued, or submitted.

        A spy is installed on every Celery dispatch method rather than on one, because "no
        training job was started" has to hold whichever way a job might have been sent.
        """
        from src.annotation_service.celery_app import celery_app

        dispatched = []
        for method in ("send_task", "apply_async"):
            if hasattr(celery_app, method):
                monkeypatch.setattr(
                    celery_app,
                    method,
                    lambda *a, _m=method, **k: dispatched.append((_m, a, k)),
                )

        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await _promote_model(engine, tenant, 3)

        # Grow the figure across a range, reading it at each step: if anything watched a
        # threshold, crossing it would show up here.
        await _review_spans(engine, tenant, doc_id, run_id, 2, model_version="3")
        assert (await _accumulation(tenant))["spans_accumulated"] == 2
        await _review_spans(engine, tenant, doc_id, run_id, 10, model_version="3")
        assert (await _accumulation(tenant))["spans_accumulated"] == 12

        assert dispatched == [], f"something was dispatched: {dispatched}"

        # And no training job row was written anywhere the tenant schema could hold one.
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = 'training_jobs'"
                ),
                {"schema": tenant["schema"]},
            )
            if result.scalar():
                rows = await conn.execute(
                    text(f"SELECT COUNT(*) FROM {tenant['schema']}.training_jobs")
                )
                assert rows.scalar() == 0

    async def test_no_module_in_this_change_enqueues_training(self):
        """Task 6.4 and 9.5, as a check rather than a promise.

        Reads this change's own modules for a training enqueue or scheduling call. Scoped to
        string literals and attribute names rather than raw text, so a comment explaining that
        this must not happen does not itself trip the check.
        """
        import ast
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[1] / "src"
        modules = [
            root / "shared" / "confidence_routing.py",
            root / "extraction_service" / "services" / "prediction_routing.py",
            root / "annotation_service" / "services" / "review_resolution.py",
            root / "annotation_service" / "services" / "accumulation.py",
            root / "annotation_service" / "services" / "audit_sampling.py",
            root / "annotation_service" / "services" / "llm_review.py",
            root / "annotation_service" / "api" / "v1" / "review_queue.py",
        ]

        for path in modules:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            forbidden = {"send_task", "apply_async", "delay", "add_periodic_task"}
            assert not calls & forbidden, (
                f"{path.name} dispatches background work: {sorted(calls & forbidden)}"
            )

            literals = " ".join(
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            )
            assert "training.jobs" not in literals, f"{path.name} names the GPU training queue"
            assert "INSERT INTO" not in literals.upper() or "training_jobs" not in literals, (
                f"{path.name} writes a training job row"
            )
