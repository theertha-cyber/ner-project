"""Entity schema proposal: request, candidate validation, and per-candidate disposition.

Covers verification.md rows 1-8.

The provider is stubbed throughout — `StubLLMClient`, never a network call — but the database is
real, and the approval path runs the real `EntityService.create_entity_type`. That last point is
the reason these tests are worth their runtime: the requirement is not "an entity type row
appears", it is "the entity type was created through the existing entity-config API", and only
executing that API proves it (verification.md Risk 1).

Celery is stubbed the way `test_llm_prelabel_api.py` stubs it: the trigger is asserted to have
enqueued, and the task body is then invoked directly.
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
from src.annotation_service.worker import run_schema_proposal_sync
from src.shared.config import settings
from tests.seed_bootstrap_support import (
    DOCUMENT_TEXT,
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
    """Record enqueues instead of reaching a broker."""
    from src.annotation_service.api.v1 import seed_bootstrap as module

    calls = []

    def _send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args, "queue": kwargs.get("queue")})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


def _candidates(*entries):
    return {
        "candidates": [
            {"name": name, "description": description, "examples": list(examples)}
            for name, description, examples in entries
        ]
    }


DEFAULT_RESPONSE = _candidates(
    ("institute", "A school", ["Vellore Institute of Technology", "Anna University"]),
    ("organization", "A company", ["Acme Corp", "Globex"]),
    ("person_name", "A person", ["John Doe", "Jane Roe"]),
    ("job_title", "A role", ["Senior Engineer", "Data Analyst"]),
)


async def _seed_proposal(client, engine, tenant, response=DEFAULT_RESPONSE, documents=5):
    doc_ids = [await add_document(engine, tenant) for _ in range(documents)]
    resp = await client.post(
        "/api/v1/schema-proposals",
        json={"document_ids": doc_ids},
        headers=auth_header(tenant["tid"]),
    )
    assert resp.status_code == 202, resp.text
    proposal_id = resp.json()["proposal_id"]
    run_schema_proposal_sync(tenant["tid"], proposal_id, llm_client=StubLLMClient(response))
    return proposal_id


async def _candidate_named(client, tenant, proposal_id, name):
    resp = await client.get(
        f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
    )
    assert resp.status_code == 200, resp.text
    for candidate in resp.json()["candidates"]:
        if candidate["name"] == name:
            return candidate
    raise AssertionError(f"no candidate named {name} in {resp.json()['candidates']}")


class TestProposalGeneration:
    """verification.md rows 1-4."""

    async def test_request_proposal_returns_202(self, client, engine, fake_send_task):
        tenant = await make_tenant(engine)
        doc_ids = [await add_document(engine, tenant) for _ in range(5)]

        resp = await client.post(
            "/api/v1/schema-proposals",
            json={"document_ids": doc_ids},
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 202, resp.text
        assert resp.json()["proposal_id"]
        assert resp.json()["seed_document_count"] == 5
        # The work was handed off, and onto change 1's non-GPU queue rather than `training.jobs`
        # (ADR-006, verification.md Risk 7).
        assert fake_send_task[0]["name"] == "run_schema_proposal"
        assert fake_send_task[0]["queue"] == settings.annotation_llm_celery_queue

    async def test_candidate_examples_are_verbatim(self, client, engine):
        tenant = await make_tenant(engine)
        proposal_id = await _seed_proposal(
            client,
            engine,
            tenant,
            response=_candidates(
                ("institute", "A school", ["Vellore Institute of Technology"]),
                # Plausible, well-formed, and nowhere in the document. The whole point of the
                # verbatim rule is that this one does not survive.
                ("degree", "A qualification", ["Bachelor of Technology"]),
            ),
        )

        resp = await client.get(
            f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
        )

        assert resp.status_code == 200, resp.text
        candidates = resp.json()["candidates"]
        assert candidates, "expected at least one surviving candidate"
        for candidate in candidates:
            assert candidate["name"]
            assert candidate["description"]
            assert candidate["examples"]
            for example in candidate["examples"]:
                assert example.lower() in DOCUMENT_TEXT.lower(), example
        assert "degree" not in {candidate["name"] for candidate in candidates}

    async def test_proposal_creates_no_entity_types(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name", "institute"))
        async with engine.connect() as conn:
            before = (
                await conn.execute(
                    text(
                        "SELECT name, version FROM public.entity_definitions "
                        "WHERE tenant_id = :tid ORDER BY name"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).fetchall()
        assert len(before) == 2

        proposal_id = await _seed_proposal(client, engine, tenant)

        resp = await client.get(
            f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
        )
        assert len(resp.json()["candidates"]) == 4

        async with engine.connect() as conn:
            after = (
                await conn.execute(
                    text(
                        "SELECT name, version FROM public.entity_definitions "
                        "WHERE tenant_id = :tid ORDER BY name"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).fetchall()
        assert [tuple(row) for row in after] == [tuple(row) for row in before]

    async def test_proposal_422_no_processed_documents(self, client, engine):
        tenant = await make_tenant(engine)
        doc_ids = [await add_document(engine, tenant, document_text=None) for _ in range(3)]

        resp = await client.post(
            "/api/v1/schema-proposals",
            json={"document_ids": doc_ids},
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "NO_PROCESSED_DOCUMENTS"


class TestCandidateDisposition:
    """verification.md rows 5-8."""

    async def test_approve_candidate_creates_entity_type(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name",))
        proposal_id = await _seed_proposal(client, engine, tenant)
        candidate = await _candidate_named(client, tenant, proposal_id, "institute")

        resp = await client.post(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}/approve",
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 201, resp.text
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT name, version, is_active, sql_identifier "
                        "FROM public.entity_definitions "
                        "WHERE tenant_id = :tid AND name = 'institute'"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).fetchone()
        assert row is not None
        assert row[1] == 1
        assert row[2] is True
        # Assigned by `EntityService.create_entity_type` and by nothing else. Its presence is
        # the evidence that the entity type came through the entity-config API rather than a
        # direct INSERT written here (verification.md Risk 1).
        assert row[3]

        assert (await _candidate_named(client, tenant, proposal_id, "institute"))[
            "disposition"
        ] == "approved"

    async def test_approved_candidate_is_suggested_provenance(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name",))
        proposal_id = await _seed_proposal(client, engine, tenant)
        candidate = await _candidate_named(client, tenant, proposal_id, "institute")

        resp = await client.post(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}/approve",
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 201, resp.text

        async with engine.connect() as conn:
            provenance = (
                await conn.execute(
                    text(
                        "SELECT provenance FROM public.entity_definitions "
                        "WHERE tenant_id = :tid AND name = 'institute'"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).scalar()
        assert provenance == "suggested"

    async def test_reject_candidate_creates_nothing(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name",))
        proposal_id = await _seed_proposal(client, engine, tenant)
        candidate = await _candidate_named(client, tenant, proposal_id, "job_title")

        resp = await client.post(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}/reject",
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 200, resp.text
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT id FROM public.entity_definitions "
                        "WHERE tenant_id = :tid AND name = 'job_title'"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).fetchone()
        assert row is None
        assert (await _candidate_named(client, tenant, proposal_id, "job_title"))[
            "disposition"
        ] == "rejected"

    async def test_edit_candidate_before_approval(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name",))
        proposal_id = await _seed_proposal(client, engine, tenant)
        candidate = await _candidate_named(client, tenant, proposal_id, "institute")
        assert candidate["description"] == "A school"

        edit = await client.patch(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}",
            json={"description": "A degree-granting institution"},
            headers=auth_header(tenant["tid"]),
        )
        assert edit.status_code == 200, edit.text
        assert edit.json()["disposition"] == "edited"

        approve = await client.post(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}/approve",
            headers=auth_header(tenant["tid"]),
        )
        assert approve.status_code == 201, approve.text

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT description FROM public.entity_definitions "
                        "WHERE tenant_id = :tid AND name = 'institute'"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).fetchone()
        assert row[0] == "A degree-granting institution"

    async def test_approve_duplicate_name_422(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("person_name", "institute"))
        proposal_id = await _seed_proposal(client, engine, tenant)
        candidate = await _candidate_named(client, tenant, proposal_id, "institute")

        resp = await client.post(
            f"/api/v1/schema-proposals/candidates/{candidate['id']}/approve",
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 422, resp.text
        assert resp.json()["detail"]["code"] == "DUPLICATE_ENTITY_TYPE"
        async with engine.connect() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM public.entity_definitions "
                        "WHERE tenant_id = :tid AND name = 'institute'"
                    ),
                    {"tid": tenant["tid"]},
                )
            ).scalar()
        assert count == 1


class TestQaDrivenProposal:
    """A Q&A-pair document turns the proposal into schema transcription: one entity type per
    Q&A pair, kept even when the seed documents contain no value for it."""

    async def _seed_qa_proposal(self, client, engine, tenant, response):
        doc_ids = [await add_document(engine, tenant) for _ in range(3)]
        qa_id = await add_document(
            engine,
            tenant,
            document_text=(
                "What is the candidate's full name?\n"
                "What is the candidate's notice period?\n"
            ),
            purpose="qa_pair",
        )
        resp = await client.post(
            "/api/v1/schema-proposals",
            json={"document_ids": doc_ids, "qa_pair_document_id": qa_id},
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 202, resp.text
        proposal_id = resp.json()["proposal_id"]
        run_schema_proposal_sync(
            tenant["tid"], proposal_id, llm_client=StubLLMClient(response)
        )
        return proposal_id

    async def test_ungrounded_candidate_survives_with_qa_answer_fallback(self, client, engine):
        tenant = await make_tenant(engine)
        proposal_id = await self._seed_qa_proposal(
            client,
            engine,
            tenant,
            _candidates(
                # grounded in DOCUMENT_TEXT
                ("full_name", "The candidate's name", ["John Doe", "Jane Roe"]),
                # nowhere in the documents — the model falls back to the Q&A answer
                ("notice_period", "How soon the candidate can start", ["2 months"]),
            ),
        )
        resp = await client.get(
            f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
        )
        names = {c["name"]: c for c in resp.json()["candidates"]}
        assert set(names) == {"full_name", "notice_period"}
        # Kept as the model's fallback value, not dropped.
        assert names["notice_period"]["examples"] == ["2 months"]
        assert names["full_name"]["examples"] == ["John Doe", "Jane Roe"]

    async def test_lenient_matching_ignores_spacing_and_punctuation(self):
        from src.annotation_service.services.schema_proposal import validate_candidate_examples

        docs = [{"text": "Current CGPA: 8.09/10.0 at Vellore  Institute of Technology"}]
        candidates = [
            {"name": "gpa", "description": "d", "examples": ["8.09 / 10.0"]},
            {"name": "institute", "description": "d", "examples": ["Vellore Institute of Technology"]},
            {"name": "phone", "description": "d", "examples": ["+91 99999 00000"]},  # absent
        ]
        out = {c["name"]: c["examples"] for c in validate_candidate_examples(
            candidates, docs, require_grounding=False, lenient=True
        )}
        assert out["gpa"] == ["8.09 / 10.0"]
        assert out["institute"] == ["Vellore Institute of Technology"]
        # Absent from the doc, but no non-value phrase, so kept as the model's fallback value.
        assert out["phone"] == ["+91 99999 00000"]

    async def test_non_value_answer_is_not_kept_as_an_example(self, client, engine):
        tenant = await make_tenant(engine)
        proposal_id = await self._seed_qa_proposal(
            client,
            engine,
            tenant,
            _candidates(
                ("notice_period", "How soon", ["Not specified in the document"]),
            ),
        )
        candidate = await _candidate_named(client, tenant, proposal_id, "notice_period")
        assert candidate["examples"] == []

    async def test_candidate_cap_follows_qa_pair_count(self):
        from src.annotation_service.services.schema_proposal import (
            MAX_CANDIDATES,
            count_qa_pairs,
            resolve_max_candidates,
        )

        twenty = "\n".join(f"Q: question {i}?\nA: answer {i}" for i in range(20))
        assert count_qa_pairs(twenty) == 20
        assert resolve_max_candidates(twenty) == 25  # 20 + headroom

        fifty = "\n".join(f"{i}. Field {i}?" for i in range(1, 51))
        assert resolve_max_candidates(fifty) == 55

        assert resolve_max_candidates(None) == MAX_CANDIDATES
        assert resolve_max_candidates("   ") == MAX_CANDIDATES

    async def test_hallucinated_example_is_still_stripped_when_grounded_ones_exist(
        self, client, engine
    ):
        tenant = await make_tenant(engine)
        proposal_id = await self._seed_qa_proposal(
            client,
            engine,
            tenant,
            _candidates(
                ("full_name", "The candidate's name", ["John Doe", "Fabricated Person"]),
            ),
        )
        candidate = await _candidate_named(client, tenant, proposal_id, "full_name")
        assert candidate["examples"] == ["John Doe"]

    async def test_discovery_mode_unchanged_without_qa_pair(self, client, engine):
        """No Q&A pair: an ungroundable candidate is still dropped."""
        tenant = await make_tenant(engine)
        proposal_id = await _seed_proposal(
            client,
            engine,
            tenant,
            _candidates(
                ("institute", "A school", ["Vellore Institute of Technology"]),
                ("degree", "A qualification", ["Bachelor of Technology"]),
            ),
        )
        resp = await client.get(
            f"/api/v1/schema-proposals/{proposal_id}", headers=auth_header(tenant["tid"])
        )
        names = {c["name"] for c in resp.json()["candidates"]}
        assert "institute" in names
        assert "degree" not in names
