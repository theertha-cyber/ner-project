"""Automated upload-to-answer path for uploaded tabular files (tabular-file-chat
spec, "End-to-end tabular answer"; verification row 55, Risk 9).

Real: the gateway upload/review/publish routes and the chat route (signed JWT),
platform MinIO, the ingest worker code, DuckDB, the Parquet cache, the AST
validator and the locked executor. Stubbed: only LLM calls — the planner (which
selects `tabular_files`), the SQL generator, and the chat model's domain check
and answer. The Celery broker hop is replaced by awaiting the same worker
function the task would run, because a broker is not part of what this proves.
Follows `tests/test_cited_document_viewer_end_to_end.py`.
"""

import json
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.chat_api.api.v1 import chat as chat_module
from src.chat_api.main import app as chat_app
from src.chat_api.services.tabular_cache import ParquetCache
from src.chat_api.services.tabular_sql_generator import TabularSQLGenerator
from src.gateway.api.v1 import tabular_files as api
from src.gateway.main import app as gateway_app
from src.shared.auth import create_access_token
from src.shared.config import settings
from src.shared.tabular_files import store, worker
from src.shared.tabular_files.storage import TabularObjectStore, file_prefix
from tests.tabular_support import SALES_Q3_CSV, ScriptedGeneratorClient

pytestmark = [pytest.mark.verification, pytest.mark.integration]

QUESTION = "total closed revenue in EMEA?"
GENERATED = {"sql": "SELECT SUM(amount) AS total FROM sales_q3 WHERE region = %(p1)s AND status = %(p2)s",
             "params": {"p1": "EMEA", "p2": "closed"}}


