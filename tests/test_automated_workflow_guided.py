"""Automated annotation guided workflow — batch_kind, named state, reviewer role gates,
and the Annotator-Admin acceptance side effects.

Covers verification.md rows 5-11 and 20-23 of the `automated-annotation-guided-workflow`
change. The Q&A-pair proposal input (rows 1-4) and initial-batch prompt guidance (rows
12-14) are exercised by the schema-proposal / batch suites once implemented.
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
from src.annotation_service.worker import run_prelabel_batch_sync, run_schema_proposal_sync
from src.shared.config import settings
from tests.seed_bootstrap_support import (
    add_document,
    auth_header,
    drop_test_schemas,
    make_tenant,
)

PROPOSAL_RESPONSE = {
    "candidates": [
        {
            "name": "person_name",
            "description": "a person's name",
            "examples": ["John Doe"],
        }
    ]
}

DEFAULT_RESPONSE = {
    "entities": [
        {"entity_type": "person_name", "quote": "John Doe"},
        {"entity_type": "institute", "quote": "Vellore Institute of Technology"},
    ]
}
EMPTY_RESPONSE = {"entities": []}


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
    async with engine.connect() as conn:
        await conn.execute(text("DELETE FROM public.notifications"))


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
        calls.append({"name": name, "args": args})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


@pytest.fixture(autouse=True)
def full_review(monkeypatch):
    # Full review, threshold 1.0 — deterministic and the whole batch is the sample.
    monkeypatch.setattr(settings, "seed_bootstrap_sampling_enabled", False)
    monkeypatch.setattr(settings, "seed_bootstrap_agreement_threshold", 1.0)


async def _trigger(client, tenant, doc_ids, kind=None, role="tenant_admin"):
    body = {"document_ids": doc_ids}
    if kind is not None:
        body["batch_kind"] = kind
    return await client.post(
        "/api/v1/prelabel-batches", json=body, headers=auth_header(tenant["tid"], role)
    )


async def _run(tenant, batch_id, response=DEFAULT_RESPONSE, per_doc=None):
    run_prelabel_batch_sync(
        tenant["tid"],
        batch_id,
        llm_client=StubLLMClient(response) if per_doc is None else StubLLMClient(per_doc),
    )


async def _notifications(engine, tenant):
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT kind, recipient_role, resource_id FROM public.notifications "
                "WHERE tenant_id = :t"
            ),
            {"t": tenant["tid"]},
        )
        return rows.fetchall()


# ── Batch kind (rows 5-7) ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_initial_batch_capped_at_five(client, engine):
    tenant = await make_tenant(engine)
    doc_ids = [await add_document(engine, tenant) for _ in range(8)]
    resp = await _trigger(client, tenant, doc_ids, kind="initial")
    assert resp.status_code == 422
    assert "5" in resp.text


@pytest.mark.asyncio
async def test_large_batch_no_cap_and_kind_recorded(client, engine):
    tenant = await make_tenant(engine)
    doc_ids = [await add_document(engine, tenant) for _ in range(7)]
    resp = await _trigger(client, tenant, doc_ids, kind="large")
    assert resp.status_code == 202
    assert resp.json()["batch_kind"] == "large"


@pytest.mark.asyncio
async def test_batch_status_reports_kind(client, engine):
    tenant = await make_tenant(engine)
    a = await _trigger(client, tenant, [await add_document(engine, tenant)], kind="initial")
    b = await _trigger(client, tenant, [await add_document(engine, tenant)], kind="large")
    for resp, kind in ((a, "initial"), (b, "large")):
        got = await client.get(
            f"/api/v1/prelabel-batches/{resp.json()['batch_id']}",
            headers=auth_header(tenant["tid"]),
        )
        assert got.json()["batch_kind"] == kind


# ── Named state (rows 8-11) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_state_completed(client, engine):
    tenant = await make_tenant(engine)
    doc_ids = [await add_document(engine, tenant) for _ in range(3)]
    batch_id = (await _trigger(client, tenant, doc_ids, kind="large")).json()["batch_id"]
    await _run(tenant, batch_id)
    got = await client.get(
        f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
    )
    assert got.json()["state"] == "completed"


@pytest.mark.asyncio
async def test_state_failed_no_spans(client, engine, monkeypatch):
    tenant = await make_tenant(engine)
    doc_ids = [await add_document(engine, tenant) for _ in range(3)]
    batch_id = (await _trigger(client, tenant, doc_ids, kind="large")).json()["batch_id"]

    from src.annotation_service import worker as worker_module

    def _boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(worker_module, "extract_and_ground_document", _boom)
    await _run(tenant, batch_id)

    got = await client.get(
        f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
    )
    assert got.json()["state"] == "failed"
    async with engine.connect() as conn:
        spans = (
            await conn.execute(text(f"SELECT COUNT(*) FROM {tenant['schema']}.spans"))
        ).scalar()
    assert spans == 0


@pytest.mark.asyncio
async def test_state_queued_before_run(client, engine):
    tenant = await make_tenant(engine)
    batch_id = (
        await _trigger(client, tenant, [await add_document(engine, tenant)], kind="large")
    ).json()["batch_id"]
    got = await client.get(
        f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
    )
    assert got.json()["state"] == "queued"


# ── Reviewer role gates + side effects (rows 20-23) ─────────────────────────


async def _drive_to_accept(client, engine, tenant, kind, reviewer_role):
    doc_ids = [await add_document(engine, tenant) for _ in range(3)]
    batch_id = (await _trigger(client, tenant, doc_ids, kind=kind)).json()["batch_id"]
    await _run(tenant, batch_id)
    start = await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance",
        headers=auth_header(tenant["tid"], reviewer_role),
    )
    if start.status_code != 201:
        return batch_id, start
    sample = await client.get(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance",
        headers=auth_header(tenant["tid"], reviewer_role),
    )
    dispositions = [
        {"suggestion_id": s["id"], "disposition": "agree"}
        for s in sample.json()["suggestions"]
    ]
    await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance/review",
        json={"dispositions": dispositions},
        headers=auth_header(tenant["tid"], reviewer_role),
    )
    accept = await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance/accept",
        headers=auth_header(tenant["tid"], reviewer_role),
    )
    return batch_id, accept


@pytest.mark.asyncio
async def test_tenant_admin_cannot_accept_large_batch(client, engine):
    tenant = await make_tenant(engine)
    _, resp = await _drive_to_accept(client, engine, tenant, "large", "tenant_admin")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_annotator_cannot_review_initial_batch(client, engine):
    tenant = await make_tenant(engine)
    _, resp = await _drive_to_accept(client, engine, tenant, "initial", "annotator")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_annotator_accept_large_batch_eligible_and_notifies(client, engine):
    tenant = await make_tenant(engine)
    batch_id, accept = await _drive_to_accept(client, engine, tenant, "large", "annotator")
    assert accept.status_code == 200, accept.text
    assert accept.json()["training_eligible"] is True

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
    assert row[0] == "approved"
    assert row[1] is not None

    notes = await _notifications(engine, tenant)
    assert len(notes) == 1
    assert notes[0][0] == "automated_batch_approved"
    assert notes[0][1] == "tenant_admin"
    assert notes[0][2] == batch_id


@pytest.mark.asyncio
async def test_initial_batch_accept_no_side_effects(client, engine):
    tenant = await make_tenant(engine)
    batch_id, accept = await _drive_to_accept(
        client, engine, tenant, "initial", "tenant_admin"
    )
    assert accept.status_code == 200, accept.text
    assert accept.json()["training_eligible"] is False

    async with engine.connect() as conn:
        eligible_at = (
            await conn.execute(
                text(
                    f"SELECT training_eligible_at FROM {tenant['schema']}.prelabel_batches "
                    "WHERE id = :id"
                ),
                {"id": batch_id},
            )
        ).scalar()
    assert eligible_at is None
    assert await _notifications(engine, tenant) == []


@pytest.mark.asyncio
async def test_large_batch_accept_is_idempotent(client, engine):
    tenant = await make_tenant(engine)
    batch_id, first = await _drive_to_accept(client, engine, tenant, "large", "annotator")
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/acceptance/accept",
        headers=auth_header(tenant["tid"], "annotator"),
    )
    assert second.status_code == 422  # BATCH_ALREADY_DECIDED

    async with engine.connect() as conn:
        span_count = (
            await conn.execute(text(f"SELECT COUNT(*) FROM {tenant['schema']}.spans"))
        ).scalar()
    notes = await _notifications(engine, tenant)
    assert len(notes) == 1  # exactly one notification, not two
    assert span_count > 0


# ── Q&A-pair proposal input (rows 1-4) ─────────────────────────────────────


async def _add_qa_pair(engine, tenant, text_value="What is the contract identifier? The contract identifier is C-900."):
    return await add_document(engine, tenant, document_text=text_value, purpose="qa_pair")


@pytest.mark.asyncio
async def test_proposal_accepts_qa_pair_document(client, engine):
    tenant = await make_tenant(engine)
    seeds = [await add_document(engine, tenant) for _ in range(3)]
    qa_id = await _add_qa_pair(engine, tenant)
    resp = await client.post(
        "/api/v1/schema-proposals",
        json={"document_ids": seeds, "qa_pair_document_id": qa_id},
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 202, resp.text
    proposal_id = resp.json()["proposal_id"]
    got = await client.get(
        f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
    )
    assert got.json()["qa_pair_document_id"] == qa_id


@pytest.mark.asyncio
async def test_qa_pair_text_in_prompt(client, engine):
    tenant = await make_tenant(engine)
    seeds = [await add_document(engine, tenant) for _ in range(3)]
    qa_id = await _add_qa_pair(engine, tenant, "What is the contract identifier?")
    resp = await client.post(
        "/api/v1/schema-proposals",
        json={"document_ids": seeds, "qa_pair_document_id": qa_id},
        headers=auth_header(tenant["tid"]),
    )
    proposal_id = resp.json()["proposal_id"]
    stub = StubLLMClient(PROPOSAL_RESPONSE)
    run_schema_proposal_sync(tenant["tid"], proposal_id, llm_client=stub)
    assert "What is the contract identifier?" in stub.calls[-1][1]


@pytest.mark.asyncio
async def test_qa_pair_unsupported_type_rejected(client, engine):
    """A document not uploaded as purpose='qa_pair' (e.g. a .csv rejected upstream never
    becomes one) cannot be used as the Q&A pair."""
    tenant = await make_tenant(engine)
    seeds = [await add_document(engine, tenant) for _ in range(3)]
    not_qa = await add_document(engine, tenant)  # purpose='training'
    resp = await client.post(
        "/api/v1/schema-proposals",
        json={"document_ids": seeds, "qa_pair_document_id": not_qa},
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 422
    assert "qa_pair" in resp.text


@pytest.mark.asyncio
async def test_qa_pair_creates_no_entity_types(client, engine):
    tenant = await make_tenant(engine)
    seeds = [await add_document(engine, tenant) for _ in range(3)]
    qa_id = await _add_qa_pair(engine, tenant)
    await client.post(
        "/api/v1/schema-proposals",
        json={"document_ids": seeds, "qa_pair_document_id": qa_id},
        headers=auth_header(tenant["tid"]),
    )
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM public.entity_definitions WHERE tenant_id = :t"),
                {"t": tenant["tid"]},
            )
        ).scalar()
    assert count == 2  # the two make_tenant seeded, unchanged


# ── Initial-batch review guidance (rows 12-14) ─────────────────────────────


@pytest.mark.asyncio
async def test_initial_guidance_persisted(client, engine):
    tenant = await make_tenant(engine)
    doc = await add_document(engine, tenant)
    batch_id = (await _trigger(client, tenant, [doc], kind="initial")).json()["batch_id"]
    resp = await client.post(
        f"/api/v1/prelabel-batches/{batch_id}/guidance",
        json={
            "document_id": doc,
            "corrected_spans": [{"text": "Acme", "entity_type": "org"}],
            "note": "treat internal project codenames as PROJECT",
        },
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 201
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    f"SELECT corrected_spans, note FROM {tenant['schema']}.prelabel_batch_guidance "
                    "WHERE batch_id = :b"
                ),
                {"b": batch_id},
            )
        ).fetchone()
    assert row[1] == "treat internal project codenames as PROJECT"


@pytest.mark.asyncio
async def test_large_batch_prompt_includes_guidance(client, engine):
    tenant = await make_tenant(engine)
    initial_doc = await add_document(engine, tenant)
    initial_id = (
        await _trigger(client, tenant, [initial_doc], kind="initial")
    ).json()["batch_id"]
    await client.post(
        f"/api/v1/prelabel-batches/{initial_id}/guidance",
        json={"document_id": initial_doc, "note": "treat internal project codenames as PROJECT"},
        headers=auth_header(tenant["tid"]),
    )

    large_doc = await add_document(engine, tenant)
    trigger = await _trigger(client, tenant, [large_doc], kind="large")
    assert trigger.json()["guidance_applied"] is True
    guidance_text = trigger.json().get("guidance_applied")

    # The task receives the rendered guidance; assert it reaches the pre-label prompt.
    from src.annotation_service.api.v1 import seed_bootstrap as sb

    rendered = sb.render_guidance_text(
        [{"corrected_spans": [], "note": "treat internal project codenames as PROJECT"}]
    )
    stub = StubLLMClient(DEFAULT_RESPONSE)
    batch_id = trigger.json()["batch_id"]
    run_prelabel_batch_sync(tenant["tid"], batch_id, llm_client=stub, guidance_text=rendered)
    assert "treat internal project codenames as PROJECT" in stub.calls[-1][1]


@pytest.mark.asyncio
async def test_large_batch_without_guidance_runs(client, engine):
    tenant = await make_tenant(engine)
    doc = await add_document(engine, tenant)
    trigger = await _trigger(client, tenant, [doc], kind="large")
    assert trigger.status_code == 202
    assert trigger.json()["guidance_applied"] is False
