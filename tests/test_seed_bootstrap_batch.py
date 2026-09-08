"""Batch pre-labeling: one job, per-document outcomes, and parity with the single-document path.

Covers verification.md rows 9-12.

Every test here drives `run_prelabel_batch_sync` — the real task body, with a stubbed provider.
Nothing in this file stubs the batch's own extraction or grounding, and that is deliberate:
verification.md Risk 2 is that the batch path quietly becomes a second, more forgiving
implementation, and a test that stubbed the path under test could not detect it.
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


def _entities(*pairs):
    return {"entities": [{"entity_type": t, "quote": q} for t, q in pairs]}


DEFAULT_RESPONSE = _entities(
    ("person_name", "John Doe"),
    ("institute", "Vellore Institute of Technology"),
)


class FailingOnNthClient:
    """A stub that raises on the nth call and answers normally otherwise.

    Models the realistic batch failure — one document's provider call goes wrong — rather than a
    whole-batch outage, which is the case the requirement is not about."""

    def __init__(self, response, fail_on: int):
        self.response = response
        self.fail_on = fail_on
        self.call_count = 0

    def complete_json(self, system_prompt: str, user_payload: str) -> dict:
        self.call_count += 1
        if self.call_count == self.fail_on:
            raise LLMUnavailable("provider error: simulated failure")
        return self.response


async def _batch_of(client, engine, tenant, count, document_text=None):
    kwargs = {} if document_text is None else {"document_text": document_text}
    doc_ids = [await add_document(engine, tenant, **kwargs) for _ in range(count)]
    resp = await client.post(
        "/api/v1/prelabel-batches",
        json={"document_ids": doc_ids},
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 202, resp.text
    return doc_ids, resp.json()["batch_id"]


class TestBatchTrigger:
    """verification.md row 9."""

    async def test_enqueue_batch_returns_batch_id(self, client, engine, fake_send_task):
        tenant = await make_tenant(engine)
        doc_ids = [await add_document(engine, tenant) for _ in range(120)]

        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": doc_ids},
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["batch_id"]
        assert body["document_count"] == 120
        # One handle for 120 documents. The requirement is a single trackable unit, so a
        # response carrying a list of ids would fail it even if every document were pre-labeled.
        assert isinstance(body["batch_id"], str)
        assert len(fake_send_task) == 1
        assert fake_send_task[0]["name"] == "run_prelabel_batch"
        # ADR-006 / verification.md Risk 7: change 1's non-GPU queue, never `training.jobs`.
        assert fake_send_task[0]["queue"] == settings.annotation_llm_celery_queue
        assert fake_send_task[0]["queue"] != "training.jobs"


class TestBatchExecution:
    """verification.md rows 10-12."""

    async def test_single_document_failure_does_not_abort_batch(self, client, engine):
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _batch_of(client, engine, tenant, 10)

        run_prelabel_batch_sync(
            tenant["tid"],
            batch_id,
            llm_client=FailingOnNthClient(DEFAULT_RESPONSE, fail_on=3),
        )

        resp = await client.get(
            f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
        )
        body = resp.json()
        assert body["succeeded"] == 9
        assert body["failed"] == 1
        assert body["status"] == "completed"

        failed = [d for d in body["documents"] if d["status"] == "failed"]
        assert len(failed) == 1
        assert "simulated failure" in failed[0]["error_message"]

        async with engine.connect() as conn:
            with_spans = (
                await conn.execute(
                    text(
                        f"SELECT COUNT(DISTINCT document_id) "
                        f"FROM {tenant['schema']}.suggested_spans"
                    )
                )
            ).scalar()
        assert with_spans == 9

    async def test_batch_honours_entity_type_constraint(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("institute", "person_name"))
        doc_ids, batch_id = await _batch_of(client, engine, tenant, 3)

        run_prelabel_batch_sync(
            tenant["tid"],
            batch_id,
            llm_client=StubLLMClient(
                _entities(
                    ("person_name", "John Doe"),
                    ("institute", "Vellore Institute of Technology"),
                    # Configured for nobody. It must be dropped, and it must not become an
                    # entity type as a side effect of having been suggested.
                    ("organization", "Acme Corp"),
                )
            ),
        )

        async with engine.connect() as conn:
            types = {
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            f"SELECT DISTINCT entity_type "
                            f"FROM {tenant['schema']}.suggested_spans"
                        )
                    )
                ).fetchall()
            }
            defined = {
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            "SELECT name FROM public.entity_definitions WHERE tenant_id = :tid"
                        ),
                        {"tid": tenant["tid"]},
                    )
                ).fetchall()
            }

        assert types == {"institute", "person_name"}
        assert defined == {"institute", "person_name"}

    async def test_batch_grounding_matches_single_document(self, client, engine):
        """The ungrounded quote is dropped and counted, exactly as on the single-document path.

        Both halves matter. A batch that stored the quote would be applying a weaker rule than
        change 1; a batch that dropped it without counting it would be applying the same rule
        invisibly, and the drop rate is the only signal that a model has started paraphrasing.
        """
        tenant = await make_tenant(engine)
        doc_ids, batch_id = await _batch_of(client, engine, tenant, 2)

        run_prelabel_batch_sync(
            tenant["tid"],
            batch_id,
            llm_client=StubLLMClient(
                _entities(
                    ("person_name", "John Doe"),
                    # Computed rather than copied — the failure mode `ground_quote` exists for.
                    ("institute", "VIT Vellore"),
                )
            ),
        )

        resp = await client.get(
            f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
        )
        body = resp.json()
        assert body["succeeded"] == 2
        for document in body["documents"]:
            assert document["counts"]["returned"] == 2
            assert document["counts"]["grounded"] == 1
            assert document["counts"]["ungrounded"] == 1
        assert body["ungrounded"] == 2

        async with engine.connect() as conn:
            stored = {
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            f"SELECT DISTINCT text_content "
                            f"FROM {tenant['schema']}.suggested_spans"
                        )
                    )
                ).fetchall()
            }
        assert stored == {"John Doe"}
