import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from unittest.mock import patch

from src.document_service.main import app as doc_app
from src.chat_api.main import app as chat_app
from src.shared.auth import create_access_token
from tests.test_ingestion_boundary import FakeStore

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from tests.test_ingestion_boundary import (
    session_factory,
)


@pytest.fixture
async def doc_client():
    transport = ASGITransport(app=doc_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def chat_client():
    transport = ASGITransport(app=chat_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def token_for(tenant_id, user_id, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def seed_document_with_conversation(
    session_factory,
    schema,
    tenant_id,
    *,
    filename,
    uploaded_by,
    conversation_id=None,
    blob_path=None,
):
    document_id = str(uuid.uuid4())
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.documents "
                f"(id, tenant_id, filename, status, purpose, conversation_id, storage_uri, mime_type, file_size_bytes) "
                f"VALUES (:id, :tid, :fn, 'processed', 'query', :cid, :blob, 'application/pdf', 1000)"
            ),
            {
                "id": document_id,
                "tid": tenant_id,
                "fn": filename,
                "cid": conversation_id,
                "blob": blob_path,
            },
        )
        # Seed a text span
        await session.execute(
            text(
                f"INSERT INTO {schema}.document_text_spans (id, document_id, text) "
                f"VALUES (:span_id, :id, 'Derived span text for ' || :fn)"
            ),
            {"span_id": str(uuid.uuid4()), "id": document_id, "fn": filename},
        )
        await session.commit()
    return document_id


# --- 4.1 Test library listing excludes conversation-linked rows ---
@pytest.mark.asyncio
async def test_4_1_library_listing_excludes_chat_attachments(
    tenant_schema, session_factory, doc_client
):
    tenant_id, schema = tenant_schema

    # Seed non-chat upload
    non_chat_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="library_doc.pdf",
        uploaded_by="test-user",
    )

    # Seed conversation-linked upload
    conv_id = str(uuid.uuid4())
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Chat Title')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    chat_att_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="chat_attachment.pdf",
        uploaded_by="test-user",
        conversation_id=conv_id,
    )

    resp = await doc_client.get(
        "/api/v1/documents", headers=token_for(tenant_id, "test-user")
    )
    assert resp.status_code == 200
    data = resp.json()
    doc_ids = {d["id"] for d in data["documents"]}

    assert non_chat_id in doc_ids
    assert chat_att_id not in doc_ids
    assert data["total"] == 1


# --- 4.2 Test fetch-by-id of a conversation-linked row returns 404 ---
@pytest.mark.asyncio
async def test_4_2_library_fetch_by_id_of_chat_attachment_fails_404(
    tenant_schema, session_factory, doc_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Chat Title')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    chat_att_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="chat_attachment_2.pdf",
        uploaded_by="test-user",
        conversation_id=conv_id,
    )

    resp = await doc_client.get(
        f"/api/v1/documents/{chat_att_id}", headers=token_for(tenant_id, "test-user")
    )
    assert resp.status_code == 404


# --- 4.3 Test library text retrieval of a conversation-linked row returns 404 ---
@pytest.mark.asyncio
async def test_4_3_library_text_retrieval_of_chat_attachment_fails_404(
    tenant_schema, session_factory, doc_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Chat Title')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    chat_att_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="chat_attachment_3.pdf",
        uploaded_by="test-user",
        conversation_id=conv_id,
    )

    resp = await doc_client.get(
        f"/api/v1/documents/{chat_att_id}/text",
        headers=token_for(tenant_id, "test-user"),
    )
    assert resp.status_code == 404


# --- 4.4 Test library delete of a conversation-linked row returns 404 ---
@pytest.mark.asyncio
async def test_4_4_library_delete_of_chat_attachment_fails_404(
    tenant_schema, session_factory, doc_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Chat Title')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    chat_att_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="chat_attachment_4.pdf",
        uploaded_by="test-user",
        conversation_id=conv_id,
    )

    resp = await doc_client.delete(
        f"/api/v1/documents/{chat_att_id}",
        headers=token_for(tenant_id, "test-user"),
    )
    assert resp.status_code == 404

    # Assert row is unchanged and still exists
    async with session_factory() as session:
        res = await session.execute(
            text(f"SELECT status FROM {schema}.documents WHERE id = :id"),
            {"id": chat_att_id},
        )
        row = res.fetchone()
        assert row is not None
        assert row.status == "processed"


