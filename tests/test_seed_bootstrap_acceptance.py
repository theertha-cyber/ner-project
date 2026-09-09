"""The sampled acceptance gate: random sample, measured rate, one decision for the whole batch.

Covers verification.md rows 13-17.

Sampling is enabled explicitly in the tests that need it rather than left at its shipped default
(off, meaning full review). Both modes are exercised: `test_sample_is_random_and_recorded` needs
a strict subset to have anything to say about randomness, while the threshold tests are clearer
reviewing everything. The mode is recorded on each acceptance record, so a test can tell which
one it measured.
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
from src.annotation_service.services.llm_client import StubLLMClient
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


async def _completed_batch(client, engine, tenant, count, response=DEFAULT_RESPONSE):
    doc_ids = [await add_document(engine, tenant) for _ in range(count)]
    resp = await client.post(
        "/api/v1/prelabel-batches",
        json={"document_ids": doc_ids},
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


class TestSampleSelection:
    """verification.md row 13."""

    async def test_sample_is_random_and_recorded(self, client, engine, sampling):
        sampling(sample_size=20, threshold=1.0)
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _completed_batch(client, engine, tenant, 100)

        record = await _start_review(client, tenant, batch_id)

        sampled = record["sampled_document_ids"]
        assert len(sampled) == 20
        assert record["sample_size"] == 20
        assert record["sampled"] is True
        assert set(sampled).issubset(set(doc_ids))
        # Not the first N. Twenty documents drawn uniformly from a hundred coincide with the
        # first twenty roughly once in 5e20 draws, so this assertion is a statement about the
        # implementation rather than about luck (design.md Decision 4).
        assert sampled != doc_ids[:20]
        assert set(sampled) != set(doc_ids[:20])

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
        assert stored[1] == 20

        # A second read returns the same draw rather than a new one.
        again = await client.get(
            f"/api/v1/prelabel-batches/{batch_id}/acceptance",
            headers=auth_header(tenant["tid"], "annotator"),
        )
        assert again.json()["sampled_document_ids"] == sampled


class TestAcceptanceGate:
    """verification.md rows 14-17."""

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
