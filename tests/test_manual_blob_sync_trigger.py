"""Verification for the manual Azure Blob sync trigger.

Maps to `openspec/changes/manual-blob-sync-trigger/verification.md` Section 1
rows 2, 4, and 6-11. Rows 1, 3, and 5 are regression runs of
`tests/test_azure_blob_source_sync.py`.

The gateway's broker seam (`_enqueue_blob_sync`) is replaced with a recorder so
each test asserts exactly what would have been enqueued: the identity-only
`(tenant, connection, trigger)` payload. Everything else -- auth, tenant
binding, lifecycle gating, idempotency -- runs against the real test database
through the gateway app.

Teardown removes exactly what each test created (via `tracked_tenants`, plus the
one tenant schema the recent-sync test creates by exact name).
"""

from datetime import datetime

import pytest
from sqlalchemy import text

from src.document_service.blob_sync import ledger
from src.document_service.blob_sync import sync as blob_sync
from src.document_service.blob_sync.scheduler import evaluate_connection
from src.gateway.api.v1 import data_sources as ds_api
from src.shared.tenant_schema import schema_for_tenant

from tests.test_ingestion_boundary import session_factory  # noqa: F401
from tests.test_tenant_data_source_control_plane import (  # noqa: F401
    ACCOUNT,
    CONTAINER,
    EVIDENCE,
    FAKE_CONN_STR,
    _env_refs,
    action_headers,
    admin_headers,
    assert_no_secrets,
    assert_safe_envelope,
    client,
    create_draft,
    fake_testers,
    tracked_tenants,
    user_headers,
    validated_draft,
)

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

SAFE_TRIGGER_KEYS = {"connection_id", "trigger", "outcome", "enqueued_at"}


@pytest.fixture
def enqueued(monkeypatch):
    """Record broker enqueues instead of sending them."""
    calls = []

    def _record(tenant_id, connection_id, trigger):
        calls.append((tenant_id, connection_id, trigger))

    monkeypatch.setattr(ds_api, "_enqueue_blob_sync", _record)
    return calls


async def active_connection(client, tid, provider="azure_blob", key="k-m"):
    cid = await validated_draft(client, tid, provider=provider, key=key)
    resp = await client.post(
        "/api/v1/data-sources/%s/activate" % cid,
        json={"activation_evidence": EVIDENCE},
        headers=action_headers(tid, "%s-a" % key),
    )
    assert resp.status_code == 200, resp.text
    return cid


async def trigger_sync(client, cid, headers, body=None):
    return await client.post(
        "/api/v1/data-sources/%s/sync" % cid,
        json={} if body is None else body,
        headers=headers,
    )


# --- Row 2: manual trigger bypasses the scheduler cadence ------------------------------


