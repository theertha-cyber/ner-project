import pytest
from httpx import AsyncClient

from src.shared.auth import create_access_token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SYSTEM_ADMIN_TOKEN = create_access_token(
    tenant_id="00000000-0000-0000-0000-000000000000",
    user_id="admin-entity",
    role="system_admin",
)


_entity_counter = 0


@pytest.fixture
async def tenant_with_token(client: AsyncClient):
    global _entity_counter
    _entity_counter += 1
    slug = f"entity-config-{_entity_counter}"
    resp = await client.post("/api/v1/admin/tenants", json={
        "name": f"Entity Config Tenant {_entity_counter}", "slug": slug,
    }, headers=auth_header(SYSTEM_ADMIN_TOKEN))
    assert resp.status_code == 201
    tid = resp.json()["tenant"]["id"]

    token = create_access_token(tenant_id=tid, user_id=f"admin-{_entity_counter}", role="tenant_admin")
    return {"tid": tid, "token": token, "slug": slug}


# --- Scenario 14: Create entity type with version: 1 ---
@pytest.mark.asyncio
async def test_scenario_14_create_entity_type_v1(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Organization",
            "description": "Company or organization names",
            "base_label_mapping": {"ORG": ["company_name", "organization_name"]},
            "required_flag": False,
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    entity = resp.json()["entity_type"]
    assert entity["version"] == 1, f"Expected version 1, got {entity['version']}"


# --- Scenario 15: Update entity type increments version ---
@pytest.mark.asyncio
async def test_scenario_15_update_increments_version(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={"name": "Person", "base_label_mapping": {"PER": ["person_name"]}},
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201
    entity_id = resp.json()["entity_type"]["id"]

    update_resp = await client.put(
        f"/api/v1/entity-types/{entity_id}",
        json={"description": "Updated description"},
        headers=auth_header(tenant["token"]),
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["entity_type"]
    assert updated["version"] == 2, f"Expected version 2, got {updated['version']}"


# --- Scenario 16: Valid base_label_mapping accepted ---
@pytest.mark.asyncio
async def test_scenario_16_valid_label_mapping(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Location Entity",
            "base_label_mapping": {
                "LOC": ["city_name", "country_name"],
                "ORG": ["vendor_name"],
            },
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    entity = resp.json()["entity_type"]
    assert "LOC" in entity["base_label_mapping"]
    assert "ORG" in entity["base_label_mapping"]


# --- Scenario 17: Invalid label returns 422 ---
@pytest.mark.asyncio
async def test_scenario_17_invalid_label_422(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.post(
        "/api/v1/entity-types",
        json={
            "name": "Bad Entity",
            "base_label_mapping": {"INVALID_LABEL": ["something"]},
        },
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"


# --- Scenario 18: List all entity types with is_active ---
@pytest.mark.asyncio
async def test_scenario_18_list_all_entity_types(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    for name, label in [("Type A", "PER"), ("Type B", "ORG"), ("Type C", "LOC"),
                          ("Type D", "MISC"), ("Type E", "PER")]:
        await client.post(
            "/api/v1/entity-types",
            json={"name": name, "base_label_mapping": {label: ["test"]}},
            headers=auth_header(tenant["token"]),
        )

    resp = await client.get(
        "/api/v1/entity-types",
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 200
    types = resp.json()["entity_types"]
    assert len(types) >= 5
    for t in types:
        assert "is_active" in t


# --- Scenario 19: Filter active only ---
@pytest.mark.asyncio
async def test_scenario_19_filter_active(client: AsyncClient, tenant_with_token):
    tenant = tenant_with_token
    resp = await client.get(
        "/api/v1/entity-types?is_active=true",
        headers=auth_header(tenant["token"]),
    )
    assert resp.status_code == 200
    types = resp.json()["entity_types"]
    for t in types:
        assert t["is_active"] is True


# --- llm-assisted-prelabeling: entity-config QA pairs (verification.md rows 17-20) ---
#
# These use their own fixture rather than `tenant_with_token` above: that fixture provisions
# through `POST /api/v1/admin/tenants`, which returns 422 on this branch as it does on `main`,
# and these assertions are about the entity-type API rather than about tenant provisioning.
# The route is the real one the gateway mounts, `/api/v1/tenants/{slug}/entity-types`.

import uuid  # noqa: E402

from sqlalchemy import text  # noqa: E402


@pytest.fixture
async def qa_tenant(client: AsyncClient, engine):
    tid = f"qa-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) "
                "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid},
        )
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    token = create_access_token(tenant_id=tid, user_id="admin", role="tenant_admin")
    yield {
        "id": tid,
        "headers": auth_header(token),
        "url": f"/api/v1/tenants/{tid}/entity-types",
    }

    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid}
        )
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest.mark.asyncio
async def test_create_entity_type(client: AsyncClient, qa_tenant):
    """verification.md row 17."""
    resp = await client.post(
        qa_tenant["url"],
        json={
            "name": "customer_name",
            "description": "Full name of a customer",
            "examples": ["John Smith", "Acme Corp"],
            "validation_rule": None,
            "required_flag": True,
        },
        headers=qa_tenant["headers"],
    )
    assert resp.status_code == 201, resp.text
    entity = resp.json()
    assert entity["name"] == "customer_name"
    assert entity["version"] == 1
    assert entity["is_active"] is True


@pytest.mark.asyncio
async def test_update_entity_type(client: AsyncClient, qa_tenant):
    """verification.md row 18."""
    created = await client.post(
        qa_tenant["url"],
        json={"name": "customer_name", "description": "Full name of a customer"},
        headers=qa_tenant["headers"],
    )
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1

    resp = await client.put(
        f"{qa_tenant['url']}/customer_name",
        json={"description": "Updated description"},
        headers=qa_tenant["headers"],
    )
    assert resp.status_code == 200, resp.text
    entity = resp.json()
    assert entity["version"] == 2
    assert entity["description"] == "Updated description"


@pytest.mark.asyncio
async def test_add_qa_examples_increments_version(client: AsyncClient, qa_tenant):
    """verification.md row 19.

    QA pairs go through the same versioned update path as every other field — nothing about
    them being LLM prompt context exempts them from the catalog's change tracking, and the
    pre-labeling cache keys on the configuration precisely so this edit invalidates it."""
    created = await client.post(
        qa_tenant["url"],
        json={"name": "years_experience", "description": "Years of professional experience"},
        headers=qa_tenant["headers"],
    )
    assert created.status_code == 201, created.text
    assert created.json()["qa_examples"] == []

    pair = {
        "question": "How many years of experience does X have?",
        "answer": "X has 10 years of experience",
    }
    resp = await client.put(
        f"{qa_tenant['url']}/years_experience",
        json={"qa_examples": [pair]},
        headers=qa_tenant["headers"],
    )
    assert resp.status_code == 200, resp.text
    entity = resp.json()
    assert entity["qa_examples"] == [pair]
    assert entity["version"] == 2


@pytest.mark.asyncio
async def test_entity_type_without_qa_examples_is_valid(client: AsyncClient, qa_tenant):
    """verification.md row 20.

    The whole point of Extraction Scope: an entity type with no QA pairs is a first-class
    entity type, not a half-configured one."""
    resp = await client.post(
        qa_tenant["url"],
        json={
            "name": "person_name",
            "description": "A person's full name",
            "examples": ["John Smith"],
        },
        headers=qa_tenant["headers"],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["qa_examples"] in ([], None)


@pytest.mark.asyncio
async def test_malformed_qa_example_is_rejected(client: AsyncClient, qa_tenant):
    """A pair missing its answer never reaches prompt construction.

    Not a spec scenario — it is the guard behind row 19's contract, and without it a malformed
    pair renders into the prompt as `None`."""
    resp = await client.post(
        qa_tenant["url"],
        json={"name": "broken_type", "qa_examples": [{"question": "Where?"}]},
        headers=qa_tenant["headers"],
    )
    assert resp.status_code == 422, resp.text
