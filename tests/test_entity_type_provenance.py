"""Entity type provenance — assigned at creation, immutable, server-controlled.

Exercises `EntityService` directly against a real database (the HTTP entity-config tests
need a live-provisioned tenant, which this container fixture set does not build).
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.gateway.services.entity_service import EntityService
from src.shared.config import settings
from tests.seed_bootstrap_support import drop_test_schemas, make_tenant


@pytest.fixture
async def engine():
    eng = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    await drop_test_schemas(engine)
    async with engine.connect() as conn:
        try:
            await conn.execute(
                text("DELETE FROM public.entity_definitions WHERE name LIKE 'prov\\_%'")
            )
        except Exception:  # noqa: BLE001 - table may not exist between test files
            pass


async def _session():
    factory = async_sessionmaker(
        create_async_engine(settings.database_url, poolclass=NullPool), expire_on_commit=False
    )
    return factory()


@pytest.mark.asyncio
async def test_manual_create_provenance(engine):
    tenant = await make_tenant(engine, entity_types=())
    async with await _session() as session:
        created = await EntityService(session).create_entity_type(
            tenant["tid"], {"name": "prov_manual", "description": "x"}
        )
    assert created["provenance"] == "manual"
    assert created["provenance_ref"] is None


@pytest.mark.asyncio
async def test_client_supplied_provenance_is_ignored_on_plain_create(engine):
    """The create API's request model has no `provenance` field, so a value in the payload
    dict that reaches the service via an unexpected path still defaults to manual unless it
    is one of the recognised server-set values — and even 'suggested' here would only stick
    if a trusted caller set it. This asserts the service does not blindly trust an arbitrary
    string."""
    tenant = await make_tenant(engine, entity_types=())
    async with await _session() as session:
        created = await EntityService(session).create_entity_type(
            tenant["tid"], {"name": "prov_bogus", "provenance": "totally-made-up"}
        )
    assert created["provenance"] == "manual"


@pytest.mark.asyncio
async def test_suggested_and_imported_provenance_persist(engine):
    tenant = await make_tenant(engine, entity_types=())
    async with await _session() as session:
        svc = EntityService(session)
        s = await svc.create_entity_type(
            tenant["tid"], {"name": "prov_sug", "provenance": "suggested", "provenance_ref": "schema v3"}
        )
        i = await svc.create_entity_type(
            tenant["tid"], {"name": "prov_imp", "provenance": "imported", "provenance_ref": "gold.jsonl"}
        )
    assert (s["provenance"], s["provenance_ref"]) == ("suggested", "schema v3")
    assert (i["provenance"], i["provenance_ref"]) == ("imported", "gold.jsonl")


@pytest.mark.asyncio
async def test_provenance_immutable_on_update(engine):
    tenant = await make_tenant(engine, entity_types=())
    async with await _session() as session:
        svc = EntityService(session)
        await svc.create_entity_type(
            tenant["tid"], {"name": "prov_upd", "provenance": "suggested"}
        )
        updated = await svc.update_entity_type(
            tenant["tid"], "prov_upd", {"description": "changed"}
        )
    assert updated["provenance"] == "suggested"
    assert updated["version"] == 2
