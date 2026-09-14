"""The acceptance gate: now `initial`-batch-only, plus `large` batches' automatic promotion.

Covers verification.md rows 13-17 for the `initial` kind (reviewed by an Annotator Admin, no
Tenant Admin approval, never training-eligible), and the new automatic-promotion behaviour for
the `large` kind, which is never manually reviewed at all
(annotation-workflow-review-simplification).

Sampling is enabled explicitly in the tests that need it rather than left at its shipped default
(off, meaning full review). An `initial` batch is capped at 5 documents, so a "strict subset"
sample here is necessarily small (3 of 5) — meaningfully different from "everything", but not
the astronomically-unlikely-to-collide-with-the-first-N assertion the old 100-document/20-sample
version could make. That specific assertion is dropped rather than kept dishonestly.
"""

import os
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.annotation_service.services.llm_client import LLMUnavailable, StubLLMClient
from src.annotation_service.worker import run_prelabel_batch_sync
from src.shared.config import settings
from tests.seed_bootstrap_support import (
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


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def fake_send_task(monkeypatch):
    from src.annotation_service.api.v1 import seed_bootstrap as module

    calls = []

    def _send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args, "queue": kwargs.get("queue")})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


@pytest.fixture
def sampling(monkeypatch):
    """Turn sampling on for one test, with the sample size and threshold it needs."""

    def _configure(sample_size=20, threshold=1.0, enabled=True):
        monkeypatch.setattr(settings, "seed_bootstrap_sampling_enabled", enabled)
        monkeypatch.setattr(settings, "seed_bootstrap_sample_size", sample_size)
        monkeypatch.setattr(settings, "seed_bootstrap_agreement_threshold", threshold)

    return _configure


def _entities(*pairs):
    return {"entities": [{"entity_type": t, "quote": q} for t, q in pairs]}


DEFAULT_RESPONSE = _entities(
    ("person_name", "John Doe"),
    ("institute", "Vellore Institute of Technology"),
)


class FailingOnNthClient:
    """Raises on the nth call, answers normally otherwise — models one bad document in an
    otherwise-successful batch."""

    def __init__(self, response, fail_on: int):
        self.response = response
        self.fail_on = fail_on
        self.call_count = 0

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:
        self.call_count += 1
        if self.call_count == self.fail_on:
            raise LLMUnavailable("provider error: simulated failure")
        return self.response


class AlwaysFailingClient:
    """Every call raises — models a large batch where every document fails."""

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:
        raise LLMUnavailable("provider error: simulated total outage")


async def _completed_batch(client, engine, tenant, count, response=DEFAULT_RESPONSE, batch_kind="initial"):
    doc_ids = [await add_document(engine, tenant) for _ in range(count)]
    resp = await client.post(
        "/api/v1/prelabel-batches",
        json={"document_ids": doc_ids, "batch_kind": batch_kind},
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 202, resp.text
    batch_id = resp.json()["batch_id"]
    run_prelabel_batch_sync(tenant["tid"], batch_id, llm_client=StubLLMClient(response))
    return doc_ids, batch_id


async def _start_review(client, tenant, batch_id, role="annotator"):
    resp = await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance",
        headers=auth_header(tenant["tid"], role),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sample_suggestions(client, tenant, batch_id, role="annotator"):
    resp = await client.get(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance",
        headers=auth_header(tenant["tid"], role),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["suggestions"]


async def _submit_review(client, tenant, batch_id, dispositions, role="annotator"):
    return await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance/review",
        json={"dispositions": dispositions},
        headers=auth_header(tenant["tid"], role),
    )


async def _accept(client, tenant, batch_id, role="annotator"):
    return await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance/accept",
        headers=auth_header(tenant["tid"], role),
    )


async def _span_count(engine, tenant) -> int:
    async with engine.connect() as conn:
        return (
            await conn.execute(text(f"SELECT COUNT(*) FROM {tenant['schema']}.spans"))
        ).scalar()


