"""Authorization for the content routes.

Covers the six authorization scenarios plus "The rule has one definition" and
"Authorization precedes delivery".

Serving a document's bytes is a new answer channel, and the uploader-scoping change that
preceded this one exists because a rule implemented twice drifts. So these tests pin two
separate things: that the outcomes are right, and that they are produced by the *shared*
predicate rather than a second copy living in the route.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.document_service.main import app
from src.shared.auth import create_access_token

pytestmark = [pytest.mark.verification, pytest.mark.integration]

OWNER = "recruiter-1"
OTHER = "recruiter-2"
CONV = "content-authz-conv"


def auth(tenant_id, user_id, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


class _FakeStore:
    """Stands in for object storage, and records whether it was read at all — which is
    how "Authorization precedes delivery" is checked."""

    def __init__(self):
        self.objects = {}
        self.opened = []

    def open(self, reference):
        self.opened.append(reference)
        return self.objects.get(reference)


@pytest_asyncio.fixture
async def seeded(tenant_schema, engine, monkeypatch):
    tenant_id, schema = tenant_schema
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    store = _FakeStore()
    ids = {}

    from src.document_service import content_resolution

    monkeypatch.setattr(content_resolution, "store_for", lambda mode: store)

    async with session_factory() as session:
        for column, ddl in (
            ("ingested_by_kind", "VARCHAR(32)"),
            ("conversation_id", "VARCHAR"),
            ("retention_mode", "VARCHAR(32) NOT NULL DEFAULT 'platform_blob'"),
            ("blob_path", "VARCHAR(500)"),
            ("content_type", "VARCHAR(255)"),
            ("source_type", "VARCHAR(64)"),
            ("source_id", "VARCHAR(128)"),
            ("external_id", "VARCHAR(512)"),
        ):
            await session.execute(
                text(f"ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS {column} {ddl}")
            )
        await session.execute(
            text(
                f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) "
                "VALUES (:c, :t, :u, 'T') ON CONFLICT (id) DO NOTHING"
            ),
            {"c": CONV, "t": tenant_id, "u": OWNER},
        )

        seeds = {
            "own": (OWNER, "human", None),
            "other": (OTHER, "human", None),
            "system": (None, "source_system", None),
            "attachment": (OWNER, "human", CONV),
        }
        for key, (uploader, kind, conv) in seeds.items():
            doc_id = f"doc-{key}-{uuid.uuid4()}"
            ids[key] = doc_id
            reference = f"tenants/{tenant_id}/documents/{doc_id}.pdf"
            store.objects[reference] = b"%PDF-1.4 " + key.encode()
            await session.execute(
                text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, status, purpose, uploaded_by,
                         ingested_by_kind, conversation_id, retention_mode,
                         blob_path, content_type)
                    VALUES (:id, :t, :fn, 'processed', 'query', :up, :kind, :conv,
                            'platform_blob', :ref, 'application/pdf')
                """),
                {"id": doc_id, "t": tenant_id, "fn": f"{key}.pdf", "up": uploader,
                 "kind": kind, "conv": conv, "ref": reference},
            )
        await session.commit()

    yield tenant_id, schema, ids, store


async def _get(path, tenant_id, user_id, role="business_user"):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=auth(tenant_id, user_id, role))


# --- The six authorization scenarios ------------------------------------------------


async def test_a_user_opens_a_document_they_may_see(seeded):
    tenant_id, _schema, ids, _store = seeded
    response = await _get(f"/api/v1/documents/{ids['own']}/content", tenant_id, OWNER)
    assert response.status_code == 200, response.text
    assert response.content == b"%PDF-1.4 own"


async def test_a_user_cannot_open_another_users_document(seeded):
    tenant_id, _schema, ids, store = seeded
    before = list(store.opened)

    response = await _get(f"/api/v1/documents/{ids['other']}/content", tenant_id, OWNER)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "DOCUMENT_NOT_PERMITTED"
    assert store.opened == before, "bytes were read before the refusal"


async def test_a_user_opens_their_own_attachment(seeded):
    """Every other route in the module excludes conversation-owned rows; the content
    routes must reach them, or a chat attachment chip could never open."""
    tenant_id, _schema, ids, _store = seeded
    response = await _get(f"/api/v1/documents/{ids['attachment']}/content", tenant_id, OWNER)
    assert response.status_code == 200, response.text
    assert response.content == b"%PDF-1.4 attachment"


async def test_another_user_cannot_open_someones_attachment(seeded):
    tenant_id, _schema, ids, _store = seeded
    response = await _get(f"/api/v1/documents/{ids['attachment']}/content", tenant_id, OTHER)
    assert response.status_code == 403


