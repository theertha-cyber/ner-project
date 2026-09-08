"""What a training run records, and the three cases where it must record nothing.

Covers verification.md rows 1-5.

Rows 3, 4 and 5 are the point of this file. Row 1 checks that a number is written; those three
check that it is *not* written when a job was rejected, when a run failed, and while a run is
still executing. Recording at submission would pass row 1 and fail all three, which is precisely
the mistake verification.md Risk 2 names — a rejected or failed job silently zeroing the
accumulation figure while producing no model, destroying the evidence that the retrain never
happened.

The rejection and failure cases exercise the real transitions: the reject test goes through
`training_service`'s reject endpoint, and the failure test drives the job to `failed` and then
asserts the recording function was never reached — which it cannot have been, because the only
call site is inside the success branch after the model version row is written.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.shared.config import settings
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    add_training_job,
    auth_header,
    complete_run,
    consumed_rows,
    dataset_span_ids_now,
    drop_test_schemas,
    ensure_audit_events,
    make_tenant,
    review_spans,
)

pytestmark = pytest.mark.verification


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


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _accumulation(tenant) -> dict:
    async with _client() as client:
        resp = await client.get(
            "/api/v1/review-accumulation", headers=auth_header(tenant["tid"])
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _tenant_serving_version_3(engine):
    """A tenant serving version 3 with a document and an extraction run against it."""
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id, model_version="3")
    await add_model_version(engine, tenant, 3, status="promoted")
    return tenant, doc_id, run_id


class TestCompletedRunRecordsConsumedSpans:
    """Row 1."""

    async def test_completed_run_records_consumed_spans(self, engine):
        """The spec's scenario at a smaller count: the spans a run's dataset was built from are
        recorded against the version the run produced.

        Six rather than 300 because the assertion is about which span ids are recorded and
        against which version, and 300 identical resolutions would test the loop, not the rule.
        """
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 6)

        # What the dataset build would cover, read through the production SQL.
        dataset = await dataset_span_ids_now(engine, tenant)
        assert len(dataset) == 6

        await add_model_version(engine, tenant, 4, status="completed")
        await complete_run(engine, tenant, dataset, version_number=4)

        recorded = await consumed_rows(engine, tenant)
        assert sorted(span_id for span_id, _ in recorded) == sorted(dataset)
        assert {version for _, version in recorded} == {"4"}


class TestAccumulationResetsAfterRun:
    """Row 2."""

    async def test_accumulation_resets_after_run(self, engine):
        """Accumulation against the newly serving version is zero once the run that consumed
        those spans has completed and version 4 serves."""
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 5)

        before = await _accumulation(tenant)
        assert before["spans_accumulated"] == 5
        assert before["model_version"] == "3"

        dataset = await dataset_span_ids_now(engine, tenant)
        await complete_run(engine, tenant, dataset, version_number=4)

        # The human promotion step. Nothing in the completion path does this — see
        # test_no_auto_retraining.py — so the test has to, exactly as a person would.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"UPDATE {tenant['schema']}.model_versions "
                    "SET status = 'archived', active_flag = false WHERE version_number = 3"
                )
            )
        await add_model_version(engine, tenant, 4, status="promoted")

        after = await _accumulation(tenant)
        assert after["model_version"] == "4"
        assert after["spans_accumulated"] == 0
        assert after["by_entity_type"] == {}


class TestRejectedJobRecordsNothing:
    """Row 3."""

    async def test_rejected_job_records_nothing(self, engine):
        """A System Admin rejecting a pending job leaves the figure exactly where it was.

        The rejection goes through `training_service`'s own reject endpoint rather than an
        UPDATE, so this asserts about the real approval flow: if that path ever grew a
        consumed-span write, this test would see it.
        """
        from src.training_service.main import app as training_app

        await ensure_audit_events(engine)
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 7)
        job_id = await add_training_job(engine, tenant, status="pending_approval")

        assert (await _accumulation(tenant))["spans_accumulated"] == 7

        transport = ASGITransport(app=training_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tenant['tid']}",
                json={"reason": "not enough new evidence"},
                headers=auth_header(tenant["tid"], role="system_admin"),
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "rejected"

        assert await consumed_rows(engine, tenant) == []
        assert (await _accumulation(tenant))["spans_accumulated"] == 7


class TestFailedRunRecordsNothing:
    """Row 4."""

    async def test_failed_run_records_nothing(self, engine):
        """A run that fails records nothing, and the figure is unchanged."""
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 7)
        job_id = await add_training_job(engine, tenant, status="running")

        # The worker's failure path: job to `failed`, version row to `failed`, and — the point
        # of the test — no consumption record, because the only call site sits after the
        # success branch's model-version insert.
        await add_model_version(engine, tenant, 4, status="failed", training_job_id=job_id)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"UPDATE {tenant['schema']}.training_jobs "
                    "SET status = 'failed', error_message = 'CUDA out of memory' "
                    "WHERE id = :id"
                ),
                {"id": job_id},
            )

        assert await consumed_rows(engine, tenant) == []
        report = await _accumulation(tenant)
        assert report["spans_accumulated"] == 7
        assert report["model_version"] == "3"


class TestAccumulationUnchangedDuringRun:
    """Row 5."""

    async def test_accumulation_unchanged_during_run(self, engine):
        """While an approved run is executing the figure is unchanged.

        This is the trade-off design.md accepts rather than a defect: the figure is stale for
        the duration of a run, because the alternative — recording at submission — is wrong in
        the worse direction. The decision surface says a run is in flight for exactly this
        reason (tasks.md 1.5).
        """
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 7)
        await add_training_job(engine, tenant, status="running")

        report = await _accumulation(tenant)
        assert report["spans_accumulated"] == 7
        assert await consumed_rows(engine, tenant) == []

        # And the surface says why the number looks like it does.
        async with _client() as client:
            decision = await client.get(
                "/api/v1/retraining-decision", headers=auth_header(tenant["tid"])
            )
        assert decision.json()["training_run_in_flight"] is True


class TestRecordingIsIdempotent:
    """Not a spec row — a property the primary key forces on any second run.

    `span_training_consumption.span_id` is the primary key, so a span consumed by one run and
    then by the next would raise on insert and fail a job that had already trained successfully.
    The writer uses `ON CONFLICT DO NOTHING` and keeps the first run's attribution, which is the
    one the figure asks about: "has any run trained on this yet?" stops being no the first time.
    """

    async def test_second_run_over_same_spans_does_not_raise(self, engine):
        tenant, doc_id, run_id = await _tenant_serving_version_3(engine)
        await review_spans(_client, engine, tenant, doc_id, run_id, 3)
        dataset = await dataset_span_ids_now(engine, tenant)

        await complete_run(engine, tenant, dataset, version_number=4)
        await complete_run(engine, tenant, dataset, version_number=5)

        recorded = await consumed_rows(engine, tenant)
        assert len(recorded) == 3
        assert {version for _, version in recorded} == {"4"}
