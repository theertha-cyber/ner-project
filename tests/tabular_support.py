"""Shared fixtures for the uploaded tabular files tests (ADR-018, ADR-019).

Import the fixtures you need into a test module:
    from tests.tabular_support import (  # noqa: F401
        session_factory, tabular_env, tenants, ...
    )

`FakeObjectStore` is an in-memory stand-in for `TabularObjectStore` exposing the
same methods; the end-to-end test uses real MinIO instead. Every tenant a test
creates is removed with its tabular rows afterwards.
"""

from __future__ import annotations

import os
import shutil
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.shared.auth import create_access_token
from src.shared.config import settings
from src.shared.tabular_files import store, worker

SALES_Q3_CSV = (
    "region,status,amount,notes\n"
    "EMEA,closed,1200,first deal\n"
    "EMEA,closed,450,\n"
    "APAC,closed,900,\n"
    "AMER,open,300,\n"
)


class FakeObjectStore:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.bucket = "fake"

    def put_file(self, key, local_path):
        with open(local_path, "rb") as fh:
            self.objects[key] = fh.read()

    def download_to(self, key, local_path):
        if key not in self.objects:
            raise FileNotFoundError(key)
        with open(local_path, "wb") as fh:
            fh.write(self.objects[key])

    def exists(self, key):
        return key in self.objects

    def list_keys(self, prefix):
        return sorted(k for k in self.objects if k.startswith(prefix))

    def delete_prefix(self, prefix):
        keys = self.list_keys(prefix)
        for key in keys:
            del self.objects[key]
        return len(keys)


def admin_headers(tenant_id, **extra):
    token = create_access_token(tenant_id, "admin-1", "tenant_admin")
    return {"Authorization": f"Bearer {token}", **extra}


