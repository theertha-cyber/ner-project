"""Tabular file upload validation (tabular-file-ingestion spec)."""

import pytest
from sqlalchemy import text

from src.gateway.api.v1 import tabular_files as api
from src.shared.config import settings
from src.shared.tabular_files import store
from tests.tabular_support import (  # noqa: F401
    SALES_Q3_CSV,
    admin_headers,
    gateway_client,
    session_factory,
    tabular_env,
    tenants,
    upload,
    user_headers,
)

pytestmark = [pytest.mark.verification]


async def _rows(session_factory, tenant_id):
    async with session_factory() as session:
        files = (await session.execute(text(f"SELECT * FROM {store.FILES_TABLE} WHERE tenant_id = :t"),
                                       {"t": tenant_id})).fetchall()
        versions = (await session.execute(text(f"SELECT * FROM {store.VERSIONS_TABLE} WHERE tenant_id = :t"),
                                          {"t": tenant_id})).fetchall()
    return files, versions


async def test_csv_upload_is_accepted(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: CSV upload is accepted."""
    tenant_id = await tenants()
    body = SALES_Q3_CSV + "".join(f"EMEA,open,{i},padding {'x' * 200}\n" for i in range(9000))
    assert 1.5 * 1024 * 1024 < len(body) < 3 * 1024 * 1024  # ~2 MB
    response = await upload(gateway_client, tenant_id, "sales_q3.csv", body)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["display_name"] == "sales_q3.csv"
    assert payload["status"] == "profiling"
    assert payload["pending"]["version"] == 1

    files, versions = await _rows(session_factory, tenant_id)
    assert len(files) == 1 and len(versions) == 1
    assert versions[0].version == 1 and versions[0].status == "profiling"
    key = f"tenants/{tenant_id}/tabular/{payload['id']}/v1/original.csv"
    assert tabular_env.objects.objects[key] == body.encode()
    assert tabular_env.enqueued == [("profile", payload["id"], 1)]


@pytest.mark.parametrize("filename", ["budget.xlsm", "legacy.xls", "notes.txt", "noext"])
async def test_macro_enabled_workbook_is_rejected(gateway_client, tabular_env, tenants, session_factory, filename):
    """Scenario: Macro-enabled workbook is rejected (and every other non-allowed type)."""
    tenant_id = await tenants()
    response = await upload(gateway_client, tenant_id, filename, b"PK\x03\x04 not really a workbook")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert tabular_env.objects.objects == {}
    assert await _rows(session_factory, tenant_id) == ([], [])


async def test_oversized_file_is_rejected_while_streaming(gateway_client, tabular_env, tenants, session_factory,
                                                          monkeypatch):
    """Scenario: Oversized file is rejected while streaming. The cap is scaled to
    1 MB and the body to 1.5 MB so the proportions match 100 MB / 150 MB; the
    body is streamed without a Content-Length so only the chunk counter can stop
    it."""
    monkeypatch.setattr(settings, "tabular_max_file_bytes", 1024 * 1024)
    tenant_id = await tenants()
    consumed = {"bytes": 0}
    boundary = "tabularboundary"
    chunk = b"a,b\n" * 16384  # 64 KiB

    async def body():
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"big.csv\"\r\n"
                "Content-Type: text/csv\r\n\r\n").encode()
        yield head
        for _ in range(24):  # 1.5 MiB
            consumed["bytes"] += len(chunk)
            yield chunk
        yield f"\r\n--{boundary}--\r\n".encode()

    response = await gateway_client.post(
        "/api/v1/data-sources/files", content=body(),
        headers=admin_headers(tenant_id, **{"Content-Type": f"multipart/form-data; boundary={boundary}"}),
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert tabular_env.objects.objects == {}
    assert await _rows(session_factory, tenant_id) == ([], [])


async def test_declared_oversize_is_refused_before_reading(gateway_client, tabular_env, tenants, monkeypatch):
    monkeypatch.setattr(settings, "tabular_max_file_bytes", 1024)
    tenant_id = await tenants()
    response = await upload(gateway_client, tenant_id, "big.csv", "x" * 200_000)
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_per_tenant_file_cap(gateway_client, tabular_env, tenants, session_factory, monkeypatch):
    """Scenario: Per-tenant file cap (20 non-deleted files)."""
    tenant_id = await tenants()
    async with session_factory() as session:
        for i in range(20):
            await store.create_file(session, tenant_id, f"f{i}.csv")
        await session.commit()
    response = await upload(gateway_client, tenant_id, "one_more.csv", SALES_Q3_CSV)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FILE_LIMIT_REACHED"
    assert tabular_env.objects.objects == {}


async def test_deleted_files_do_not_count_toward_the_cap(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    async with session_factory() as session:
        ids = [await store.create_file(session, tenant_id, f"f{i}.csv") for i in range(20)]
        await store.mark_deleted(session, tenant_id, ids[0])
        await session.commit()
    response = await upload(gateway_client, tenant_id, "one_more.csv", SALES_Q3_CSV)
    assert response.status_code == 201


async def test_non_administrator_cannot_upload(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Non-administrator cannot upload."""
    tenant_id = await tenants()
    response = await upload(gateway_client, tenant_id, "sales_q3.csv", SALES_Q3_CSV, headers=user_headers(tenant_id))
    assert response.status_code == 403
    assert tabular_env.objects.objects == {}
    assert await _rows(session_factory, tenant_id) == ([], [])


async def test_kill_switch_refuses_upload(gateway_client, tabular_env, tenants, monkeypatch):
    monkeypatch.setattr(settings, "tabular_files_enabled", False)
    tenant_id = await tenants()
    response = await upload(gateway_client, tenant_id, "sales_q3.csv", SALES_Q3_CSV)
    assert response.json()["error"]["code"] == "TABULAR_FILES_DISABLED"
    listing = await gateway_client.get("/api/v1/data-sources/files", headers=admin_headers(tenant_id))
    assert listing.json()["enabled"] is False and listing.json()["files"] == []
    assert tabular_env.objects.objects == {}


async def test_tenant_comes_from_the_token_not_the_request(gateway_client, tabular_env, tenants, session_factory):
    tenant_a, tenant_b = await tenants(), await tenants()
    response = await gateway_client.post(
        "/api/v1/data-sources/files?tenant_id=" + tenant_b,
        files={"file": ("sales_q3.csv", SALES_Q3_CSV.encode(), "text/csv")},
        data={"tenant_id": tenant_b},
        headers=admin_headers(tenant_a),
    )
    assert response.status_code == 201
    assert all(k.startswith(f"tenants/{tenant_a}/tabular/") for k in tabular_env.objects.objects)
    assert await _rows(session_factory, tenant_b) == ([], [])
    assert api  # module import keeps the seam patched in tabular_env
