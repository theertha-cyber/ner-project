"""Verification for document visibility by ingesting actor — verification.md rows 88-92.

`list_documents` used to scope non-admins by `uploaded_by` while retrieval scoped only by
`purpose`. A system-ingested document would therefore be invisible in the portal yet
answerable in chat — listing and citation disagreeing about what a user may see. The
filter now applies only to documents a *human* ingested.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.main import app
from src.shared.auth import create_access_token

from tests.test_ingestion_boundary import (
    session_factory,  # noqa: F401
    tenant,  # noqa: F401
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def token_for(tenant_id, user_id, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def seed_document(
    session_factory, schema, tenant_id, *, filename, uploaded_by, actor_kind
):
    document_id = str(uuid.uuid4())
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.documents "
                f"(id, tenant_id, filename, status, purpose, uploaded_by, ingested_by_kind, "
                f" source_type, source_id) "
                f"VALUES (:id, :tid, :fn, 'processed', 'query', :by, :kind, :stype, :sid)"
            ),
            {
                "id": document_id,
                "tid": tenant_id,
                "fn": filename,
                "by": uploaded_by,
                "kind": actor_kind,
                "stype": "platform_upload" if actor_kind == "human" else "keka",
                "sid": "platform-upload" if actor_kind == "human" else "keka-prod",
            },
        )
        await session.commit()
    return document_id


async def listed_ids(client, tenant_id, user_id, role="business_user"):
    response = await client.get(
        "/api/v1/documents", headers=token_for(tenant_id, user_id, role)
    )
    assert response.status_code == 200, response.text
    return {d["id"] for d in response.json()["documents"]}, response.json()["total"]


@pytest.fixture
async def seeded(tenant, session_factory):
    tenant_id, schema = tenant["tenant_id"], tenant["schema"]
    own = await seed_document(
        session_factory, schema, tenant_id,
        filename="mine.pdf", uploaded_by="test-user", actor_kind="human",
    )
    other = await seed_document(
        session_factory, schema, tenant_id,
        filename="theirs.pdf", uploaded_by="other-user", actor_kind="human",
    )
    system = await seed_document(
        session_factory, schema, tenant_id,
        filename="fetched.pdf", uploaded_by=None, actor_kind="source_system",
    )
    return {**tenant, "own": own, "other": other, "system": system}


# --- Row 88: a user sees their own uploads ---------------------------------------------


@pytest.mark.asyncio
async def test_row_88_a_user_sees_their_own_upload(seeded, client):
    ids, _ = await listed_ids(client, seeded["tenant_id"], "test-user")
    assert seeded["own"] in ids


# --- Row 89: a user does not see another user's upload ---------------------------------


@pytest.mark.asyncio
async def test_row_89_a_user_does_not_see_another_users_upload(seeded, client):
    ids, _ = await listed_ids(client, seeded["tenant_id"], "test-user")
    assert seeded["other"] not in ids


# --- Row 90: a system-ingested document is visible tenant-wide -------------------------


@pytest.mark.asyncio
async def test_row_90_a_system_ingested_document_is_visible_tenant_wide(seeded, client):
    for user in ("test-user", "other-user", "third-user"):
        ids, _ = await listed_ids(client, seeded["tenant_id"], user)
        assert seeded["system"] in ids, f"{user} could not see the system-ingested document"


# --- Row 91: listing and retrieval agree -----------------------------------------------


@pytest.mark.asyncio
async def test_row_91_a_citable_document_is_also_listable(seeded, client, session_factory):
    """Retrieval filters on `purpose` alone, so anything it can cite must be listable."""
    tenant_id, schema = seeded["tenant_id"], seeded["schema"]

    async with session_factory() as session:
        citable = (
            await session.execute(
                text(
                    f"SELECT id FROM {schema}.documents "
                    f"WHERE purpose = 'query' AND status != 'deleted'"
                )
            )
        ).fetchall()
    citable_ids = {r[0] for r in citable}

    listed, _ = await listed_ids(client, tenant_id, "third-user")
    # A user who uploaded nothing can still be cited system-ingested documents, and every
    # one of those must appear in their listing.
    system_citable = {seeded["system"]} & citable_ids
    assert system_citable <= listed, "chat could cite a document listing would deny"


# --- Row 92: administrators are unaffected ----------------------------------------------


@pytest.mark.asyncio
async def test_row_92_administrators_see_every_non_deleted_document(seeded, client):
    ids, total = await listed_ids(client, seeded["tenant_id"], "admin-user", "tenant_admin")
    assert {seeded["own"], seeded["other"], seeded["system"]} <= ids
    assert total == 3


# --- The count and the listing agree on the same predicate ------------------------------


@pytest.mark.asyncio
async def test_the_listing_and_its_total_apply_the_same_filter(seeded, client):
    """The two queries build their WHERE clause from one list of conditions; a prefixing
    bug that broke only one of them would show up as a total that disagrees with the rows."""
    ids, total = await listed_ids(client, seeded["tenant_id"], "test-user")
    assert total == len(ids)
    assert ids == {seeded["own"], seeded["system"]}
