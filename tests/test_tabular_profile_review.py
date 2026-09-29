"""Draft profile and administrator review (tabular-file-ingestion spec)."""

import pytest

from tests.tabular_support import (  # noqa: F401
    SALES_Q3_CSV,
    admin_headers,
    gateway_client,
    review,
    session_factory,
    tabular_env,
    tenants,
    upload_and_profile,
)

pytestmark = [pytest.mark.verification]


async def _profile(client, tenant_id, file_id, version=1):
    response = await client.get(f"/api/v1/data-sources/files/{file_id}/versions/{version}/profile",
                                headers=admin_headers(tenant_id))
    assert response.status_code == 200, response.text
    return response.json()


def _column(body, identifier):
    return next(c for c in body["review"]["columns"] if c["identifier"] == identifier)


async def test_profile_is_ready_for_review(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Profile is ready for review."""
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    body = await _profile(gateway_client, tenant_id, file_id)
    assert body["status"] == "needs_review"
    assert body["file"]["status"] == "needs_review"
    columns = {c["identifier"]: c for c in body["profile"]["columns"]}
    assert set(columns) == {"region", "status", "amount", "notes"}
    for column in columns.values():
        assert {"identifier", "label", "type", "null_count", "distinct_count"} <= set(column)
    assert columns["amount"]["type"] == "bigint"
    assert columns["region"]["label"] == "region"
    assert {v["value"] for v in columns["region"]["top_values"]} == {"EMEA", "APAC", "AMER"}
    assert columns["notes"]["null_count"] == 3
    assert body["profile"]["relation"] == "sales_q3"
    assert body["profile"]["row_count"] == 4


async def test_forcing_a_stricter_type_reports_rejects(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Forcing a stricter type reports rejects."""
    tenant_id = await tenants()
    lines = ["id,qty"] + [f"{i},{i}" for i in range(1, 10_001)]
    bad = list(range(100, 10_000, 1000))
    for position in bad:
        lines[position + 1] = f"{position + 1},abc"
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id,
                                       filename="stock.csv", content="\n".join(lines) + "\n")
    before = await _profile(gateway_client, tenant_id, file_id)
    assert _column(before, "qty")["type"] == "text"

    index = _column(before, "qty")["index"]
    response = await review(gateway_client, tenant_id, file_id, 1, {"columns": [{"index": index, "type": "bigint"}]})
    assert response.status_code == 200, response.text
    report = response.json()["load_report"]
    assert report["rows_read"] == 10_000
    assert report["rows_rejected"] == 10
    assert report["rows_to_load"] == 9_990
    assert [r["row"] for r in report["rejects"]] == [p + 2 for p in bad]
    assert {r["reason"] for r in report["rejects"]} == {"cast_failed"}


async def test_excluded_column_disappears_from_preview(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Excluded column disappears from preview."""
    tenant_id = await tenants()
    content = "name,salary,team\nAna,100,red\nBo,200,blue\n"
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id,
                                       filename="staff.csv", content=content)
    before = await _profile(gateway_client, tenant_id, file_id)
    assert "salary" in before["load_report"]["preview"][0]
    index = _column(before, "salary")["index"]
    response = await review(gateway_client, tenant_id, file_id, 1, {"columns": [{"index": index, "excluded": True}]})
    assert response.status_code == 200
    preview = response.json()["load_report"]["preview"]
    assert len(preview) == 2
    assert all("salary" not in row for row in preview)
    assert preview[0] == {"name": "Ana", "team": "red"}


async def test_invalid_identifier_edit_is_refused(gateway_client, tabular_env, tenants, session_factory):
    """Scenario: Invalid identifier edit is refused."""
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    before = await _profile(gateway_client, tenant_id, file_id)
    index = _column(before, "region")["index"]
    response = await review(gateway_client, tenant_id, file_id, 1,
                            {"columns": [{"index": index, "identifier": "drop table x"}]})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["field"] == "columns[0].identifier"
    assert "drop table x" not in error["message"]
    after = await _profile(gateway_client, tenant_id, file_id)
    assert _column(after, "region")["identifier"] == "region"


async def test_preview_is_typed_and_capped(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    content = "n,flag\n" + "".join(f"{i},yes\n" for i in range(50))
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id,
                                       filename="n.csv", content=content)
    body = await _profile(gateway_client, tenant_id, file_id)
    preview = body["load_report"]["preview"]
    assert len(preview) == 20
    assert preview[0] == {"n": 0, "flag": True}


async def test_value_hints_approve_and_null_tokens(gateway_client, tabular_env, tenants, session_factory):
    tenant_id = await tenants()
    file_id = await upload_and_profile(gateway_client, tabular_env, session_factory, tenant_id)
    before = await _profile(gateway_client, tenant_id, file_id)
    region = _column(before, "region")
    response = await review(gateway_client, tenant_id, file_id, 1, {
        "table": {"null_tokens": ["", "n/a", "EMEA"]},
        "columns": [{"index": region["index"], "value_hints": [{"value": "EMEA", "approved": True}]}],
    })
    assert response.status_code == 200
    body = response.json()
    assert {"value": "EMEA", "approved": True} in _column(body, "region")["value_hints"]
    assert [row["region"] for row in body["load_report"]["preview"]] == [None, None, "APAC", "AMER"]
    bad = await review(gateway_client, tenant_id, file_id, 1, {
        "columns": [{"index": region["index"], "value_hints": [{"value": "invented", "approved": True}]}],
    })
    assert bad.status_code == 422
