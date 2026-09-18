"""Verification for the tenant-scoped connection control plane (CAP-2).

Maps to `openspec/changes/cap-2-tenant-scoped-connection-control-plane/verification.md`
Section 1 rows 1-12, plus the TDD REST-contract tests (routes, closed schemas,
idempotency, pagination, replacement, retirement confirmation).

Azure is unreachable from this environment and live Azure verification is
deferred per run provisioning, so the secure-test seam runs registered fakes --
exactly the seam production uses for SDK-backed testers. Every other layer
(persistence, lifecycle, auth, evidence) runs against the real test database.

Teardown removes exactly what each test created: connection rows, idempotency
rows, and tenant rows it inserted. Nothing leaks into the shared dataset.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.gateway.main import app as gateway_app
from src.shared.auth import create_access_token
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources import providers as prov
from src.shared.data_sources import resolver as cap2_resolver
from src.shared.data_sources import service as svc
from src.shared.data_sources import testing as testing_seam
from src.shared.data_sources.store import CONNECTIONS_TABLE, IDEMPOTENCY_TABLE
from src.shared.data_sources.testing import SecureTestResult
from src.shared.integration_profile import (
    TransitionRejected,
    activate_profile,
    load_profile,
    unsupported_selections,
    validate_profile,
    write_profile,
)
from src.shared.observability import domain_metrics as dm

from tests.test_ingestion_boundary import (  # noqa: F401
    session_factory,
    tenant,
)

pytestmark = [pytest.mark.verification]

needs_event_loop = pytest.mark.asyncio


@pytest.fixture
async def client():
    """HTTP client for the gateway app (the boundary under test)."""
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

FAKE_CONN_STR = "fake-test-connection-string"
FAKE_PASSWORD = "fake-test-password"
ACCOUNT = "testaccount"
CONTAINER = "testcontainer"

BLOB_CONFIG = {"account": ACCOUNT, "container": CONTAINER, "prefix": "docs/"}
BLOB_SECRETS = {"connection_string_ref": "env://CAP2_TEST_CONN_STR"}
PG_CONFIG = {
    "host": "pg.example.internal",
    "port": 5432,
    "database": "tenantdb",
    "username": "reader",
    "sslmode": "verify-full",
}
PG_SECRETS = {"password_ref": "env://CAP2_TEST_PASSWORD"}
EVIDENCE = ["network_approved", "governance_approved"]


class FakeTester:
    """Deterministic stand-in for an SDK-backed secure tester."""

    def __init__(self, passed=True, reason="none"):
        self.passed = passed
        self.reason = reason
        self.calls = []

    async def run(self, provider, configuration, secret_values):
        self.calls.append((provider, dict(configuration)))
        return SecureTestResult(self.passed, self.reason)


@pytest.fixture
async def fake_testers():
    """Register passing fakes; restore the shipped testers afterwards."""
    passing = FakeTester(passed=True)
    testing_seam.register_tester(prov.PROVIDER_AZURE_BLOB, passing)
    testing_seam.register_tester(prov.PROVIDER_AZURE_POSTGRESQL, passing)
    yield passing
    testing_seam.register_tester(
        prov.PROVIDER_AZURE_BLOB, testing_seam.TlsHandshakeTester()
    )
    testing_seam.register_tester(
        prov.PROVIDER_AZURE_POSTGRESQL, testing_seam.TlsHandshakeTester()
    )


@pytest.fixture
async def tracked_tenants(session_factory):
    """Tenants this test creates, removed with their control-plane rows after."""
    created = []

    async def _make():
        tid = uuid.uuid4().hex
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status) "
                    "VALUES (:id, :n, :s, 'active') ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid, "n": "CAP2 %s" % tid[:8], "s": "cap2-%s" % tid[:8]},
            )
            await session.commit()
        created.append(tid)
        return tid

    yield _make

    async with session_factory() as session:
        for tid in created:
            await session.execute(
                text("DELETE FROM %s WHERE tenant_id = :id" % CONNECTIONS_TABLE),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM %s WHERE tenant_id = :id" % IDEMPOTENCY_TABLE),
                {"id": tid},
            )
            await session.execute(
                text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid}
            )
            await session.commit()


@pytest.fixture(autouse=True)
def _env_refs():
    os.environ["CAP2_TEST_CONN_STR"] = FAKE_CONN_STR
    os.environ["CAP2_TEST_PASSWORD"] = FAKE_PASSWORD
    yield
    os.environ.pop("CAP2_TEST_CONN_STR", None)
    os.environ.pop("CAP2_TEST_PASSWORD", None)


def admin_headers(tenant_id):
    token = create_access_token(tenant_id, "admin-1", "tenant_admin")
    return {"Authorization": "Bearer %s" % token}


def user_headers(tenant_id):
    token = create_access_token(tenant_id, "user-1", "business_user")
    return {"Authorization": "Bearer %s" % token}


async def create_draft(client, tenant_id, provider="azure_blob",
                       config=None, secrets=None, key="k-create"):
    return await client.post(
        "/api/v1/data-sources",
        json={
            "provider": provider,
            "configuration": config or dict(BLOB_CONFIG),
            "secret_references": secrets or dict(BLOB_SECRETS),
        },
        headers=dict(admin_headers(tenant_id), **{"Idempotency-Key": key}),
    )


def action_headers(tenant_id, key):
    return dict(admin_headers(tenant_id), **{"Idempotency-Key": key})


def assert_safe_envelope(payload):
    assert set(payload) == {"error"}, payload
    assert set(payload["error"]) == {"code", "message", "request_id"}, payload


def assert_no_secrets(payload, *forbidden):
    rendered = str(payload)
    for value in forbidden:
        assert value not in rendered, "sensitive value leaked: %r" % (value,)


class TestCreate:
    pytestmark = needs_event_loop

    async def test_create_returns_draft_with_names_only(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        resp = await create_draft(client, tid)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["provider"] == "azure_blob"
        assert body["status"] == "draft"
        assert body["configured_fields"] == ["account", "container", "prefix"]
        assert body["secret_reference_fields"] == ["connection_string_ref"]
        assert body["last_test"]["outcome"] == "not_run"
        assert body["last_test"]["reason_code"] == "none"
        assert body["last_test"]["tested_at"] is None
        assert body["activation"]["outcome"] == "inactive"
        assert body["schedule"] == {"enabled": False, "cadence_minutes": None}
        assert body["last_sync"] == {"outcome": "never_run", "completed_at": None}
        assert_no_secrets(body, FAKE_CONN_STR, ACCOUNT, CONTAINER)

    async def test_create_postgres_shape_omits_sync(self, client, tracked_tenants):
        tid = await tracked_tenants()
        resp = await create_draft(
            client, tid, provider="azure_postgresql",
            config=dict(PG_CONFIG), secrets=dict(PG_SECRETS), key="k-pg",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["schedule"] == {"enabled": False, "cadence_minutes": None}
        assert "last_sync" not in body
        assert body["secret_reference_fields"] == ["password_ref"]
        assert_no_secrets(body, FAKE_PASSWORD, "pg.example.internal")

    async def test_unknown_provider_rejected(self, client, tracked_tenants):
        tid = await tracked_tenants()
        resp = await create_draft(
            client, tid, provider="s3",
            config={"bucket": "b"}, secrets={}, key="k-bad",
        )
        assert resp.status_code == 422, resp.text
        assert_safe_envelope(resp.json())
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"

    async def test_literal_credential_rejected(self, client, tracked_tenants):
        tid = await tracked_tenants()
        resp = await create_draft(
            client, tid, secrets={"connection_string_ref": "hunter2-plaintext"},
            key="k-lit",
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"

    async def test_closed_config_keys_enforced(self, client, tracked_tenants):
        tid = await tracked_tenants()
        bad = dict(BLOB_CONFIG)
        bad["connection_string"] = "postgres://x"
        resp = await create_draft(client, tid, config=bad, key="k-closed")
        assert resp.status_code == 422, resp.text

    async def test_postgres_sslmode_fixed(self, client, tracked_tenants):
        tid = await tracked_tenants()
        bad = dict(PG_CONFIG)
        bad["sslmode"] = "prefer"
        resp = await create_draft(
            client, tid, provider="azure_postgresql",
            config=bad, secrets=dict(PG_SECRETS), key="k-ssl",
        )
        assert resp.status_code == 422, resp.text

    async def test_unknown_top_level_field_rejected(self, client, tracked_tenants):
        tid = await tracked_tenants()
        resp = await client.post(
            "/api/v1/data-sources",
            json={
                "provider": "azure_blob", "configuration": dict(BLOB_CONFIG),
                "secret_references": dict(BLOB_SECRETS), "tenant_id": tid,
            },
            headers=action_headers(tid, "k-extra"),
        )
        assert resp.status_code == 422, resp.text

class TestSecureTest:
    pytestmark = needs_event_loop

    async def test_passing_test_validates(self, client, tracked_tenants, fake_testers):
        tid = await tracked_tenants()
        created = (await create_draft(client, tid)).json()
        resp = await client.post(
            "/api/v1/data-sources/%s/test" % created["id"],
            json={},
            headers=action_headers(tid, "k-test"),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "validated"
        assert body["last_test"]["outcome"] == "passed"
        assert body["last_test"]["tested_at"] is not None
        assert fake_testers.calls and fake_testers.calls[0][0] == "azure_blob"
        assert_no_secrets(body, FAKE_CONN_STR, ACCOUNT)

    async def test_unresolvable_reference_errors_safely(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        resp = await create_draft(
            client, tid,
            secrets={"connection_string_ref": "env://CAP2_MISSING_REF"},
            key="k-unres",
        )
        cid = resp.json()["id"]
        tested = await client.post(
            "/api/v1/data-sources/%s/test" % cid,
            json={},
            headers=action_headers(tid, "k-test2"),
        )
        assert tested.status_code == 200, tested.text
        body = tested.json()
        assert body["status"] == "error"
        assert body["last_test"]["outcome"] == "failed"
        assert body["last_test"]["reason_code"] == "secret_unavailable"
        assert body["last_test"]["tested_at"] is not None
        assert_no_secrets(body, "CAP2_MISSING_REF")

    async def test_failing_tester_errors_safely(
        self, client, tracked_tenants, session_factory
    ):
        tid = await tracked_tenants()
        testing_seam.register_tester(
            prov.PROVIDER_AZURE_BLOB,
            FakeTester(passed=False, reason="connection_failed"),
        )
        try:
            cid = (await create_draft(client, tid, key="k-fail")).json()["id"]
            tested = await client.post(
                "/api/v1/data-sources/%s/test" % cid,
                json={},
                headers=action_headers(tid, "k-test3"),
            )
        finally:
            testing_seam.register_tester(
                prov.PROVIDER_AZURE_BLOB, testing_seam.TlsHandshakeTester()
            )
        assert tested.status_code == 200, tested.text
        assert tested.json()["last_test"]["reason_code"] == "connection_failed"


class TestAuthz:
    pytestmark = needs_event_loop

    async def test_no_token_is_unauthenticated(self, client, tracked_tenants):
        await tracked_tenants()
        resp = await client.get("/api/v1/data-sources")
        assert resp.status_code == 401, resp.text

    async def test_non_admin_denied_without_state_change(
        self, client, tracked_tenants, session_factory, fake_testers
    ):
        tid = await tracked_tenants()
        cid = (await create_draft(client, tid)).json()["id"]
        denied = await client.post(
            "/api/v1/data-sources/%s/test" % cid,
            json={},
            headers=dict(user_headers(tid), **{"Idempotency-Key": "k-denied"}),
        )
        assert denied.status_code == 403, denied.text
        async with session_factory() as session:
            row = await svc.get_connection(session, tid, cid)
            assert row.status == "draft"

    async def test_cross_tenant_access_is_not_found(
        self, client, tracked_tenants, fake_testers
    ):
        tenant_a = await tracked_tenants()
        tenant_b = await tracked_tenants()
        cid = (await create_draft(client, tenant_a)).json()["id"]
        read = await client.get(
            "/api/v1/data-sources/%s" % cid, headers=admin_headers(tenant_b)
        )
        assert read.status_code == 404, read.text
        assert read.json()["error"]["code"] == "CONNECTION_NOT_FOUND"
        listed = await client.get(
            "/api/v1/data-sources", headers=admin_headers(tenant_b)
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 0
        act = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tenant_b, "k-x"),
        )
        assert act.status_code == 404, act.text

async def validated_draft(client, tid, provider="azure_blob",
                          config=None, secrets=None, key="k-v"):
    if provider == "azure_blob":
        config = config if config is not None else dict(BLOB_CONFIG)
        secrets = secrets if secrets is not None else dict(BLOB_SECRETS)
    else:
        config = config if config is not None else dict(PG_CONFIG)
        secrets = secrets if secrets is not None else dict(PG_SECRETS)
    created = await create_draft(client, tid, provider, config, secrets, key)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    tested = await client.post(
        "/api/v1/data-sources/%s/test" % cid, json={},
        headers=action_headers(tid, "%s-t" % key),
    )
    assert tested.status_code == 200, tested.text
    return cid


class TestActivation:
    pytestmark = needs_event_loop

    async def test_activate_without_test_is_required(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        cid = (await create_draft(client, tid)).json()["id"]
        resp = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-act"),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "TEST_REQUIRED"
        current = await client.get(
            "/api/v1/data-sources/%s" % cid, headers=admin_headers(tid)
        )
        assert current.json()["status"] == "draft"

    async def test_activate_with_failed_test_is_rejected(
        self, client, tracked_tenants
    ):
        tid = await tracked_tenants()
        testing_seam.register_tester(
            prov.PROVIDER_AZURE_BLOB,
            FakeTester(passed=False, reason="connection_failed"),
        )
        try:
            cid = await validated_draft(client, tid, key="k-fv")
        finally:
            testing_seam.register_tester(
                prov.PROVIDER_AZURE_BLOB, testing_seam.TlsHandshakeTester()
            )
        resp = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-actf"),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "TEST_FAILED"

    async def test_activate_without_evidence_is_blocked(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        cid = await validated_draft(client, tid, key="k-ev")
        resp = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": ["network_approved"]},
            headers=action_headers(tid, "k-acte"),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "ACTIVATION_PREREQUISITE_MISSING"
        body = (await client.get(
            "/api/v1/data-sources/%s" % cid, headers=admin_headers(tid)
        )).json()
        assert body["status"] == "validated"
        assert body["activation"]["outcome"] == "blocked"
        assert body["activation"]["reason_code"] == "prerequisite_missing"

    async def test_independent_providers_activate_concurrently(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        blob = await validated_draft(client, tid, key="k-b1")
        pg = await validated_draft(client, tid, provider="azure_postgresql", key="k-p1")
        for cid in (blob, pg):
            resp = await client.post(
                "/api/v1/data-sources/%s/activate" % cid,
                json={"activation_evidence": EVIDENCE},
                headers=action_headers(tid, "k-a-%s" % cid[:8]),
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["activation"]["outcome"] == "active"
        listed = (await client.get(
            "/api/v1/data-sources", headers=admin_headers(tid)
        )).json()
        assert listed["total"] == 2
        assert {i["status"] for i in listed["items"]} == {"active"}

    async def test_duplicate_active_provider_rejected(
        self, client, tracked_tenants, session_factory, fake_testers
    ):
        tid = await tracked_tenants()
        first = await validated_draft(client, tid, key="k-d1")
        second = await validated_draft(client, tid, key="k-d2")
        for cid, key, expect in ((first, "k-a1", 200), (second, "k-a2", 409)):
            resp = await client.post(
                "/api/v1/data-sources/%s/activate" % cid,
                json={"activation_evidence": EVIDENCE},
                headers=action_headers(tid, key),
            )
            assert resp.status_code == expect, resp.text
            if expect == 409:
                assert resp.json()["error"]["code"] == "ACTIVE_PROVIDER_EXISTS"
        async with session_factory() as session:
            incumbent = await svc.get_connection(session, tid, first)
            assert incumbent.status == "active"
            challenger = await svc.get_connection(session, tid, second)
            assert challenger.status == "validated"

    async def test_paused_with_current_evidence_reactivates(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        cid = await validated_draft(client, tid, key="k-p")
        activate = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a"),
        )
        assert activate.status_code == 200, activate.text
        paused = await client.post(
            "/api/v1/data-sources/%s/pause" % cid, json={},
            headers=action_headers(tid, "k-p2"),
        )
        assert paused.status_code == 200, paused.text
        assert paused.json()["status"] == "paused"
        assert paused.json()["schedule"] == {"enabled": False, "cadence_minutes": None}
        again = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a3"),
        )
        assert again.status_code == 200, again.text
        assert again.json()["status"] == "active"

    async def test_update_clears_evidence_to_draft(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        created = await create_draft(
            client, tid,
            secrets={"connection_string_ref": "env://CAP2_MISSING_REF"},
            key="k-ue",
        )
        cid = created.json()["id"]
        await client.post(
            "/api/v1/data-sources/%s/test" % cid, json={},
            headers=action_headers(tid, "k-ue-t"),
        )
        errored = (await client.get(
            "/api/v1/data-sources/%s" % cid, headers=admin_headers(tid)
        )).json()
        assert errored["status"] == "error"
        updated = await client.patch(
            "/api/v1/data-sources/%s" % cid,
            json={
                "configuration": {"prefix": "new/"},
                "secret_references": dict(BLOB_SECRETS),
            },
            headers=action_headers(tid, "k-u2"),
        )
        assert updated.status_code == 200, updated.text
        body = updated.json()
        assert body["status"] == "draft"
        assert body["last_test"]["outcome"] == "not_run"
        assert body["configured_fields"] == ["account", "container", "prefix"]

    async def test_update_validated_rejected(self, client, tracked_tenants,
                                            fake_testers):
        tid = await tracked_tenants()
        cid = await validated_draft(client, tid, key="k-uv")
        resp = await client.patch(
            "/api/v1/data-sources/%s" % cid,
            json={"configuration": {"prefix": "new/"}},
            headers=action_headers(tid, "k-uv2"),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"

    async def test_pause_non_active_rejected(self, client, tracked_tenants):
        tid = await tracked_tenants()
        cid = (await create_draft(client, tid)).json()["id"]
        resp = await client.post(
            "/api/v1/data-sources/%s/pause" % cid, json={},
            headers=action_headers(tid, "k-pn"),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"

class TestRetireReplace:
    pytestmark = needs_event_loop

    async def test_retire_requires_confirmation(self, client, tracked_tenants):
        tid = await tracked_tenants()
        cid = (await create_draft(client, tid)).json()["id"]
        for payload, key in (({}, "k-r0"), ({"confirm": False}, "k-rf")):
            resp = await client.post(
                "/api/v1/data-sources/%s/retire" % cid, json=payload,
                headers=action_headers(tid, key),
            )
            assert resp.status_code == 422, resp.text
            assert resp.json()["error"]["code"] == "RETIRE_CONFIRMATION_REQUIRED"

    async def test_active_must_pause_before_retire(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        cid = await validated_draft(client, tid, key="k-rp")
        await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a"),
        )
        refused = await client.post(
            "/api/v1/data-sources/%s/retire" % cid,
            json={"confirm": True}, headers=action_headers(tid, "k-r1"),
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "RETIRED_CONNECTION"
        paused = await client.post(
            "/api/v1/data-sources/%s/pause" % cid, json={},
            headers=action_headers(tid, "k-p"),
        )
        assert paused.status_code == 200, paused.text
        retired = await client.post(
            "/api/v1/data-sources/%s/retire" % cid,
            json={"confirm": True}, headers=action_headers(tid, "k-r2"),
        )
        assert retired.status_code == 200, retired.text
        assert retired.json()["status"] == "retired"
        dead = await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a2"),
        )
        assert dead.status_code == 409, dead.text

    async def test_replace_links_successor_and_retires_on_activate(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        pred = await validated_draft(client, tid, key="k-rpc")
        await client.post(
            "/api/v1/data-sources/%s/activate" % pred,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a"),
        )
        new_config = dict(BLOB_CONFIG)
        new_config["prefix"] = "v2/"
        replaced = await client.post(
            "/api/v1/data-sources/%s/replace" % pred,
            json={
                "provider": "azure_blob", "configuration": new_config,
                "secret_references": dict(BLOB_SECRETS),
            },
            headers=action_headers(tid, "k-rep"),
        )
        assert replaced.status_code == 201, replaced.text
        succ = replaced.json()
        assert succ["status"] == "draft"
        assert succ["replaces_connection_id"] == pred
        pred_body = (await client.get(
            "/api/v1/data-sources/%s" % pred, headers=admin_headers(tid)
        )).json()
        assert pred_body["status"] == "active"
        assert pred_body["replaced_by_connection_id"] == succ["id"]
        await client.post(
            "/api/v1/data-sources/%s/test" % succ["id"], json={},
            headers=action_headers(tid, "k-t2"),
        )
        activated = await client.post(
            "/api/v1/data-sources/%s/activate" % succ["id"],
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tid, "k-a2"),
        )
        assert activated.status_code == 200, activated.text
        pred_after = (await client.get(
            "/api/v1/data-sources/%s" % pred, headers=admin_headers(tid)
        )).json()
        assert pred_after["status"] == "retired"
        assert activated.json()["status"] == "active"

    async def test_failed_replacement_leaves_predecessor(
        self, client, tracked_tenants, fake_testers
    ):
        tid = await tracked_tenants()
        pred = (await create_draft(client, tid, key="k-fp")).json()["id"]
        bad = await client.post(
            "/api/v1/data-sources/%s/replace" % pred,
            json={
                "provider": "azure_blob", "configuration": {"account": "x"},
                "secret_references": dict(BLOB_SECRETS),
            },
            headers=action_headers(tid, "k-bad"),
        )
        assert bad.status_code == 422, bad.text
        pred_body = (await client.get(
            "/api/v1/data-sources/%s" % pred, headers=admin_headers(tid)
        )).json()
        assert pred_body["status"] == "draft"
        assert pred_body["replaced_by_connection_id"] is None


class TestContract:
    pytestmark = needs_event_loop

    async def test_replay_returns_original(self, client, tracked_tenants):
        tid = await tracked_tenants()
        headers = dict(admin_headers(tid), **{"Idempotency-Key": "replay-1"})
        payload = {
            "provider": "azure_blob", "configuration": dict(BLOB_CONFIG),
            "secret_references": dict(BLOB_SECRETS),
        }
        first = await client.post("/api/v1/data-sources", json=payload, headers=headers)
        assert first.status_code == 201, first.text
        assert "Idempotent-Replay" not in first.headers
        second = await client.post("/api/v1/data-sources", json=payload, headers=headers)
        assert second.status_code == 201, second.text
        assert second.headers.get("Idempotent-Replay") == "true"
        assert second.json()["id"] == first.json()["id"]

    async def test_key_reuse_with_different_body_conflicts(
        self, client, tracked_tenants
    ):
        tid = await tracked_tenants()
        headers = dict(admin_headers(tid), **{"Idempotency-Key": "reuse-1"})
        first = await client.post(
            "/api/v1/data-sources",
            json={"provider": "azure_blob", "configuration": dict(BLOB_CONFIG),
                  "secret_references": dict(BLOB_SECRETS)},
            headers=headers,
        )
        assert first.status_code == 201, first.text
        other = dict(BLOB_CONFIG)
        other["prefix"] = "other/"
        second = await client.post(
            "/api/v1/data-sources",
            json={"provider": "azure_blob", "configuration": other,
                  "secret_references": dict(BLOB_SECRETS)},
            headers=headers,
        )
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    async def test_missing_key_is_required(self, client, tracked_tenants):
        tid = await tracked_tenants()
        resp = await client.post(
            "/api/v1/data-sources",
            json={"provider": "azure_blob", "configuration": dict(BLOB_CONFIG),
                  "secret_references": dict(BLOB_SECRETS)},
            headers=admin_headers(tid),
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
        listed = (await client.get(
            "/api/v1/data-sources", headers=admin_headers(tid)
        )).json()
        assert listed["total"] == 0

    async def test_list_pagination_and_bounds(self, client, tracked_tenants):
        tid = await tracked_tenants()
        for i in range(3):
            resp = await create_draft(client, tid, key="k-l%d" % i)
            assert resp.status_code == 201, resp.text
        page1 = (await client.get(
            "/api/v1/data-sources?page=1&page_size=2", headers=admin_headers(tid)
        )).json()
        assert (page1["page"], page1["page_size"], page1["total"]) == (1, 2, 3)
        assert page1["total_pages"] == 2
        assert page1["sort"] == "last_activity" and page1["order"] == "desc"
        assert len(page1["items"]) == 2
        empty = (await client.get(
            "/api/v1/data-sources?page=9&page_size=2", headers=admin_headers(tid)
        )).json()
        assert empty["items"] == [] and empty["total"] == 3
        bad = await client.get(
            "/api/v1/data-sources?page_size=101", headers=admin_headers(tid)
        )
        assert bad.status_code == 422, bad.text
        unknown = await client.get(
            "/api/v1/data-sources?tenant_id=x", headers=admin_headers(tid)
        )
        assert unknown.status_code == 422, unknown.text
        assert unknown.json()["error"]["code"] == "INVALID_REQUEST"

    async def test_platform_provider_not_administrable(
        self, client, tracked_tenants
    ):
        """Row 11: the Azure-bounded lifecycle grants no platform-profile access."""
        tid = await tracked_tenants()
        resp = await create_draft(
            client, tid, provider="platform_upload",
            config={}, secrets={}, key="k-plat",
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "INVALID_REQUEST"


class TestCompatibility:
    pytestmark = needs_event_loop

    async def test_unsupported_selection_stays_recorded_but_inactive(
        self, tracked_tenants, session_factory
    ):
        """Row 7: a recorded-but-unsupported value succeeds as a write, stays draft."""
        tid = await tracked_tenants()
        async with session_factory() as session:
            await write_profile(session, tid, selections={"source_adapter": "keka"})
            loaded = await load_profile(session, tid)
        assert loaded.status == "draft"
        assert unsupported_selections(loaded.selections()) == ["source_adapter"]

    async def test_unsupported_selection_cannot_activate(
        self, tracked_tenants, session_factory
    ):
        """Row 8: activation of an unsupported selection is rejected."""
        tid = await tracked_tenants()
        async with session_factory() as session:
            await write_profile(
                session, tid, selections={"relational_adapter": "tenant_postgresql"}
            )
            await validate_profile(session, tid)
            with pytest.raises(TransitionRejected):
                await activate_profile(session, tid)

    async def test_approved_azure_resolves_only_for_owning_tenant(
        self, client, tracked_tenants, session_factory, fake_testers
    ):
        """Row 9: an activated Azure capability resolves for its tenant only."""
        tenant_a = await tracked_tenants()
        tenant_b = await tracked_tenants()
        cid = await validated_draft(client, tenant_a, key="k-res")
        await client.post(
            "/api/v1/data-sources/%s/activate" % cid,
            json={"activation_evidence": EVIDENCE},
            headers=action_headers(tenant_a, "k-a"),
        )
        async with session_factory() as session:
            assert await cap2_resolver.is_selection_executable(
                session, tenant_a, "source_adapter", "azure_blob"
            ) is True
            assert await cap2_resolver.is_selection_executable(
                session, tenant_b, "source_adapter", "azure_blob"
            ) is False
            assert await cap2_resolver.executable_providers(session, tenant_a) == [
                "azure_blob"
            ]
            assert await cap2_resolver.executable_providers(session, tenant_b) == []
            assert await cap2_resolver.active_connection(
                session, tenant_b, "azure_blob"
            ) is None

    async def test_platform_defaults_stay_executable(
        self, tracked_tenants, session_factory
    ):
        """Row 10: inactive/unsupported sources never alter the executable set."""
        tid = await tracked_tenants()
        async with session_factory() as session:
            assert await cap2_resolver.is_selection_executable(
                session, tid, "source_adapter", "platform_upload"
            ) is True
            assert await cap2_resolver.is_selection_executable(
                session, tid, "source_adapter", "keka"
            ) is False
            assert await cap2_resolver.is_selection_executable(
                session, tid, "source_adapter", "azure_blob"
            ) is False


class TestTelemetry:
    def test_metric_label_sets_mirror_lifecycle(self):
        """The declared families use exactly the lifecycle vocabulary."""
        lifecycle_fam = dm.FAMILIES["ner_data_source_lifecycle_total"]
        test_fam = dm.FAMILIES["ner_data_source_tests_total"]
        by_name = {label.name: label.values for label in lifecycle_fam.labels}
        assert by_name["provider"] == frozenset(
            {"azure_blob", "azure_postgresql", "azure_postgresql_data_plane", "other"}
        )
        assert by_name["action"] == frozenset(
            {"create", "update", "test", "activate", "pause", "replace", "retire",
             "sync", "other"}
        )
        assert by_name["outcome"] == frozenset({"success", "rejected", "error", "other"})
        by_name = {label.name: label.values for label in test_fam.labels}
        assert by_name["outcome"] == frozenset({"passed", "failed", "not_run", "other"})
        assert by_name["reason"] == (set(lc.TEST_REASONS) | {"other"})

    def test_control_plane_families_carry_no_tenant_label(self):
        assert "tenant_id" not in dm.FAMILIES[
            "ner_data_source_lifecycle_total"
        ].label_names
        assert "tenant_id" not in dm.FAMILIES["ner_data_source_tests_total"].label_names
        assert dm.allowlist_violations() == []

    def test_recorders_coerce_unknown_values(self):
        dm.record_data_source_lifecycle("azure_blob", "activate", "success")
        dm.record_data_source_lifecycle("nope", "activate", "success")
        dm.record_data_source_test("azure_blob", "passed", "none")
        dm.record_data_source_test("azure_blob", "passed", "raw provider text")
