"""Platform object storage layout (tabular-file-ingestion spec, ADR-019)."""

import uuid

import pytest
from sqlalchemy import text

from src.shared.tabular_files import storage, store
from tests.tabular_support import (  # noqa: F401
    SALES_Q3_CSV,
    gateway_client,
    publish_ready,
    session_factory,
    tabular_env,
    tenants,
    upload,
    upload_and_profile,
)

pytestmark = [pytest.mark.verification]


async def test_tenant_owned_tenant_uploads_a_file(gateway_client, tabular_env, tenants, session_factory, monkeypatch):
    """Scenario: Tenant-owned tenant uploads a file. The tenant's resolved data
    plane is never consulted: the metadata goes to `public` through the
    gateway's platform session and the object to platform MinIO."""
    from src.shared import database

    tenant_id = await tenants(mode="tenant_owned")

    class NoResolve:
        async def resolve(self, tid):
            raise AssertionError("tenant store must not be touched by a tabular upload")

    monkeypatch.setattr(database, "get_resolver", lambda: NoResolve())
    response = await upload(gateway_client, tenant_id, "sales_q3.csv", SALES_Q3_CSV)
    assert response.status_code == 201, response.text
    file_id = response.json()["id"]
    assert list(tabular_env.objects.objects) == [f"tenants/{tenant_id}/tabular/{file_id}/v1/original.csv"]
    async with session_factory() as session:
        row = (await session.execute(text(f"SELECT tenant_id FROM {store.FILES_TABLE} WHERE id = :id"),
                                     {"id": file_id})).fetchone()
    assert row.tenant_id == tenant_id


async def test_object_keys_never_cross_tenants(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Object keys never cross tenants."""
    tenant_a, tenant_b = await tenants(), await tenants()
    for tenant_id in (tenant_a, tenant_b):
        file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
        await publish_ready(gateway_client, tabular_env, session_factory, tenant_id, file_id)
    a_keys = tabular_env.objects.list_keys(f"tenants/{tenant_a}/")
    b_keys = tabular_env.objects.list_keys(f"tenants/{tenant_b}/")
    assert len(a_keys) == 2 and len(b_keys) == 2  # original + data.parquet each
    assert all(k.startswith(f"tenants/{tenant_a}/tabular/") for k in a_keys)
    assert not any(k.startswith(f"tenants/{tenant_b}/") for k in a_keys)
    assert set(a_keys) | set(b_keys) == set(tabular_env.objects.objects)


@pytest.mark.parametrize("tenant_id,file_id,version", [
    ("../etc", str(uuid.uuid4()), 1),
    ("t1", "not-a-uuid/../../x", 1),
    ("t1", str(uuid.uuid4()), 0),
    ("t1", str(uuid.uuid4()), "1"),
])
def test_keys_are_built_from_server_ids_only(tenant_id, file_id, version):
    with pytest.raises(ValueError):
        storage.version_prefix(tenant_id, file_id, version)


def test_key_shapes():
    fid = str(uuid.uuid4())
    assert storage.original_key("t1", fid, 2, "xlsx") == f"tenants/t1/tabular/{fid}/v2/original.xlsx"
    assert storage.parquet_key("t1", fid, 2) == f"tenants/t1/tabular/{fid}/v2/data.parquet"
    with pytest.raises(ValueError):
        storage.original_key("t1", fid, 1, "xlsm")
