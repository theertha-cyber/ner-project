"""Requesting a retrain, and the approval it must not skip.

Covers verification.md rows 10-13.

Row 10's second clause carries the weight. "A job is created in `pending_approval`" is easy to
satisfy and easy to satisfy *while also* enqueuing the Celery task — the request would work, the
status would read `pending_approval` for as long as it took the worker to pick it up, and System
Admin approval would have been skipped entirely (verification.md Risk 4). So `send_task` is
spied on for the whole request and asserted never called, and row 11 then shows the same spy
firing exactly once at approval. The pair is what proves where the enqueue lives, not either
half alone.

Row 13 is checked structurally as well: the request body model has no hyperparameter fields at
all, so there is nothing for a caller to send and nothing for the endpoint to read (ADR-009).
"""

import os
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app as annotation_app
from src.shared.config import settings
from src.training_service.main import app as training_app
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    auth_header,
    drop_test_schemas,
    ensure_audit_events,
    make_tenant,
    review_spans,
)

pytestmark = pytest.mark.verification

APPROVE_BODY = {
    "learning_rate": 2e-5,
    "num_epochs": 3,
    "batch_size": 8,
    "max_seq_length": 512,
}


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


class _SendTaskSpy:
    """Stands in for `celery_app.send_task` and remembers every call.

    A spy rather than a mock that raises, because row 11 needs the enqueue to *work* at approval
    while row 10 needs it never to happen at request time. One object records both.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, name, args=None, **kwargs):
        self.calls.append((name, args))

        class _Result:
            id = "spied-task-id"

        return _Result()


@pytest.fixture
def send_task_spy(monkeypatch):
    from src.training_service.api.v1 import training_jobs

    spy = _SendTaskSpy()
    monkeypatch.setattr(training_jobs.celery_app, "send_task", spy)
    return spy


def _annotation_client():
    return AsyncClient(transport=ASGITransport(app=annotation_app), base_url="http://test")


def _training_client():
    return AsyncClient(transport=ASGITransport(app=training_app), base_url="http://test")


async def _tenant_with_accumulation(engine, count=6):
    await ensure_audit_events(engine)
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id, model_version="3")
    await add_model_version(engine, tenant, 3, status="promoted")
    if count:
        await review_spans(_annotation_client, engine, tenant, doc_id, run_id, count)
    return tenant


async def _request_retrain(tenant):
    async with _training_client() as client:
        return await client.post(
            "/api/v1/training-retrain-requests",
            headers=auth_header(tenant["tid"]),
        )


async def _job_row(engine, tenant, job_id) -> dict:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(f"SELECT * FROM {tenant['schema']}.training_jobs WHERE id = :id"),
            {"id": job_id},
        )
        return dict(result.fetchone()._mapping)


class TestRequestCreatesPendingApprovalJob:
    """Row 10."""

    async def test_request_creates_pending_approval_job(self, engine, send_task_spy):
        """A request creates a job awaiting approval and enqueues nothing."""
        tenant = await _tenant_with_accumulation(engine)

        resp = await _request_retrain(tenant)

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "pending_approval"
        assert send_task_spy.calls == []

        row = await _job_row(engine, tenant, body["id"])
        assert row["status"] == "pending_approval"
        # Not merely un-enqueued: no task id was recorded either, so nothing can pick it up.
        assert row["celery_task_id"] is None

    async def test_requester_must_be_tenant_admin(self, engine, send_task_spy):
        """tasks.md 1.2: Tenant Admin requests, System Admin approves.

        A System Admin who could both request and approve would make the approval a formality
        rather than a gate, so the request path keeps the role the existing submission path
        already enforces.
        """
        tenant = await _tenant_with_accumulation(engine)

        async with _training_client() as client:
            resp = await client.post(
                "/api/v1/training-retrain-requests",
                headers=auth_header(tenant["tid"], role="system_admin"),
            )

        assert resp.status_code == 403
        assert send_task_spy.calls == []

    async def test_zero_accumulation_is_allowed_with_a_warning(self, engine, send_task_spy):
        """tasks.md 1.3: allowed, flagged, not blocked.

        Retraining over unchanged data with different hyperparameters is legitimate, and this
        surface reports evidence rather than deciding on it.
        """
        tenant = await _tenant_with_accumulation(engine, count=0)

        resp = await _request_retrain(tenant)

        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending_approval"
        assert resp.headers.get("X-Retrain-Warning") == "no-accumulated-spans"

    async def test_no_warning_when_evidence_has_accumulated(self, engine, send_task_spy):
        tenant = await _tenant_with_accumulation(engine, count=4)

        resp = await _request_retrain(tenant)

        assert resp.status_code == 201, resp.text
        assert "X-Retrain-Warning" not in resp.headers


class TestRequestedRetrainFollowsApprovalFlow:
    """Row 11."""

    async def test_requested_retrain_follows_approval_flow(self, engine, send_task_spy):
        """Approval is what moves the job to `queued` and what enqueues the task.

        Same spy as row 10. Empty there, one call here — which is what locates the enqueue at
        approval rather than at request.
        """
        tenant = await _tenant_with_accumulation(engine)
        job_id = (await _request_retrain(tenant)).json()["id"]
        assert send_task_spy.calls == []

        async with _training_client() as client:
            resp = await client.post(
                f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tenant['tid']}",
                json=APPROVE_BODY,
                headers=auth_header(tenant["tid"], role="system_admin"),
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "queued"
        assert len(send_task_spy.calls) == 1
        name, args = send_task_spy.calls[0]
        assert name == "fine_tune_model"
        assert args[1] == job_id

    async def test_approval_handles_it_like_any_other_job(self, engine, send_task_spy):
        """Task 4.4: the approve path does not branch on how the job originated.

        Two jobs, one from the ordinary submission endpoint and one from the retrain request,
        approved the same way and compared field by field. Any branch on origin would show up as
        a difference here.
        """
        tenant = await _tenant_with_accumulation(engine)

        async with _training_client() as client:
            ordinary_id = (
                await client.post(
                    "/api/v1/training-jobs", json={}, headers=auth_header(tenant["tid"])
                )
            ).json()["id"]
        requested_id = (await _request_retrain(tenant)).json()["id"]

        async with _training_client() as client:
            for job_id in (ordinary_id, requested_id):
                resp = await client.post(
                    f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tenant['tid']}",
                    json=APPROVE_BODY,
                    headers=auth_header(tenant["tid"], role="system_admin"),
                )
                assert resp.status_code == 200, resp.text

        ordinary = await _job_row(engine, tenant, ordinary_id)
        requested = await _job_row(engine, tenant, requested_id)
        compared = ("status", "hyperparams", "error_message")
        assert {k: ordinary[k] for k in compared} == {k: requested[k] for k in compared}
        assert requested["status"] == "queued"


class TestRequestedRetrainCanBeRejected:
    """Row 12."""

    async def test_requested_retrain_can_be_rejected(self, engine, send_task_spy):
        """Rejection works, records the reason, and enqueues nothing."""
        tenant = await _tenant_with_accumulation(engine)
        job_id = (await _request_retrain(tenant)).json()["id"]

        async with _training_client() as client:
            resp = await client.post(
                f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tenant['tid']}",
                json={"reason": "wait for the next quarter's review backlog"},
                headers=auth_header(tenant["tid"], role="system_admin"),
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "rejected"

        row = await _job_row(engine, tenant, job_id)
        assert row["status"] == "rejected"
        assert row["error_message"] == "wait for the next quarter's review backlog"
        assert send_task_spy.calls == []


class TestRequestCarriesNoHyperparameters:
    """Row 13."""

    async def test_request_carries_no_hyperparameters(self, engine, send_task_spy):
        """The pre-approval job carries none, and they arrive at approval (ADR-009)."""
        tenant = await _tenant_with_accumulation(engine)
        job_id = (await _request_retrain(tenant)).json()["id"]

        before = await _job_row(engine, tenant, job_id)
        assert before["hyperparams"] is None

        async with _training_client() as client:
            await client.post(
                f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tenant['tid']}",
                json=APPROVE_BODY,
                headers=auth_header(tenant["tid"], role="system_admin"),
            )

        after = await _job_row(engine, tenant, job_id)
        assert after["hyperparams"]["learning_rate"] == APPROVE_BODY["learning_rate"]
        assert after["hyperparams"]["num_epochs"] == APPROVE_BODY["num_epochs"]

    async def test_supplied_hyperparameters_are_refused(self, engine, send_task_spy):
        """A caller that tries to set them is rejected rather than silently ignored.

        `TrainingJobCreate` forbids extra fields, so this is structural: there is no field to
        set, and sending one is a 422 rather than a value quietly dropped.
        """
        tenant = await _tenant_with_accumulation(engine)

        async with _training_client() as client:
            resp = await client.post(
                "/api/v1/training-retrain-requests",
                json={"learning_rate": 0.1},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 422
        assert send_task_spy.calls == []

    def test_request_module_reads_no_hyperparameters(self):
        """Nothing in the request path names a hyperparameter."""
        source = Path("src/training_service/api/v1/retrain_request.py").read_text(
            encoding="utf-8"
        )
        code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        code = re.sub(r"#.*", "", code)

        for name in ("learning_rate", "num_epochs", "batch_size", "max_seq_length"):
            assert name not in code, name