def user_headers(tenant_id):
    token = create_access_token(tenant_id, "user-1", "business_user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def session_factory():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def tenants(session_factory):
    """`await tenants(mode="platform")` creates a tenant and returns its id."""
    created: list[str] = []

    async def _make(mode: str = "platform") -> str:
        tid = uuid.uuid4().hex
        async with session_factory() as session:
            await session.execute(
                text("INSERT INTO public.tenants (id, name, slug, status) VALUES (:id, :n, :s, 'active')"),
                {"id": tid, "n": f"Tabular {tid[:8]}", "s": f"tabular-{tid[:8]}"},
            )
            await session.execute(
                text("INSERT INTO public.tenant_data_planes (tenant_id, mode, status, schema_revision) "
                     "VALUES (:id, :mode, 'ready', 1) ON CONFLICT (tenant_id) DO UPDATE SET mode = :mode"),
                {"id": tid, "mode": mode},
            )
            await session.commit()
        created.append(tid)
        return tid

    yield _make

    async with session_factory() as session:
        for tid in created:
            for table in (store.VERSIONS_TABLE, store.FILES_TABLE,
                          "public.tenant_data_source_idempotency", "public.tenant_data_planes"):
                await session.execute(text(f"DELETE FROM {table} WHERE tenant_id = :id"), {"id": tid})
            await session.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
        await session.commit()


@pytest.fixture
def tabular_env(monkeypatch, tmp_path):
    """Fake object store, a private staging dir, and a recording enqueue for
    both ingest tasks. Returns a namespace the test drives the worker with."""
    from src.gateway.api.v1 import tabular_files as api

    objects = FakeObjectStore()
    enqueued: list[tuple[str, str, int]] = []
    monkeypatch.setattr(api, "get_object_store", lambda: objects)
    monkeypatch.setattr(api, "_enqueue_profile", lambda f, v: enqueued.append(("profile", f, v)))
    monkeypatch.setattr(api, "_enqueue_publish", lambda f, v: enqueued.append(("publish", f, v)))
    monkeypatch.setattr(settings, "tabular_staging_dir", str(tmp_path / "staging"))
    monkeypatch.setattr(settings, "tabular_files_enabled", True)

    class Env:
        pass

    env = Env()
    env.objects = objects
    env.enqueued = enqueued
    yield env
    shutil.rmtree(tmp_path / "staging", ignore_errors=True)


@pytest.fixture
async def gateway_client():
    from src.gateway.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def upload(client, tenant_id, filename, content: bytes | str, headers=None, path="/api/v1/data-sources/files",
                 sheet=None):
    if isinstance(content, str):
        content = content.encode("utf-8")
    data = {"sheet": sheet} if sheet else None
    return await client.post(path, files={"file": (filename, content, "application/octet-stream")},
                             data=data, headers=headers or admin_headers(tenant_id))


async def drain(env, session_factory):
    """Runs every enqueued ingest task through the real worker code."""
    while env.enqueued:
        kind, file_id, version = env.enqueued.pop(0)
        runner = worker.run_profile if kind == "profile" else worker.run_publish
        await runner(session_factory, env.objects, file_id, version)


async def upload_and_profile(client, env, session_factory, tenant_id, filename="sales_q3.csv",
                             content=SALES_Q3_CSV):
    response = await upload(client, tenant_id, filename, content)
    assert response.status_code == 201, response.text
    await drain(env, session_factory)
    return response.json()["id"]


async def review(client, tenant_id, file_id, version, body):
    return await client.put(f"/api/v1/data-sources/files/{file_id}/versions/{version}/review",
                            json=body, headers=admin_headers(tenant_id))


async def publish(client, tenant_id, file_id, version, key=None):
    return await client.post(
        f"/api/v1/data-sources/files/{file_id}/versions/{version}/publish",
        headers=admin_headers(tenant_id, **{"Idempotency-Key": key or uuid.uuid4().hex}),
    )


async def publish_ready(client, env, session_factory, tenant_id, file_id, version=1,
                        description="Q3 sales deals by region"):
    response = await review(client, tenant_id, file_id, version, {"table": {"description": description}})
    assert response.status_code == 200, response.text
    response = await publish(client, tenant_id, file_id, version)
    assert response.status_code == 202, response.text
    await drain(env, session_factory)


def parquet_types(objects: FakeObjectStore, key: str, tmp_path) -> dict:
    import duckdb

    local = os.path.join(str(tmp_path), f"check-{uuid.uuid4().hex}.parquet")
    objects.download_to(key, local)
    con = duckdb.connect()
    try:
        path = local.replace("\\", "/")
        return {name: kind for name, kind, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()}
    finally:
        con.close()


SALES_CONTRACT = {
    "relation": "sales_q3", "description": "Q3 sales deals by region",
    "source_file": "sales_q3.csv", "sheet": None, "version": 1,
    "columns": [
        {"name": "region", "label": "region", "type": "text", "date_format": None,
         "description": "Sales region", "value_hints": ["EMEA", "APAC", "AMER"]},
        {"name": "status", "label": "status", "type": "text", "date_format": None,
         "description": "", "value_hints": []},
        {"name": "amount", "label": "amount", "type": "bigint", "date_format": None,
         "description": "Deal amount in USD", "value_hints": []},
    ],
}


async def make_file(session_factory, tenant_id, contract=None, *, status="ready", display_name="sales_q3.csv",
                    parquet_key=None):
    """Inserts a file with one version directly through the store. `status`
    `ready` publishes it with `contract`; anything else leaves it unpublished."""
    contract = contract or SALES_CONTRACT
    async with session_factory() as session:
        file_id = await store.create_file(session, tenant_id, display_name)
        await store.create_version(session, tenant_id, file_id, 1, source_kind="csv",
                                   source_filename=display_name,
                                   original_key=f"tenants/{tenant_id}/tabular/{file_id}/v1/original.csv")
        if status == "ready":
            await store.switch_served_version(
                session, tenant_id, file_id, 1,
                parquet_key=parquet_key or f"tenants/{tenant_id}/tabular/{file_id}/v1/data.parquet",
                contract=contract, load_report={"rows_to_load": 4},
            )
        else:
            await store.set_version_status(session, tenant_id, file_id, 1, status)
        await session.commit()
    return file_id


def write_parquet(path, select_sql: str) -> str:
    """Writes a Parquet file from a DuckDB SELECT (test data only)."""
    import duckdb

    con = duckdb.connect()
    try:
        con.execute(f"COPY ({select_sql}) TO '{str(path).replace(chr(92), '/')}' (FORMAT PARQUET)")
    finally:
        con.close()
    return str(path)


SALES_ROWS_SQL = (
    "SELECT * FROM (VALUES ('EMEA', 'closed', 1200::BIGINT, 'first deal'), ('EMEA', 'closed', 450::BIGINT, NULL), "
    "('APAC', 'closed', 900::BIGINT, NULL), ('AMER', 'open', 300::BIGINT, NULL)) AS t(region, status, amount, notes)"
)


class ScriptedGeneratorClient:
    """Stands in for the generator's OpenAI client: returns scripted JSON
    responses in order and records every request."""

    def __init__(self, *responses):
        import json as _json
        from types import SimpleNamespace

        self.responses = [r if isinstance(r, str) else _json.dumps(r) for r in responses]
        self.requests: list[dict] = []

        async def create(**kwargs):
            self.requests.append(kwargs)
            content = self.responses.pop(0) if self.responses else '{"sql": "", "params": {}}'
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))
