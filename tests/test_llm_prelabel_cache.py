"""Result caching, keyed on (document content hash, entity-config version).

Covers verification.md rows 14-15, and with them hallucination risk 4: a cache keyed on the
document hash alone would pass row 14 and silently fail row 15, serving a tenant the previous
run's suggestions after they changed what the prompt asks for.

The assertions are on `StubLLMClient.call_count`, because "used the cache" is a claim about
whether the provider was called, not about what came back.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.annotation_service.main import app
from src.annotation_service.services.llm_client import StubLLMClient
from src.annotation_service.worker import run_llm_prelabel_sync
from src.shared.config import settings
from tests.test_llm_prelabel_api import (  # noqa: F401 — fixtures are used by name
    DEFAULT_RESPONSE,
    DOCUMENT_TEXT,
    _add_document,
    _make_tenant,
    auth_header,
    cleanup,
    engine,
    fake_send_task,
    make_token,
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _trigger_and_run(client, engine, tenant, doc_id, stub):
    """One full cycle: trigger, and run the task only if the trigger actually enqueued one."""
    token = make_token(tenant["tid"])
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/prelabel/llm", headers=auth_header(token)
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    if not body["cached"]:
        run_llm_prelabel_sync(tenant["tid"], doc_id, body["job_id"], llm_client=stub)
    return body


class TestCacheHit:
    """verification.md row 14."""

    async def test_unchanged_document_and_config_uses_cache(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        first = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert first["cached"] is False
        assert stub.call_count == 1

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is True
        assert second["status"] == "completed"
        assert stub.call_count == 1

    async def test_a_cache_hit_still_leaves_the_suggestions_in_place(self, client, engine):
        """"Served from cache" has to mean the spans are there now.

        A keyword pre-label run between the two triggers replaces every suggestion for the
        document, so a cache hit that merely skipped the provider call would leave the reviewer
        looking at keyword spans while being told they were served an LLM result."""
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        token = make_token(tenant["tid"])
        stub = StubLLMClient(DEFAULT_RESPONSE)

        await _trigger_and_run(client, engine, tenant, doc_id, stub)

        await client.post(f"/api/v1/documents/{doc_id}/prelabel", headers=auth_header(token))
        after_keyword = await client.get(
            f"/api/v1/documents/{doc_id}/spans?type=suggested", headers=auth_header(token)
        )
        assert all(span["source"] == "keyword" for span in after_keyword.json())

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is True
        assert stub.call_count == 1

        listed = await client.get(
            f"/api/v1/documents/{doc_id}/spans?type=suggested", headers=auth_header(token)
        )
        spans = listed.json()
        assert len(spans) == 3
        assert all(span["source"] == "llm" for span in spans)


class TestCacheInvalidation:
    """verification.md row 15."""

    async def test_entity_config_change_invalidates_cache(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        first = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert first["cached"] is False
        assert stub.call_count == 1

        # The tenant adds a QA pair — the prompt now carries few-shot context it did not before,
        # so the previous run is no longer an answer to the question being asked.
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions "
                    "SET qa_examples = CAST(:qa AS JSONB), version = version + 1 "
                    "WHERE tenant_id = :tid AND name = 'person_name'"
                ),
                {
                    "tid": tenant["tid"],
                    "qa": '[{"question": "Who is the candidate?", "answer": "The candidate is X"}]',
                },
            )

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is False
        assert stub.call_count == 2

    async def test_adding_an_entity_type_invalidates_cache(self, client, engine):
        """No per-row `version` moves when a type is added, which is why the key is a hash of
        the whole active set rather than any counter."""
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert stub.call_count == 1

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, examples, is_active) "
                    "VALUES (:id, :tid, 'job_title', 'A role', '[\"Engineer\"]', true)"
                ),
                {"id": str(uuid.uuid4()), "tid": tenant["tid"]},
            )

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is False
        assert stub.call_count == 2

    async def test_deactivating_an_entity_type_invalidates_cache(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert stub.call_count == 1

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions SET is_active = false "
                    "WHERE tenant_id = :tid AND name = 'institute'"
                ),
                {"tid": tenant["tid"]},
            )

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is False
        assert stub.call_count == 2

    async def test_document_text_change_invalidates_cache(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert stub.call_count == 1

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f'UPDATE {tenant["schema"]}.document_text_spans SET "text" = :txt '
                    "WHERE document_id = :doc_id"
                ),
                {"txt": DOCUMENT_TEXT + " He reports to Alice Ray.", "doc_id": doc_id},
            )

        second = await _trigger_and_run(client, engine, tenant, doc_id, stub)
        assert second["cached"] is False
        assert stub.call_count == 2

    async def test_another_tenants_cached_result_is_never_served(self, client, engine):
        """The cache lives in the tenant's own schema, so an identical document under an
        identical configuration in another tenant is a miss, not a hit."""
        first_tenant = await _make_tenant(engine)
        second_tenant = await _make_tenant(engine)
        first_doc = await _add_document(engine, first_tenant)
        second_doc = await _add_document(engine, second_tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        await _trigger_and_run(client, engine, first_tenant, first_doc, stub)
        assert stub.call_count == 1

        result = await _trigger_and_run(client, engine, second_tenant, second_doc, stub)
        assert result["cached"] is False
        assert stub.call_count == 2