# --- 4.5 Test non-chat list/fetch/text/soft-delete behavior is unchanged ---
@pytest.mark.asyncio
async def test_4_5_non_chat_documents_behave_unchanged(
    tenant_schema, session_factory, doc_client
):
    tenant_id, schema = tenant_schema

    # Seed non-chat upload
    non_chat_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="library_doc_unchanged.pdf",
        uploaded_by="test-user",
    )

    # 1. Fetch
    get_resp = await doc_client.get(
        f"/api/v1/documents/{non_chat_id}", headers=token_for(tenant_id, "test-user")
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["document"]["filename"] == "library_doc_unchanged.pdf"

    # 2. Text
    text_resp = await doc_client.get(
        f"/api/v1/documents/{non_chat_id}/text",
        headers=token_for(tenant_id, "test-user"),
    )
    assert text_resp.status_code == 200
    assert "Derived span text" in text_resp.json()["text"]

    # 3. Soft-delete
    del_resp = await doc_client.delete(
        f"/api/v1/documents/{non_chat_id}", headers=token_for(tenant_id, "test-user")
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"


# --- 4.6 Test conversation deletion removes attachment document rows, blobs, and derived rows ---
@pytest.mark.asyncio
async def test_4_6_conversation_deletion_removes_attachments_and_trace(
    tenant_schema, session_factory, chat_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Deletable Chat')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    fake_store = FakeStore()
    blob_id = str(uuid.uuid4())
    blob_path = fake_store.put(
        tenant_id, blob_id, b"cap-5 hard delete verification", "my_attachment.pdf"
    )

    chat_att_id = await seed_document_with_conversation(
        session_factory,
        schema,
        tenant_id,
        filename="chat_attachment_deletable.pdf",
        uploaded_by="test-user",
        conversation_id=conv_id,
        blob_path=blob_path,
    )

    # Confirm it exists before delete
    assert fake_store.open(blob_path) is not None

    with patch(
        "src.document_service.services.hard_delete.get_durable_store",
        return_value=fake_store,
    ):
        # Delete conversation
        resp = await chat_client.delete(
            f"/api/v1/chat/conversations/{conv_id}",
            headers=token_for(tenant_id, "test-user"),
        )
        assert resp.status_code == 204

    # Verify conversation row is deleted
    async with session_factory() as session:
        conv_res = await session.execute(
            text(f"SELECT id FROM {schema}.conversations WHERE id = :cid"),
            {"cid": conv_id},
        )
        assert conv_res.fetchone() is None

        # Verify attachment document row is deleted
        doc_res = await session.execute(
            text(f"SELECT id FROM {schema}.documents WHERE id = :id"),
            {"id": chat_att_id},
        )
        assert doc_res.fetchone() is None

        # Verify derived spans are deleted
        span_res = await session.execute(
            text(
                f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :id"
            ),
            {"id": chat_att_id},
        )
        assert span_res.fetchone() is None

    # Verify blob is deleted from fake_store
    assert fake_store.open(blob_path) is None


# --- 4.7 Test retrying a conversation delete returns 404 ---
@pytest.mark.asyncio
async def test_4_7_retry_conversation_delete_is_safe_and_404s(
    tenant_schema, session_factory, chat_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'Deletable Chat')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    # First delete (succeeds with 204)
    resp = await chat_client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=token_for(tenant_id, "test-user"),
    )
    assert resp.status_code == 204

    # Second delete (fails with 404)
    resp2 = await chat_client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=token_for(tenant_id, "test-user"),
    )
    assert resp2.status_code == 404


# --- 4.8 Test deleting a conversation without attachments is unchanged ---
@pytest.mark.asyncio
async def test_4_8_delete_conversation_without_attachments_is_unchanged(
    tenant_schema, session_factory, chat_client
):
    tenant_id, schema = tenant_schema
    conv_id = str(uuid.uuid4())

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:cid, :tid, :uid, 'No Attachments Chat')"
            ),
            {"cid": conv_id, "tid": tenant_id, "uid": "test-user"},
        )
        await session.commit()

    resp = await chat_client.delete(
        f"/api/v1/chat/conversations/{conv_id}",
        headers=token_for(tenant_id, "test-user"),
    )
    assert resp.status_code == 204

    # Verify conversation row is deleted
    async with session_factory() as session:
        conv_res = await session.execute(
            text(f"SELECT id FROM {schema}.conversations WHERE id = :cid"),
            {"cid": conv_id},
        )
        assert conv_res.fetchone() is None