async def test_an_admin_cannot_open_someone_elses_attachment(seeded):
    """Deliberate: a tenant admin sees the library, but a colleague's private chat
    attachment is not library content."""
    tenant_id, _schema, ids, _store = seeded
    response = await _get(
        f"/api/v1/documents/{ids['attachment']}/content", tenant_id, "boss", "tenant_admin"
    )
    assert response.status_code == 403


async def test_another_tenants_document_is_not_reachable(seeded):
    """Credentials for a different tenant must not reach this tenant's document.

    Asserting only that the bytes are refused, not on a particular code: the request is
    rejected before the route by tenant context and the data-plane gate, which is a
    stronger outcome than the route's own not-found and is not this change's to
    specify."""
    tenant_id, _schema, ids, store = seeded
    before = list(store.opened)

    response = await _get(f"/api/v1/documents/{ids['own']}/content", "some-other-tenant", OWNER)

    assert response.status_code >= 400, response.text
    assert b"%PDF" not in response.content
    assert store.opened == before


async def test_source_system_documents_are_open_to_everyone(seeded):
    tenant_id, _schema, ids, _store = seeded
    for user in (OWNER, OTHER):
        response = await _get(f"/api/v1/documents/{ids['system']}/content", tenant_id, user)
        assert response.status_code == 200, f"hidden from {user}"


async def test_an_admin_opens_a_library_document_of_anothers(seeded):
    tenant_id, _schema, ids, _store = seeded
    response = await _get(
        f"/api/v1/documents/{ids['other']}/content", tenant_id, "boss", "tenant_admin"
    )
    assert response.status_code == 200


# --- Missing vs forbidden ------------------------------------------------------------


async def test_a_missing_document_is_not_confused_with_a_forbidden_one(seeded):
    tenant_id, _schema, ids, _store = seeded

    missing = await _get(f"/api/v1/documents/{uuid.uuid4()}/content", tenant_id, OWNER)
    forbidden = await _get(f"/api/v1/documents/{ids['other']}/content", tenant_id, OWNER)

    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "DOCUMENT_NOT_FOUND"
    assert forbidden.json()["detail"]["code"] == "DOCUMENT_NOT_PERMITTED"
    assert missing.json()["detail"]["code"] != forbidden.json()["detail"]["code"]


# --- The probe enforces the same rule ------------------------------------------------


async def test_the_probe_is_not_a_way_to_learn_a_document_exists(seeded):
    """The probe answers without touching the store, which makes it cheap — and would
    make it an attractive oracle if it were not authorized."""
    tenant_id, _schema, ids, _store = seeded
    response = await _get(f"/api/v1/documents/{ids['other']}/content/status", tenant_id, OWNER)
    assert response.status_code == 403


# --- "The rule has one definition" ---------------------------------------------------


def test_the_route_uses_the_shared_predicate():
    import inspect

    from src.document_service.api.v1 import documents as module

    source = inspect.getsource(module._load_document_for_content)
    assert "visibility_predicate(" in source, "the content route does not use the shared rule"
    assert "ingested_by_kind <>" not in source, "the content route restates the predicate"


# --- ADR-017: no control-plane reach -------------------------------------------------


async def test_authorization_reaches_no_control_plane_table(seeded):
    """`documents` may resolve to a tenant-owned database where `conversations` and the
    control-plane tables are simply absent (ADR-017). An authorization query that joined
    either would work in dev and fail there.

    Scoped to the authorization helper rather than the whole request: the data-plane gate
    legitimately reads `public.tenant_data_planes` on the platform database before any
    route runs, and folding that into this assertion would make it meaningless.
    """
    tenant_id, schema, ids, _store = seeded
    from src.document_service.api.v1 import documents as module

    statements = []

    class _RecordingSession:
        def __init__(self, inner):
            self._inner = inner

        async def execute(self, statement, *args, **kwargs):
            statements.append(str(statement))
            return await self._inner.execute(statement, *args, **kwargs)

    class _State:
        tenant_id = None
        role = "business_user"
        user_id = OWNER

    class _Request:
        state = _State()

    _State.tenant_id = tenant_id

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.shared.database import get_resolver

    engine = await get_resolver().resolve(tenant_id)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await module._load_document_for_content(
            _RecordingSession(session), _Request(), ids["attachment"]
        )

    joined = " ".join(statements).lower()
    assert statements, "no statements captured"
    assert "public." not in joined, f"authorization reached a control-plane table: {joined}"
    assert "conversations" not in joined, "authorization joined the conversations relation"