async def test_manual_trigger_enqueues_despite_recent_sync(
    client, tracked_tenants, session_factory, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-recent")
    schema = schema_for_tenant(tid)
    try:
        async with session_factory() as session:
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await session.commit()
            await ledger.ensure_sync_tables(session, schema)
            await session.execute(
                text(
                    f"INSERT INTO {schema}.azure_blob_sync_runs "
                    "(id, tenant_id, connection_id, trigger, outcome, reason, "
                    "started_at, completed_at) "
                    "VALUES ('recent', :tid, :cid, 'scheduled', 'succeeded', 'none', "
                    "NOW() - INTERVAL '2 minutes', NOW() - INTERVAL '1 minute')"
                ),
                {"tid": tid, "cid": cid},
            )
            await session.commit()
            last = await ledger.last_successful_run_at(session, schema, cid)

        # The scheduler would wait: the last success is well inside one cadence.
        assert evaluate_connection(active=True, last_success_at=last).decision == "not_due"

        resp = await trigger_sync(client, cid, action_headers(tid, "k-recent-sync"))
        assert resp.status_code == 202, resp.text
        assert enqueued == [(tid, cid, blob_sync.TRIGGER_MANUAL)]
    finally:
        async with session_factory() as session:
            await session.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await session.commit()


# --- Row 4: inactive connections enqueue nothing ---------------------------------------


@pytest.mark.parametrize("state", ["draft", "paused"])
async def test_inactive_connection_enqueues_nothing(
    client, tracked_tenants, fake_testers, enqueued, state
):
    tid = await tracked_tenants()
    if state == "paused":
        cid = await active_connection(client, tid, key="k-inactive")
        paused = await client.post(
            "/api/v1/data-sources/%s/pause" % cid, json={},
            headers=action_headers(tid, "k-inactive-p"),
        )
        assert paused.status_code == 200, paused.text
    else:
        cid = (await create_draft(client, tid, key="k-inactive")).json()["id"]

    # Scheduler side: an inactive connection is never due and carries no trigger.
    decision = evaluate_connection(active=False, last_success_at=None)
    assert decision.decision == "inactive"

    # Manual side: rejected before the broker is touched.
    resp = await trigger_sync(client, cid, action_headers(tid, "k-inactive-sync"))
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "INACTIVE_CONNECTION"
    assert enqueued == []


# --- Row 6: administrator triggers a manual sync ---------------------------------------


async def test_manual_sync_enqueues_manual_trigger(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-ok")

    resp = await trigger_sync(client, cid, action_headers(tid, "k-ok-sync"))

    assert resp.status_code == 202, resp.text
    assert "Idempotent-Replay" not in resp.headers
    body = resp.json()
    assert set(body) == SAFE_TRIGGER_KEYS, body
    assert body["connection_id"] == cid
    assert body["trigger"] == "manual"
    assert body["outcome"] == "enqueued"
    datetime.fromisoformat(body["enqueued_at"])
    assert_no_secrets(body, FAKE_CONN_STR, ACCOUNT, CONTAINER, "env://")
    # Identity-only payload: tenant, connection, trigger class -- strings only.
    assert enqueued == [(tid, cid, "manual")]
    assert all(isinstance(arg, str) for arg in enqueued[0])


# --- Rows 7-8: inactive and PostgreSQL rejections --------------------------------------


async def test_manual_sync_on_inactive_connection_is_rejected_safely(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await validated_draft(client, tid, key="k-val")

    resp = await trigger_sync(client, cid, action_headers(tid, "k-val-sync"))

    assert resp.status_code == 409, resp.text
    payload = resp.json()
    assert_safe_envelope(payload)
    assert payload["error"]["code"] == "INACTIVE_CONNECTION"
    assert_no_secrets(payload, FAKE_CONN_STR, ACCOUNT, CONTAINER, "env://")
    assert enqueued == []
    current = await client.get(
        "/api/v1/data-sources/%s" % cid, headers=admin_headers(tid)
    )
    assert current.json()["status"] == "validated"


async def test_manual_sync_on_postgresql_connection_is_rejected(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, provider="azure_postgresql", key="k-pg")

    resp = await trigger_sync(client, cid, action_headers(tid, "k-pg-sync"))

    assert resp.status_code == 409, resp.text
    payload = resp.json()
    assert_safe_envelope(payload)
    assert payload["error"]["code"] == "UNSUPPORTED_PROVIDER"
    assert_no_secrets(payload, "pg.example.internal", "tenantdb", "reader", "env://")
    assert enqueued == []


# --- Rows 9-10: authorization and tenant binding ---------------------------------------


async def test_non_admin_manual_sync_is_denied(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-na")

    resp = await trigger_sync(
        client, cid, dict(user_headers(tid), **{"Idempotency-Key": "k-na-sync"})
    )

    assert resp.status_code == 403, resp.text
    assert enqueued == []


async def test_cross_tenant_manual_sync_is_not_found(
    client, tracked_tenants, fake_testers, enqueued
):
    tenant_a = await tracked_tenants()
    tenant_b = await tracked_tenants()
    cid = await active_connection(client, tenant_a, key="k-xt")

    resp = await trigger_sync(client, cid, action_headers(tenant_b, "k-xt-sync"))

    assert resp.status_code == 404, resp.text
    payload = resp.json()
    assert_safe_envelope(payload)
    assert payload["error"]["code"] == "CONNECTION_NOT_FOUND"
    assert_no_secrets(payload, "azure_blob", ACCOUNT, CONTAINER, FAKE_CONN_STR)
    assert enqueued == []


# --- Row 11: idempotent replay ---------------------------------------------------------


async def test_same_key_replay_does_not_enqueue_twice(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-rp")
    headers = action_headers(tid, "k-rp-sync")

    first = await trigger_sync(client, cid, headers)
    assert first.status_code == 202, first.text
    replay = await trigger_sync(client, cid, headers)
    assert replay.status_code == 202, replay.text
    assert replay.headers.get("Idempotent-Replay") == "true"
    assert replay.json() == first.json()
    assert len(enqueued) == 1

    # Same key, different body: refused, still no second enqueue.
    reused = await trigger_sync(client, cid, headers, body={"force": True})
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len(enqueued) == 1

    # A fresh key is a new intent and enqueues again (the worker lease serializes).
    fresh = await trigger_sync(client, cid, action_headers(tid, "k-rp-sync-2"))
    assert fresh.status_code == 202, fresh.text
    assert "Idempotent-Replay" not in fresh.headers
    assert len(enqueued) == 2


async def test_missing_idempotency_key_enqueues_nothing(
    client, tracked_tenants, fake_testers, enqueued
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-nokey")

    resp = await trigger_sync(client, cid, admin_headers(tid))

    assert resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert enqueued == []


async def test_broker_unavailable_returns_safe_code(
    client, tracked_tenants, fake_testers, monkeypatch
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-down")

    def _refuse(tenant_id, connection_id, trigger):
        raise ConnectionError("amqp://guest:hunter2@rabbitmq:5672 refused")

    monkeypatch.setattr(ds_api, "_enqueue_blob_sync", _refuse)

    resp = await trigger_sync(client, cid, action_headers(tid, "k-down-sync"))

    assert resp.status_code == 503, resp.text
    payload = resp.json()
    assert_safe_envelope(payload)
    assert payload["error"]["code"] == "SYNC_UNAVAILABLE"
    assert_no_secrets(payload, "amqp://", "hunter2", "rabbitmq", "refused")


# --- DS-001: connection responses report the latest completed run ----------------------


async def test_connection_reports_latest_completed_sync_run(
    client, tracked_tenants, session_factory, fake_testers
):
    tid = await tracked_tenants()
    cid = await active_connection(client, tid, key="k-last")
    schema = schema_for_tenant(tid)
    try:
        async with session_factory() as session:
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await session.commit()
            await ledger.ensure_sync_tables(session, schema)
            await session.execute(
                text(
                    f"INSERT INTO {schema}.azure_blob_sync_runs "
                    "(id, tenant_id, connection_id, trigger, outcome, reason, "
                    "started_at, completed_at) VALUES "
                    "('r-old', :tid, :cid, 'scheduled', 'succeeded', 'none', "
                    "NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '29 minutes'), "
                    "('r-lease', :tid, :cid, 'manual', 'lease_held', 'lease_held', "
                    "NOW() - INTERVAL '2 minutes', NOW() - INTERVAL '2 minutes'), "
                    "('r-running', :tid, :cid, 'scheduled', 'started', 'none', "
                    "NOW() - INTERVAL '1 minute', NULL)"
                ),
                {"tid": tid, "cid": cid},
            )
            await session.commit()

        # The run still in progress is skipped; the newest finished run wins.
        detail = (await client.get(
            "/api/v1/data-sources/%s" % cid, headers=admin_headers(tid)
        )).json()
        assert set(detail["last_sync"]) == {"outcome", "completed_at"}
        assert detail["last_sync"]["outcome"] == "lease_held"
        datetime.fromisoformat(detail["last_sync"]["completed_at"])

        listed = (await client.get(
            "/api/v1/data-sources", headers=admin_headers(tid)
        )).json()
        assert [item["last_sync"] for item in listed["items"]] == [detail["last_sync"]]

        # A mutation response carries the same run, so the portal cache is not reset.
        paused = await client.post(
            "/api/v1/data-sources/%s/pause" % cid, json={},
            headers=action_headers(tid, "k-last-p"),
        )
        assert paused.status_code == 200, paused.text
        assert paused.json()["last_sync"] == detail["last_sync"]
    finally:
        async with session_factory() as session:
            await session.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await session.commit()
