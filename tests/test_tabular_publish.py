"""Publish gate and Parquet publication (tabular-file-ingestion spec)."""

import pytest

from src.shared.tabular_files import store
from src.shared.tabular_files.capability import resolve_tabular_capability
from tests.tabular_support import (  # noqa: F401
    admin_headers,
    gateway_client,
    parquet_types,
    publish,
    publish_ready,
    review,
    session_factory,
    tabular_env,
    tenants,
    upload_and_profile,
)

pytestmark = [pytest.mark.verification]


async def _version(session_factory, tenant_id, file_id, version=1):
    async with session_factory() as session:
        return await store.get_version(session, tenant_id, file_id, version)


async def test_unresolved_date_format_blocks_publish(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Unresolved date format blocks publish."""
    tenant_id = await tenants()
    content = "deal,closed_on\nA,03/04/2026\nB,05/06/2026\nC,11/12/2026\n"
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id,
                                       filename="deals.csv", content=content)
    await review(gateway_client, tenant_id, file_id, 1, {"table": {"description": "Deals"}})
    response = await publish(gateway_client, tenant_id, file_id, 1)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "DATE_FORMAT_REQUIRED"
    assert "closed_on" in error["message"]
    assert (await _version(session_factory, tenant_id, file_id)).status == "needs_review"
    assert tabular_env.enqueued == []


async def test_missing_table_description_blocks_publish(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Missing table description blocks publish."""
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    response = await publish(gateway_client, tenant_id, file_id, 1)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DESCRIPTION_REQUIRED"
    assert (await _version(session_factory, tenant_id, file_id)).status == "needs_review"


async def test_duplicate_identifiers_block_publish(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    response = await review(gateway_client, tenant_id, file_id, 1, {
        "table": {"description": "Sales"}, "columns": [{"index": 1, "identifier": "region"}],
    })
    assert response.json()["blockers"] == [{"code": "DUPLICATE_IDENTIFIER", "column": "region"}]
    assert (await publish(gateway_client, tenant_id, file_id, 1)).json()["error"]["code"] == "DUPLICATE_IDENTIFIER"


async def test_successful_publish(gateway_client, tabular_env, tenants, session_factory, tmp_path):
    """Scenario: Successful publish."""
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    await review(gateway_client, tenant_id, file_id, 1, {"columns": [{"index": 3, "excluded": True}]})
    await publish_ready(gateway_client, tabular_env, session_factory, tenant_id, file_id)

    key = f"tenants/{tenant_id}/tabular/{file_id}/v1/data.parquet"
    assert tabular_env.objects.exists(key)
    assert parquet_types(tabular_env.objects, key, tmp_path) == {
        "region": "VARCHAR", "status": "VARCHAR", "amount": "BIGINT",
    }
    version = await _version(session_factory, tenant_id, file_id)
    assert version.status == "ready"
    assert [c["name"] for c in version.contract["columns"]] == ["region", "status", "amount"]
    assert version.contract["relation"] == "sales_q3"
    assert version.contract["source_file"] == "sales_q3.csv"
    async with session_factory() as session:
        assert (await store.get_file(session, tenant_id, file_id)).status == "ready"
        capability = await resolve_tabular_capability(session, tenant_id)
    assert capability["executable"] is True
    assert capability["files"][0]["version"] == 1


async def test_publish_is_idempotent(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    await review(gateway_client, tenant_id, file_id, 1, {"table": {"description": "Sales"}})
    first = await publish(gateway_client, tenant_id, file_id, 1, key="same-key")
    second = await publish(gateway_client, tenant_id, file_id, 1, key="same-key")
    assert first.status_code == second.status_code == 202
    assert second.headers.get("Idempotent-Replay") == "true"
    assert [e[0] for e in tabular_env.enqueued] == ["publish"]
    missing = await gateway_client.post(f"/api/v1/data-sources/files/{file_id}/versions/1/publish",
                                        headers=admin_headers(tenant_id))
    assert missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


async def test_file_is_not_offered_to_chat_before_publish(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    async with session_factory() as session:
        assert (await resolve_tabular_capability(session, tenant_id))["executable"] is False