async def _approve_initial_batch(client, engine, tenant):
    """Clear the sequencing gate: an Annotator-Admin-approved `initial` batch, over 1 document.

    Every `large`-batch test needs this first now — a large batch cannot be created otherwise.
    """
    _, initial_id = await _completed_batch(client, engine, tenant, 1)
    await _start_review(client, tenant, initial_id)
    suggestions = await _sample_suggestions(client, tenant, initial_id)
    await _submit_review(
        client,
        tenant,
        initial_id,
        [{"suggestion_id": s["id"], "disposition": "agree"} for s in suggestions],
    )
    accept = await _accept(client, tenant, initial_id)
    assert accept.status_code == 200, accept.text
    return initial_id


class TestSampleSelection:
    """verification.md row 13 — now exercised on an `initial` batch (max 5 documents)."""

    async def test_sample_is_random_and_recorded(self, client, engine, sampling):
        sampling(sample_size=3, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 5)

        record = await _start_review(client, tenant, batch_id)

        sampled = record["sampled_document_ids"]
        assert len(sampled) == 3
        assert record["sample_size"] == 3
        assert record["sampled"] is True
        assert set(sampled).issubset(set(doc_ids))

        # Persisted at selection time, not recomputed at read time — the property that makes the
        # rate measured against this sample auditable afterwards.
        async with engine.connect() as conn:
            stored = (
                await conn.execute(
                    text(
                        f"SELECT sampled_document_ids, sample_size "
                        f"FROM {tenant['schema']}.batch_acceptance_records WHERE batch_id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
        assert list(stored[0]) == sampled
        assert stored[1] == 3

        # A second read returns the same draw rather than a new one.
        again = await client.get(
            f"/api/v1/prelabel-batches/{batch_id}/acceptance",
            headers=auth_header(tenant["tid"], "annotator"),
        )
        assert again.json()["sampled_document_ids"] == sampled


class TestAcceptanceGate:
    """verification.md rows 14-17, for the `initial` kind."""

    async def test_batch_above_threshold_bulk_accepts(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 5)
        await _start_review(client, tenant, batch_id)

        suggestions = await _sample_suggestions(client, tenant, batch_id)
        assert len(suggestions) == 10
        review = await _submit_review(
            client,
            tenant,
            batch_id,
            [{"suggestion_id": s["id"], "disposition": "agree"} for s in suggestions],
        )
        assert review.status_code == 200, review.text
        assert review.json()["agreement_rate"] == 1.0
        assert review.json()["sample_review_complete"] is True

        resp = await _accept(client, tenant, batch_id)

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"] == "accepted"
        assert body["promoted_spans"] == 10
        assert await _span_count(engine, tenant) == 10

        async with engine.connect() as conn:
            record = (
                await conn.execute(
                    text(
                        f"SELECT sample_size, agreement_rate, reviewer, decided_at, decision "
                        f"FROM {tenant['schema']}.batch_acceptance_records WHERE batch_id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
        assert record[0] == 5
        assert record[1] == 1.0
        assert record[2] == "test-user"
        assert record[3] is not None
        assert record[4] == "accepted"

    async def test_batch_below_threshold_rejected(self, client, engine, sampling):
        sampling(enabled=False, threshold=0.9)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 5)
        await _start_review(client, tenant, batch_id)

        suggestions = await _sample_suggestions(client, tenant, batch_id)
        # Six of ten agreed: 0.6, below the 0.9 threshold. The disagreements are a mix of kinds,
        # because the gate must treat a boundary correction as disagreement under the exact-match
        # definition this change adopted (design.md, task 1.4).
        dispositions = []
        for index, suggestion in enumerate(suggestions):
            if index < 6:
                disposition = "agree"
            elif index < 8:
                disposition = "boundary"
            else:
                disposition = "reject"
            dispositions.append(
                {"suggestion_id": suggestion["id"], "disposition": disposition}
            )
        review = await _submit_review(client, tenant, batch_id, dispositions)
        assert review.json()["agreement_rate"] == 0.6
        assert review.json()["meets_threshold"] is False

        resp = await _accept(client, tenant, batch_id)

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "AGREEMENT_BELOW_THRESHOLD"
        # The point of the row, not the status code: a sub-threshold batch promotes nothing.
        # There is no partial-acceptance path, so the reviewed documents are not promoted
        # either (design.md Decision 3, verification.md Risk 4).
        assert await _span_count(engine, tenant) == 0

        async with engine.connect() as conn:
            record = (
                await conn.execute(
                    text(
                        f"SELECT decision, agreement_rate, agreed_count, reviewed_count "
                        f"FROM {tenant['schema']}.batch_acceptance_records WHERE batch_id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
            remaining = (
                await conn.execute(
                    text(f"SELECT COUNT(*) FROM {tenant['schema']}.suggested_spans")
                )
            ).scalar()
        assert record[0] == "rejected"
        assert record[1] == 0.6
        assert (record[2], record[3]) == (6, 10)
        # Retained, not discarded (task 1.5): the suggestions stay available for ordinary
        # per-document review.
        assert remaining == 10

        # And the gate stays closed. Re-drawing a sample until one passes is the failure
        # retention would otherwise enable.
        retry = await client.post(
            f"/api/v1/prelabel-batches/{batch_id}/acceptance",
            headers=auth_header(tenant["tid"], "annotator"),
        )
        assert retry.status_code == 422
        assert retry.json()["detail"]["code"] == "BATCH_ALREADY_DECIDED"

    async def test_repeated_dispositions_do_not_inflate_the_rate(self, client, engine, sampling):
        """Sending one suggestion twice must not count it twice.

        Not a scenario in the spec, but the gate is a ratio the client supplies the numerator
        for: if repeating an `agree` raised the rate, a batch could be talked past the threshold
        without any further review, which would make every recorded rate worthless as evidence.
        """
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 5)
        await _start_review(client, tenant, batch_id)

        suggestions = await _sample_suggestions(client, tenant, batch_id)
        agreed_once = [{"suggestion_id": suggestions[0]["id"], "disposition": "agree"}]
        review = await _submit_review(client, tenant, batch_id, agreed_once * 10)

        assert review.status_code == 200, review.text
        assert review.json()["reviewed_count"] == 1
        assert review.json()["sample_review_complete"] is False

        resp = await _accept(client, tenant, batch_id)
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "SAMPLE_REVIEW_INCOMPLETE"
        assert await _span_count(engine, tenant) == 0

    async def test_acceptance_requires_completed_sample_review(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 5)
        await _start_review(client, tenant, batch_id)

        # Nothing reviewed at all.
        resp = await _accept(client, tenant, batch_id)
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "SAMPLE_REVIEW_INCOMPLETE"

        # Reviewed, but not all of it — and every one of those a perfect agreement, so this
        # cannot be passing on the rate.
        suggestions = await _sample_suggestions(client, tenant, batch_id)
        await _submit_review(
            client,
            tenant,
            batch_id,
            [{"suggestion_id": s["id"], "disposition": "agree"} for s in suggestions[:4]],
        )

        resp = await _accept(client, tenant, batch_id)
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "SAMPLE_REVIEW_INCOMPLETE"
        assert await _span_count(engine, tenant) == 0

    async def test_bulk_promoted_spans_record_route(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 3)

        # One span promoted the ordinary way first, so the test compares the two routes rather
        # than merely observing that the batch wrote something.
        individual_doc = doc_ids[0]
        async with engine.connect() as conn:
            suggestion_id = (
                await conn.execute(
                    text(
                        f"SELECT id FROM {tenant['schema']}.suggested_spans "
                        "WHERE document_id = :doc_id LIMIT 1"
                    ),
                    {"doc_id": individual_doc},
                )
            ).scalar()
        promoted = await client.post(
            f"/api/v1/documents/{individual_doc}/spans/promote/{suggestion_id}",
            headers=auth_header(tenant["tid"]),
        )
        assert promoted.status_code == 201, promoted.text
        individual_span_id = promoted.json()["id"]

        await _start_review(client, tenant, batch_id)
        suggestions = await _sample_suggestions(client, tenant, batch_id)
        await _submit_review(
            client,
            tenant,
            batch_id,
            [{"suggestion_id": s["id"], "disposition": "agree"} for s in suggestions],
        )
        accept = await _accept(client, tenant, batch_id)
        assert accept.status_code == 200, accept.text
        acceptance_id = accept.json()["acceptance_id"]

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"SELECT s.id, p.batch_id, p.acceptance_id "
                        f"FROM {tenant['schema']}.spans s "
                        f"LEFT JOIN {tenant['schema']}.span_batch_provenance p "
                        "  ON p.span_id = s.id"
                    )
                )
            ).fetchall()

        by_id = {row[0]: (row[1], row[2]) for row in rows}
        assert len(by_id) == 6

        # Every bulk-accepted span names the batch and the acceptance record whose measured rate
        # admitted it.
        for span_id, (batch, acceptance) in by_id.items():
            if span_id == individual_span_id:
                continue
            assert batch == batch_id
            assert acceptance == acceptance_id

        # And the individually promoted one is distinguishable: no provenance row.
        assert by_id[individual_span_id] == (None, None)


class TestInitialBatchReviewerRole:
    """The initial batch is reviewed by an Annotator Admin — no Tenant Admin approval."""

    async def test_tenant_admin_cannot_review_initial_batch(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 2)

        start = await client.post(
            f"/api/v1/prelabel-batches/{batch_id}/acceptance",
            headers=auth_header(tenant["tid"], "tenant_admin"),
        )
        assert start.status_code == 403, start.text

        # The gate refuses the tenant admin uniformly — accepting is refused too, not only
        # starting the review.
        accept = await _accept(client, tenant, batch_id, role="tenant_admin")
        assert accept.status_code == 403, accept.text

    async def test_annotator_accepting_initial_batch_does_not_notify_or_mark_training_eligible(
        self, client, engine, sampling
    ):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 2)
        await _start_review(client, tenant, batch_id)
        suggestions = await _sample_suggestions(client, tenant, batch_id)
        await _submit_review(
            client,
            tenant,
            batch_id,
            [{"suggestion_id": s["id"], "disposition": "agree"} for s in suggestions],
        )
        accept = await _accept(client, tenant, batch_id)
        assert accept.status_code == 200, accept.text
        assert accept.json()["training_eligible"] is False

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT annotator_review_status, training_eligible_at "
                        f"FROM {tenant['schema']}.prelabel_batches WHERE id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
            notifications = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM public.notifications WHERE resource_id = :id"),
                    {"id": batch_id},
                )
            ).scalar()
        # The approval is recorded — the frontend gates large-batch upload on this — but it is
        # explicitly not the training-eligibility gate and nobody is notified over it.
        assert row[0] == "approved"
        assert row[1] is None
        assert notifications == 0


class TestLargeBatchAutoPromotion:
    """A `large` batch is never reviewed by anyone — its output becomes training data as soon
    as pre-labeling finishes."""

    async def test_large_batch_auto_promotes_on_completion(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        await _approve_initial_batch(client, engine, tenant)

        doc_ids, batch_id = await _completed_batch(
            client, engine, tenant, 5, batch_kind="large"
        )

        # No human ever reviews it — the batch is already training-eligible.
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT annotator_review_status, training_eligible_at "
                        f"FROM {tenant['schema']}.prelabel_batches WHERE id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
            notification = (
                await conn.execute(
                    text(
                        "SELECT kind, recipient_role FROM public.notifications "
                        "WHERE resource_id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
        assert row[0] == "approved"
        assert row[1] is not None
        assert notification == ("automated_batch_approved", "tenant_admin")

        # Its suggestions are gone from the suggestion table and are now confirmed spans. Total
        # spans include the 1-document initial batch's own 2 (also accepted, above) plus this
        # large batch's 5 documents x 2 entities.
        assert await _span_count(engine, tenant) == 12
        async with engine.connect() as conn:
            remaining_suggestions = (
                await conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM {tenant['schema']}.suggested_spans "
                        "WHERE document_id = ANY(:doc_ids)"
                    ),
                    {"doc_ids": doc_ids},
                )
            ).scalar()
            provenance_count = (
                await conn.execute(
                    text(
                        f"SELECT COUNT(*) FROM {tenant['schema']}.span_batch_provenance "
                        "WHERE batch_id = :id"
                    ),
                    {"id": batch_id},
                )
            ).scalar()
        assert remaining_suggestions == 0
        assert provenance_count == 10

    async def test_large_batch_partial_success_still_promotes(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        await _approve_initial_batch(client, engine, tenant)

        doc_ids = [await add_document(engine, tenant) for _ in range(5)]
        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": doc_ids, "batch_kind": "large"},
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 202, resp.text
        batch_id = resp.json()["batch_id"]
        run_prelabel_batch_sync(
            tenant["tid"], batch_id, llm_client=FailingOnNthClient(DEFAULT_RESPONSE, fail_on=3)
        )

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT annotator_review_status, training_eligible_at "
                        f"FROM {tenant['schema']}.prelabel_batches WHERE id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
        # 4 of 5 documents succeeded; the batch is still promoted and training-eligible.
        assert row[0] == "approved"
        assert row[1] is not None
        # 1 (initial batch) + 4 (succeeding large-batch documents) x 2 entities.
        assert await _span_count(engine, tenant) == 2 + 8

    async def test_large_batch_full_failure_is_not_promoted(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        await _approve_initial_batch(client, engine, tenant)

        doc_ids = [await add_document(engine, tenant) for _ in range(3)]
        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": doc_ids, "batch_kind": "large"},
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 202, resp.text
        batch_id = resp.json()["batch_id"]
        run_prelabel_batch_sync(tenant["tid"], batch_id, llm_client=AlwaysFailingClient())

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT annotator_review_status, training_eligible_at, state "
                        f"FROM {tenant['schema']}.prelabel_batches WHERE id = :id"
                    ),
                    {"id": batch_id},
                )
            ).fetchone()
            notification_count = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM public.notifications WHERE resource_id = :id"),
                    {"id": batch_id},
                )
            ).scalar()
        assert row[2] == "failed"
        assert row[1] is None
        assert row[0] is None
        assert notification_count == 0
        # Only the initial batch's 2 spans exist; nothing from the fully-failed large batch.
        assert await _span_count(engine, tenant) == 2

    async def test_large_batch_acceptance_endpoints_are_refused(self, client, engine, sampling):
        sampling(enabled=False, threshold=1.0)
        tenant = await make_tenant(engine)
        await _approve_initial_batch(client, engine, tenant)

        doc_ids, batch_id = await _completed_batch(
            client, engine, tenant, 2, batch_kind="large"
        )

        for resp in (
            await client.post(
                f"/api/v1/prelabel-batches/{batch_id}/acceptance",
                headers=auth_header(tenant["tid"], "annotator"),
            ),
            await client.get(
                f"/api/v1/prelabel-batches/{batch_id}/acceptance",
                headers=auth_header(tenant["tid"], "annotator"),
            ),
            await _accept(client, tenant, batch_id),
        ):
            assert resp.status_code == 422, resp.text
            assert resp.json()["detail"]["code"] == "LARGE_BATCH_NOT_REVIEWED"

    async def test_large_batch_requires_an_approved_initial_batch_first(
        self, client, engine, fake_send_task
    ):
        tenant = await make_tenant(engine)
        doc_ids = [await add_document(engine, tenant) for _ in range(3)]

        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": doc_ids, "batch_kind": "large"},
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "INITIAL_BATCH_NOT_APPROVED"
        # Refused before enqueue — no pre-labeling work was ever scheduled for the rejected batch.
        assert len(fake_send_task) == 0
