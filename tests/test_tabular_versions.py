"""Versioned replace and file deletion (tabular-file-ingestion spec)."""

import pytest

from src.shared.tabular_files.capability import resolve_tabular_capability
from tests.tabular_support import (  # noqa: F401
    admin_headers,
    drain,
    gateway_client,
    publish_ready,
    session_factory,
    tabular_env,
    tenants,
    upload,
    upload_and_profile,
)

pytestmark = [pytest.mark.verification]

V1 = "amount,region\n100,EMEA\n200,APAC\n"
V2 = "amount,country\n1.5,FR\n2.25,JP\n"


async def _served(session_factory, tenant_id):
    async with session_factory() as session:
        capability = await resolve_tabular_capability(session, tenant_id)
    return {f["contract"]["relation"]: f["version"] for f in capability.get("files", [])}


async def _with_v2_in_review(client, env, session_factory, tenant_id):
    file_id = await upload_and_profile(client, env, session_factory, tenant_id, filename="sales_q3.csv", content=V1)
    await publish_ready(client, env, session_factory, tenant_id, file_id)
    response = await upload(client, tenant_id, "sales_q3.csv", V2,
                            path=f"/api/v1/data-sources/files/{file_id}/versions")
    assert response.status_code == 201, response.text
    assert response.json()["pending"]["version"] == 2
    await drain(env, session_factory)
    return file_id


async def test_old_version_stays_live_during_review(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Old version stays live during review."""
    tenant_id = await tenants()
    file_id = await _with_v2_in_review(gateway_client, tabular_env, session_factory, tenant_id)
    listing = (await gateway_client.get("/api/v1/data-sources/files", headers=admin_headers(tenant_id))).json()
    [entry] = listing["files"]
    assert entry["id"] == file_id
    assert entry["served_version"] == 1 and entry["status"] == "ready"
    assert entry["pending"] == {"version": 2, "status": "needs_review", "failure_reason": None, "sheet": None}
    assert await _served(session_factory, tenant_id) == {"sales_q3": 1}


async def test_schema_diff_is_shown(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Schema diff is shown."""
    tenant_id = await tenants()
    file_id = await _with_v2_in_review(gateway_client, tabular_env, session_factory, tenant_id)
    body = (await gateway_client.get(f"/api/v1/data-sources/files/{file_id}/versions/2/profile",
                                     headers=admin_headers(tenant_id))).json()
    assert body["schema_diff"] == {
        "added": ["country"], "removed": ["region"],
        "retyped": [{"column": "amount", "from": "bigint", "to": "numeric"}], "renamed": [],
    }


async def test_publishing_switches_the_served_version(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Publishing switches the served version."""
    tenant_id = await tenants()
    file_id = await _with_v2_in_review(gateway_client, tabular_env, session_factory, tenant_id)
    await publish_ready(gateway_client, tabular_env, session_factory, tenant_id, file_id, version=2)
    assert await _served(session_factory, tenant_id) == {"sales_q3": 2}
    assert tabular_env.objects.list_keys(f"tenants/{tenant_id}/tabular/{file_id}/v1/") == []
    assert tabular_env.objects.list_keys(f"tenants/{tenant_id}/tabular/{file_id}/v2/") == [
        f"tenants/{tenant_id}/tabular/{file_id}/v2/data.parquet",
        f"tenants/{tenant_id}/tabular/{file_id}/v2/original.csv",
    ]


async def test_deleted_file_leaves_chat_immediately(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Deleted file leaves chat immediately."""
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    await publish_ready(gateway_client, tabular_env, session_factory, tenant_id, file_id)
    assert await _served(session_factory, tenant_id) == {"sales_q3": 1}
    response = await gateway_client.delete(f"/api/v1/data-sources/files/{file_id}", headers=admin_headers(tenant_id))
    assert response.status_code == 200
    assert await _served(session_factory, tenant_id) == {}
    assert tabular_env.objects.list_keys(f"tenants/{tenant_id}/tabular/{file_id}/") == []
    listing = (await gateway_client.get("/api/v1/data-sources/files", headers=admin_headers(tenant_id))).json()
    assert listing["files"] == []


async def test_other_tenants_cannot_touch_a_file(gateway_client, tabular_env, tenants, session_factory):
    owner, other = await tenants(), await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, owner)
    for method, path in [("get", f"/{file_id}/versions/1/profile"), ("delete", f"/{file_id}")]:
        response = await getattr(gateway_client, method)(f"/api/v1/data-sources/files{path}",
                                                         headers=admin_headers(other))
        assert response.status_code == 404
    assert tabular_env.objects.list_keys(f"tenants/{owner}/")