class ChatModelStub:
    """The chat model's three roles in a turn, told apart by request shape:
    the planner is offered tools, the domain check asks for a handful of tokens,
    and everything else is answer generation. Every request is recorded."""

    def __init__(self):
        self.requests: list[dict] = []

        async def create(**kwargs):
            self.requests.append(kwargs)
            if kwargs.get("tools") and any(t["function"]["name"] == "tabular_files" for t in kwargs["tools"]):
                call = SimpleNamespace(id="call-1", type="function", function=SimpleNamespace(
                    name="tabular_files", arguments=json.dumps({"query": QUESTION})))
                message = SimpleNamespace(content=None, tool_calls=[call])
            elif kwargs.get("max_tokens", 0) <= 10:
                message = SimpleNamespace(content="in_domain", tool_calls=None)
            else:
                message = SimpleNamespace(content="Closed revenue in EMEA is 1650.", tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    def generation_prompts(self) -> list[str]:
        return [json.dumps(r["messages"], default=str) for r in self.requests
                if not r.get("tools") and r.get("max_tokens", 0) > 10]


def _auth(tenant_id, role, user_id):
    return {"Authorization": f"Bearer {create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)}"}


def _real_minio() -> TabularObjectStore:
    """The live MinIO the compose stack publishes on localhost. `tests/conftest.py`
    pins placeholder MinIO keys for the unit suite, so the real ones are read from
    `.env` here; the test skips when MinIO is not reachable."""
    import boto3
    from dotenv import dotenv_values

    env = dotenv_values(".env")
    client = boto3.client(
        "s3", endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=env.get("NER_MINIO_ACCESS_KEY"),
        aws_secret_access_key=env.get("NER_MINIO_SECRET_KEY"),
        config=boto3.session.Config(signature_version="s3v4"),
    )
    try:
        return TabularObjectStore(client=client, bucket=env.get("NER_MINIO_BUCKET") or settings.minio_bucket)
    except Exception as exc:
        pytest.skip(f"MinIO not reachable: {type(exc).__name__}")


@pytest.fixture
async def minio_cleanup():
    objects = _real_minio()
    created: list[tuple[str, str]] = []
    yield objects, created
    for tenant_id, file_id in created:
        objects.delete_prefix(file_prefix(tenant_id, file_id))


async def test_automated_upload_to_answer_path(engine, tenant_schema, db_session, tmp_path, monkeypatch, minio_cleanup):
    """Scenario: Automated upload-to-answer path."""
    tenant_id, schema = tenant_schema
    objects, created = minio_cleanup
    monkeypatch.setattr(settings, "tabular_files_enabled", True)
    monkeypatch.setattr(settings, "tabular_staging_dir", str(tmp_path / "staging"))
    enqueued: list[tuple[str, str, int]] = []
    monkeypatch.setattr(api, "_enqueue_profile", lambda f, v: enqueued.append(("profile", f, v)))
    monkeypatch.setattr(api, "_enqueue_publish", lambda f, v: enqueued.append(("publish", f, v)))
    monkeypatch.setattr(api, "get_object_store", lambda: objects)

    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # The real graph's entity-resolution node reads these tenant tables; the shared
    # fixture does not create them (same setup as the uploader-isolation e2e test).
    async with session_factory() as session:
        await session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.conversation_entity_state (
                conversation_id VARCHAR PRIMARY KEY, pending_original_message TEXT,
                pending_mention TEXT, pending_candidates JSONB, pending_reask_count INTEGER DEFAULT 0,
                resolved_document_id VARCHAR, resolved_entity_value TEXT)"""))
        await session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_entities (
                id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
                confidence DOUBLE PRECISION NOT NULL)"""))
        await session.commit()

    async def drain():
        while enqueued:
            kind, file_id, version = enqueued.pop(0)
            runner = worker.run_profile if kind == "profile" else worker.run_publish
            await runner(session_factory, objects, file_id, version)

    admin = _auth(tenant_id, "tenant_admin", "admin-1")
    try:
        async with AsyncClient(transport=ASGITransport(app=gateway_app), base_url="http://gw") as gw:
            response = await gw.post("/api/v1/data-sources/files", headers=admin,
                                     files={"file": ("sales_q3.csv", SALES_Q3_CSV.encode(), "text/csv")})
            assert response.status_code == 201, response.text
            file_id = response.json()["id"]
            created.append((tenant_id, file_id))
            assert objects.exists(f"tenants/{tenant_id}/tabular/{file_id}/v1/original.csv")
            await drain()

            profile = (await gw.get(f"/api/v1/data-sources/files/{file_id}/versions/1/profile", headers=admin)).json()
            assert profile["status"] == "needs_review"
            review = await gw.put(f"/api/v1/data-sources/files/{file_id}/versions/1/review", headers=admin,
                                  json={"table": {"description": "Q3 sales deals by region"}})
            assert review.status_code == 200 and review.json()["blockers"] == []
            published = await gw.post(f"/api/v1/data-sources/files/{file_id}/versions/1/publish",
                                       headers={**admin, "Idempotency-Key": uuid.uuid4().hex})
            assert published.status_code == 202, published.text
            await drain()
            listing = (await gw.get("/api/v1/data-sources/files", headers=admin)).json()
            assert [f["status"] for f in listing["files"]] == ["ready"]
            assert objects.exists(f"tenants/{tenant_id}/tabular/{file_id}/v1/data.parquet")

        chat_model = ChatModelStub()
        generator = TabularSQLGenerator(cache=ParquetCache(root=str(tmp_path / "cache"), max_bytes=10**9,
                                                           object_store_factory=lambda: objects))
        generator.client = ScriptedGeneratorClient(GENERATED)
        monkeypatch.setattr(chat_module.orchestrator, "llm_client", chat_model)
        monkeypatch.setattr(chat_module.orchestrator, "tabular_sql_generator", generator)

        envelopes = []
        from src.shared.retrieval.tools import tabular_tools
        real_call = tabular_tools.TabularFilesTool.call

        async def spy_call(self, args, context):
            result = await real_call(self, args, context)
            envelopes.append(result)
            return result

        monkeypatch.setattr(tabular_tools.TabularFilesTool, "call", spy_call)

        user = _auth(tenant_id, "business_user", "test-user")
        async with AsyncClient(transport=ASGITransport(app=chat_app), base_url="http://chat") as chat:
            answer = await chat.post("/api/v1/chat", headers=user, json={"message": QUESTION, "conversation_id": None})
            assert answer.status_code == 200, answer.text
            body = answer.json()
            reloaded = (await chat.get(f"/api/v1/chat/conversations/{body['conversation_id']}", headers=user)).json()

        [envelope] = envelopes
        assert envelope.error is None
        assert envelope.results == [{"total": 1650}]
        assert any("1650" in prompt for prompt in chat_model.generation_prompts())
        assert "1650" in body["reply"]

        assistant = [m for m in reloaded["messages"] if m["role"] == "assistant"][0]
        [citation] = [s for s in assistant["sources"] if s["source_type"] == "tabular_file"]
        assert citation["file_name"] == "sales_q3.csv"
        assert citation["file_version"] == 1
        serialized = json.dumps(assistant["sources"])
        assert "EMEA" not in serialized and "closed" not in serialized
    finally:
        async with session_factory() as session:
            for table in (store.VERSIONS_TABLE, store.FILES_TABLE):
                await session.execute(text(f"DELETE FROM {table} WHERE tenant_id = :t"), {"t": tenant_id})
            await session.execute(text("DELETE FROM public.tenant_data_source_idempotency WHERE tenant_id = :t"),
                                  {"t": tenant_id})
            await session.commit()
