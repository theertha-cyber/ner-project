import asyncio
import time
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app
from src.gateway.api.v1.dashboard import (
    DashboardSummaryResponse,
    StatItem,
    ActivityRow,
    SideMetric,
    SideRow,
    DashboardData,
    _platform_health_status,
)


def auth_header(tenant_id: str, role: str = "tenant_admin", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _get(role: str, tenant_id: str = "test-tenant", user_id: str = "test-user") -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/summary", headers=auth_header(tenant_id, role, user_id))
        return resp.status_code, resp.json() if resp.text else {}


@pytest.mark.asyncio
class TestDashboardSummaryShape:
    async def test_unauthenticated_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    async def test_system_admin_returns_correct_shape(self):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        assert "data" in body
        assert "sources" in body
        d = body["data"]
        assert d["kicker"] == "Platform control plane"
        assert isinstance(d["stats"], list) and len(d["stats"]) == 4
        assert [s["label"] for s in d["stats"]] == [
            "Active Tenants", "Active Users", "Pending Approvals", "Training Jobs Running",
        ]
        assert d["pTitle"] == "Platform Activity"
        assert isinstance(d["pRows"], list)
        assert d["sideTop"] == "Platform Health"
        assert d["big"] in ("Healthy", "Degraded", "Critical")
        assert isinstance(d["sideMetrics"], list) and len(d["sideMetrics"]) == 3
        assert isinstance(d["sideRows"], list)
        payload_str = str(body)
        for banned in ("f1", "F1", "precision", "recall", "loss", "SLA", "p95", "GPU"):
            assert banned not in payload_str

    async def test_tenant_admin_returns_correct_shape(self):
        status, body = await _get("tenant_admin")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Good morning"
        assert len(d["stats"]) == 3
        assert d["pTitle"] == "Recent Activity"
        assert d["sideTop"] == "Active model"

    async def test_annotator_returns_correct_shape(self):
        status, body = await _get("annotator")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Your annotation queue"
        assert [s["label"] for s in d["stats"]] == ["Assigned tasks", "Completion"]
        assert "continueWork" in d
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"

    async def test_business_user_returns_correct_shape(self):
        status, body = await _get("business_user")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Your AI assistant workspace"
        assert len(d["stats"]) == 3
        assert [s["label"] for s in d["stats"]] == ["Conversations", "Messages Sent", "Responses Marked Helpful"]
        assert d["pTitle"] == "Recent Conversations"
        assert d["sideTop"] == "AI Assistant Status"
        assert d["sideBot"] == ""

    async def test_system_admin_tenant_count_is_wired(self):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        sources = body["sources"]
        assert "tenants" in sources
        assert sources["tenants"] is True

    async def test_response_model_validates_correctly(self):
        status, body = await _get("tenant_admin")
        assert status == 200
        validated = DashboardSummaryResponse(**body)
        assert isinstance(validated.data, DashboardData)
        assert isinstance(validated.data.stats[0], StatItem)
        assert isinstance(validated.data.pRows[0], ActivityRow)
        assert isinstance(validated.data.sideMetrics[0], SideMetric)


async def _seed_docs(engine, schema: str, count: int, annotated: int = 0, statuses: list[str] | None = None):
    async with engine.begin() as conn:
        for i in range(count):
            doc_id = f"doc-{i}"
            st = statuses[i] if statuses else ("annotated" if i < annotated else "uploaded")
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, :st) ON CONFLICT (id) DO NOTHING"),
                {"id": doc_id, "tid": "test-tenant", "fn": f"doc-{i}.pdf", "st": st},
            )


async def _seed_promoted_model(engine, schema: str, f1: float = 0.872):
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.model_versions (id, tenant_id, version, metrics, status, promoted_at) VALUES (:id, :tid, :ver, :met, 'promoted', NOW()) ON CONFLICT (id) DO NOTHING"),
            {"id": "mod-1", "tid": "test-tenant", "ver": 1, "met": f'{{"f1": {f1}, "precision": 0.91, "recall": 0.85, "loss": 0.12}}'},
        )


async def _seed_training_jobs(engine, schema: str, count: int = 1):
    async with engine.begin() as conn:
        for i in range(count):
            await conn.execute(
                text(f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, created_at, started_at) VALUES (:id, :tid, 'completed', NOW(), NOW()) ON CONFLICT (id) DO NOTHING"),
                {"id": f"tj-{i}", "tid": "test-tenant"},
            )


async def _seed_annotator_tasks(engine, schema: str, user_id: str, total: int = 8, completed: int = 6):
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) VALUES ('doc-ann', 'test-tenant', 'doc-ann.pdf', 'uploaded') ON CONFLICT (id) DO NOTHING")
        )
        for i in range(total):
            task_id = f"at-{i}"
            # Real annotation_task vocabulary. "annotated" was never a task
            # status — it is a *document* status (see seed.py) — so the previous
            # fixture value matched no production code path.
            status = "completed" if i < completed else "pending"
            await conn.execute(
                text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, 'doc-ann', :uid, :st) ON CONFLICT (id) DO NOTHING"),
                {"id": task_id, "uid": user_id, "st": status},
            )


async def _seed_spans(engine, schema: str, count: int = 45):
    async with engine.begin() as conn:
        for i in range(count):
            await conn.execute(
                text(f"INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence) VALUES (:id, 'doc-ann', 'PER', :cs, :ce, 'text', 0.95) ON CONFLICT (id) DO NOTHING"),
                {"id": f"sp-{i}", "cs": i * 5, "ce": i * 5 + 4},
            )


async def _seed_conversations(engine, schema: str, user_id: str, conversation_count: int = 3, messages_per: int = 2, up_ratings: int = 1):
    async with engine.begin() as conn:
        for i in range(conversation_count):
            conv_id = f"conv-{i}"
            await conn.execute(
                text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES (:id, :tid, :uid, :title) ON CONFLICT (id) DO NOTHING"),
                {"id": conv_id, "tid": "test-tenant", "uid": user_id, "title": f"Question about topic {i}"},
            )
            for m in range(messages_per):
                msg_id = f"msg-{i}-{m}"
                await conn.execute(
                    text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content) VALUES (:id, :cid, 'user', :content) ON CONFLICT (id) DO NOTHING"),
                    {"id": msg_id, "cid": conv_id, "content": f"message {m}"},
                )
        rated = 0
        for i in range(conversation_count):
            if rated >= up_ratings:
                break
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_message_feedback (id, message_id, tenant_id, user_id, rating) VALUES (:id, :mid, :tid, :uid, 'up') ON CONFLICT (id) DO NOTHING"),
                {"id": f"fb-{i}", "mid": f"msg-{i}-0", "tid": "test-tenant", "uid": user_id},
            )
            rated += 1


@pytest.mark.asyncio
class TestTenantAdminQueries:
    async def test_stats_return_real_values(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 15, 9)
        await _seed_training_jobs(engine, schema, 2)
        await _seed_promoted_model(engine, schema, 0.872)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]
        sources = body["sources"]

        assert s[0]["value"] == "15"
        assert sources["documents"] is True

        expected_f1 = f"{0.872 * 100:.1f}"
        assert body["data"]["big"] == expected_f1

        # Training value reflects jobs currently running, not a 24h historical
        # count — the 2 seeded jobs are 'completed', so none are running.
        assert s[2]["value"] == "0"
        assert "2" in s[2]["sub"]

    async def test_training_stat_shows_zero_when_nothing_running(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_training_jobs(engine, schema, 1)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]
        assert s[2]["value"] == "0"
        assert s[2]["sub"] == "1 job ran in last 24h"

    async def test_annotation_progress_calculates_correctly(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 20)
        async with engine.begin() as conn:
            for i in range(20):
                task_status = "completed" if i < 12 else "open"
                await conn.execute(
                    text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, status) VALUES (:id, :did, :st) ON CONFLICT (id) DO NOTHING"),
                    {"id": f"annt-{i}", "did": f"doc-{i}", "st": task_status},
                )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]

        assert s[1]["value"] == "12/20"
        assert s[1]["unit"] == ""

    async def test_active_model_f1_from_promoted_model(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 5)
        await _seed_promoted_model(engine, schema, 0.872)

        status, body = await _get("tenant_admin", tid)
        assert status == 200

        assert body["data"]["big"] == "87.2"

    async def test_pipeline_activity_rows_populated(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 3)
        await _seed_training_jobs(engine, schema, 2)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        non_placeholder = [r for r in rows if r["title"] not in ("\u2014", "No recent activity")]
        assert len(non_placeholder) > 0
        for r in non_placeholder:
            assert r["go"] in ("documents", "training")

    async def test_graceful_degradation_when_training_unavailable(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 5)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]
        sources = body["sources"]

        assert s[2]["value"] is None
        assert sources["training"] is False


@pytest.mark.asyncio
class TestAnnotatorQueries:
    async def test_stats_return_assigned_task_and_span_counts(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "ann-user-1"
        await _seed_annotator_tasks(engine, schema, user_id, 8, 6)
        await _seed_spans(engine, schema, 45)

        status, body = await _get("annotator", tid, user_id)
        assert status == 200
        s = body["data"]["stats"]
        sources = body["sources"]

        # completed/total, not a bare assigned count
        assert s[0]["value"] == "6/8"
        assert sources["annotations"] is True

    async def test_completion_percentage(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "ann-user-2"
        await _seed_annotator_tasks(engine, schema, user_id, 8, 6)

        status, body = await _get("annotator", tid, user_id)
        assert status == 200
        s = body["data"]["stats"]

        assert s[1]["label"] == "Completion"
        assert s[1]["value"] == "75"
        assert s[1]["unit"] == "%"

    async def test_task_activity_rows(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "ann-user-3"
        await _seed_annotator_tasks(engine, schema, user_id, 4, 2)

        status, body = await _get("annotator", tid, user_id)
        assert status == 200
        rows = body["data"]["pRows"]
        non_placeholder = [r for r in rows if r["title"] not in ("\u2014", "No tasks assigned")]
        assert len(non_placeholder) > 0
        for r in non_placeholder:
            assert r["go"] == "annotation"


@pytest.mark.asyncio
class TestBusinessUserQueries:
    async def test_stats_return_conversation_message_and_feedback_counts(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-shape"
        await _seed_conversations(engine, schema, user_id, conversation_count=3, messages_per=2, up_ratings=2)

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        s = body["data"]["stats"]
        sources = body["sources"]

        assert s[0]["value"] == "3"
        assert s[1]["value"] == "6"
        assert s[2]["value"] == "2"
        assert sources["conversations"] is True
        assert sources["feedback"] is True

    async def test_conversation_activity_rows(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-activity"
        await _seed_conversations(engine, schema, user_id, conversation_count=3, messages_per=1)

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        rows = body["data"]["pRows"]
        non_placeholder = [r for r in rows if r["title"] not in ("\u2014", "No conversations yet")]
        assert len(non_placeholder) > 0
        for r in non_placeholder:
            assert r["go"] == "chat"
            assert r["id"]

    async def test_business_user_side_panel_no_eval_metrics(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-panel"
        await _seed_conversations(engine, schema, user_id, conversation_count=2)
        await _seed_promoted_model(engine, schema, 0.89)

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        d = body["data"]

        assert d["bigUnit"] == ""
        assert d["big"] in ("Online", "Offline")

    async def test_avg_response_time_shows_milliseconds(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-resp-ms"
        await _seed_conversations(engine, schema, user_id, conversation_count=1, messages_per=1)
        async with engine.begin() as conn:
            for ms in (200, 400):
                await conn.execute(
                    text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, response_time_ms) VALUES (:id, 'conv-0', 'assistant', 'reply', :ms)"),
                    {"id": f"asst-{ms}", "ms": ms},
                )

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        resp_time = next(m for m in body["data"]["sideMetrics"] if m["k"] == "resp time")
        assert resp_time["v"] == "300ms"

    async def test_avg_response_time_shows_seconds_above_1000ms(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-resp-s"
        await _seed_conversations(engine, schema, user_id, conversation_count=1, messages_per=1)
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content, response_time_ms) VALUES ('asst-slow', 'conv-0', 'assistant', 'reply', 2500)"),
            )

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        resp_time = next(m for m in body["data"]["sideMetrics"] if m["k"] == "resp time")
        assert resp_time["v"] == "2.5s"

    async def test_avg_response_time_dash_when_no_data(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-resp-none"
        await _seed_conversations(engine, schema, user_id, conversation_count=1, messages_per=1)

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        resp_time = next(m for m in body["data"]["sideMetrics"] if m["k"] == "resp time")
        assert resp_time["v"] == "—"

    async def test_frequently_asked_topics_block_removed(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "biz-user-no-topics"
        await _seed_conversations(engine, schema, user_id, conversation_count=2)

        status, body = await _get("business_user", tid, user_id)
        assert status == 200
        d = body["data"]
        assert d["sideBot"] == ""
        assert d["sideRows"] == []


@pytest.mark.asyncio
class TestRouteDispatch:
    async def test_route_dispatches_db_and_tenant_id_to_all_handlers(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) VALUES ('routedoc-1', 'test-tenant', 'test.pdf', 'uploaded') ON CONFLICT (id) DO NOTHING")
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        sources = body["sources"]
        assert "documents" in sources

    async def test_annotator_handler_receives_user_id(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "specific-annotator"
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) VALUES ('adoc-1', 'test-tenant', 'doc.pdf', 'uploaded') ON CONFLICT (id) DO NOTHING")
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, 'adoc-1', :uid, 'open') ON CONFLICT (id) DO NOTHING"),
                {"id": "task-uid-1", "uid": user_id},
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status) VALUES (:id, 'adoc-1', :uid, 'annotated') ON CONFLICT (id) DO NOTHING"),
                {"id": "task-uid-2", "uid": "other-annotator"},
            )

        status, body = await _get("annotator", tid, user_id)
        assert status == 200
        s = body["data"]["stats"]
        # Only this annotator's task is counted, and it is not complete.
        assert s[0]["value"] == "0/1"

    async def test_sources_map_contains_all_keys(self, engine, tenant_schema):
        tid, schema = tenant_schema

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        sources = body["sources"]
        for key in ("documents", "annotations", "training", "models"):
            assert key in sources


@pytest.mark.asyncio
class TestSystemAdminSchemaFailureRecovery:
    async def test_one_bad_tenant_schema_does_not_blank_out_others(self, engine, setup_database):
        # setup_database already registers several "active" tenants (test-tenant, tenant-b,
        # no-model, no-model-tenant) with no schema ever created for them here, so every one
        # of those per-schema queries already fails before this test's own healthy tenant is
        # reached in the enumeration. This reproduces the real incident shape: several bad
        # schemas failing in a row, followed by a healthy one, on a single shared session.
        healthy_tid = "healthy-schema-tenant"
        healthy_schema = f"tenant_{healthy_tid.replace('-', '_')}"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :name, :slug, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": healthy_tid, "name": "Healthy Tenant", "slug": healthy_tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {healthy_schema}"))
            await conn.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {healthy_schema}.training_jobs (
                        id VARCHAR PRIMARY KEY,
                        tenant_id VARCHAR NOT NULL,
                        status VARCHAR(20) NOT NULL DEFAULT 'queued',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        started_at TIMESTAMPTZ
                    )
                """)
            )
            await conn.execute(
                text(f"""
                    CREATE TABLE IF NOT EXISTS {healthy_schema}.model_versions (
                        id VARCHAR PRIMARY KEY,
                        tenant_id VARCHAR NOT NULL,
                        version INTEGER NOT NULL,
                        metrics JSONB,
                        status VARCHAR(20) DEFAULT 'candidate',
                        promoted_at TIMESTAMPTZ
                    )
                """)
            )
            await conn.execute(
                text(f"""
                    INSERT INTO {healthy_schema}.training_jobs (id, tenant_id, status, created_at)
                    VALUES ('tj-healthy-1', :tid, 'pending_approval', NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"tid": healthy_tid},
            )
            await conn.execute(
                text(f"""
                    INSERT INTO {healthy_schema}.training_jobs (id, tenant_id, status, created_at, started_at)
                    VALUES ('tj-healthy-2', :tid, 'running', NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"tid": healthy_tid},
            )

        try:
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
            assert status == 200
            s = body["data"]["stats"]
            sources = body["sources"]

            pending_approvals = s[2]
            training_jobs_running = s[3]
            assert pending_approvals["value"] == "1"
            assert training_jobs_running["value"] == "1"
            assert sources["training"] is True
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {healthy_schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": healthy_tid})


@pytest.mark.asyncio
class TestSystemAdminActivityFeed:
    async def test_activity_feed_reflects_multi_tenant_audit_events_ordered(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.audit_events (id, actor, role, action, target, kind, tenant_id, created_at) VALUES "
                    "('ae-1', 'admin@x.com', 'system_admin', 'tenant.create', 'tenant-b', 'create', 'tenant-b', NOW() - INTERVAL '2 minutes'),"
                    "('ae-2', 'admin@x.com', 'system_admin', 'user.create', 'user-1', 'create', 'test-tenant', NOW() - INTERVAL '1 minute')"
                )
            )
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        rows = body["data"]["pRows"]
        titles = [r["title"] for r in rows]
        assert titles[0] == "User onboarded"
        assert titles[1] == "Tenant created"
        tenant_ids_seen = {"tenant-b", "test-tenant"}
        assert tenant_ids_seen  # multi-tenant seed data above spans two tenants

    async def test_unmapped_action_shows_humanized_fallback_not_dropped(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.audit_events (id, actor, role, action, target, kind, tenant_id, created_at) VALUES "
                    "('ae-unmapped', 'admin@x.com', 'system_admin', 'tenant_settings.update', 'tenant-b', 'update', 'tenant-b', NOW())"
                )
            )
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        rows = body["data"]["pRows"]
        matches = [r for r in rows if r["title"] == "tenant settings: update"]
        assert len(matches) == 1


@pytest.mark.asyncio
class TestSystemAdminStats:
    async def test_stats_are_active_tenants_users_pending_approvals_training_running(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status) VALUES "
                    "('tu-1', :tid, 'a@x.com', 'x', 'business_user', 'active'),"
                    "('tu-2', :tid, 'b@x.com', 'x', 'business_user', 'suspended')"
                ),
                {"tid": tid},
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, created_at) VALUES "
                     "('tj-p1', :tid, 'pending_approval', NOW())"),
                {"tid": tid},
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, created_at, started_at) VALUES "
                     "('tj-r1', :tid, 'running', NOW(), NOW())"),
                {"tid": tid},
            )
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        s = body["data"]["stats"]
        # Active Tenants: "<active>/<total>" — baseline fixture registers 4 active tenants.
        assert s[0]["value"] == "4/4"
        assert s[0]["sub"] == "+4 in the last 24h"
        assert s[0]["delta"] == ""
        # Active Users: "<active>/<total>"; the seeded users have no created_at, so the
        # 24-hour onboarding count is 0 and the +N lives in the sub, not a header badge.
        assert s[1]["value"] == "1/2"
        assert s[1]["sub"] == "+0 in the last 24h"
        assert s[1]["delta"] == ""
        # Pending Approvals / Training Jobs Running keep their counts but drop their badges.
        assert s[2]["value"] == "1"
        assert s[2]["delta"] == ""
        assert s[3]["value"] == "1"
        assert s[3]["delta"] == ""


@pytest.mark.asyncio
class TestSystemAdminStatMetrics:
    async def test_active_tenants_shows_active_over_total_with_24h_delta(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenants"))
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, created_at) VALUES "
                    "(:id, :name, :slug, 'active', NOW())"
                ),
                {"id": "t-new", "name": "New Tenant", "slug": "new-tenant"},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, created_at) VALUES "
                    "(:id, :name, :slug, 'active', NOW() - INTERVAL '30 days')"
                ),
                {"id": "t-old", "name": "Old Tenant", "slug": "old-tenant"},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, created_at) VALUES "
                    "(:id, :name, :slug, 'inactive', NOW())"
                ),
                {"id": "t-inactive", "name": "Inactive Tenant", "slug": "inactive-tenant"},
            )

        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        tenants = body["data"]["stats"][0]
        assert tenants["label"] == "Active Tenants"
        # 2 active of 3 total; 2 tenants (active-new + inactive-new) created in the last 24h.
        assert tenants["value"] == "2/3"
        assert tenants["delta"] == ""
        assert tenants["sub"] == "+2 in the last 24h"

    async def test_active_users_shows_active_over_total_with_24h_sub(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenant_users"))
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status, created_at) VALUES "
                    "(:id, :tid, :email, :hash, 'business_user', 'active', NOW())"
                ),
                {"id": "tu-active-new", "tid": "test-tenant", "email": "a@x.com", "hash": "x"},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status, created_at) VALUES "
                    "(:id, :tid, :email, :hash, 'business_user', 'active', NOW() - INTERVAL '30 days')"
                ),
                {"id": "tu-active-old", "tid": "test-tenant", "email": "b@x.com", "hash": "x"},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status, created_at) VALUES "
                    "(:id, :tid, :email, :hash, 'business_user', 'suspended', NOW())"
                ),
                {"id": "tu-suspended", "tid": "test-tenant", "email": "c@x.com", "hash": "x"},
            )

        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        users = body["data"]["stats"][1]
        assert users["label"] == "Active Users"
        # 2 active of 3 total; 2 users (active-new + suspended) onboarded in the last 24h.
        assert users["value"] == "2/3"
        assert users["sub"] == "+2 in the last 24h"
        assert users["delta"] == ""

    async def test_active_users_shows_single_onboarded_user_in_sub(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.tenant_users"))
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status, created_at) VALUES "
                    "(:id, :tid, :email, :hash, 'business_user', 'active', NOW())"
                ),
                {"id": "tu-one", "tid": "test-tenant", "email": "a@x.com", "hash": "x"},
            )

        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        users = body["data"]["stats"][1]
        assert users["value"] == "1/1"
        assert users["sub"] == "+1 in the last 24h"
        assert users["delta"] == ""

    async def test_pending_approvals_badge_removed(self, engine, setup_database):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        pending = body["data"]["stats"][2]
        assert pending["label"] == "Pending Approvals"
        assert pending["delta"] == ""
        assert pending.get("dir") is None

    async def test_training_jobs_running_badge_removed(self, engine, setup_database):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        training = body["data"]["stats"][3]
        assert training["label"] == "Training Jobs Running"
        assert training["delta"] == ""
        assert training.get("dir") is None


def test_platform_health_status_healthy_when_all_online():
    assert _platform_health_status("Online", "Online", "Online", "Online", "Online") == "Healthy"


def test_platform_health_status_degraded_when_noncritical_offline():
    assert _platform_health_status("Online", "Offline", "Online", "Online", "Online") == "Degraded"
    assert _platform_health_status("Online", "Online", "Offline", "Online", "Online") == "Degraded"
    assert _platform_health_status("Online", "Online", "Online", "Offline", "Online") == "Degraded"


def test_platform_health_status_critical_when_gateway_or_model_serving_offline():
    assert _platform_health_status("Offline", "Online", "Online", "Online", "Online") == "Critical"
    assert _platform_health_status("Online", "Online", "Online", "Online", "Offline") == "Critical"
    assert _platform_health_status("Offline", "Offline", "Offline", "Offline", "Offline") == "Critical"
    assert _platform_health_status("Offline", "Online", "Online", "Online", "Offline") == "Critical"


class _FakeHealthResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class _FakeHealthClient:
    def __init__(self, responses, delay=0.0, timeout=None):
        self._responses = responses
        self._delay = delay

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        if self._delay:
            await asyncio.sleep(self._delay)
        for prefix, behavior in self._responses.items():
            if url.startswith(prefix):
                if isinstance(behavior, Exception):
                    raise behavior
                return _FakeHealthResponse(behavior)
        return _FakeHealthResponse(200)


@pytest.mark.asyncio
class TestSystemAdminPlatformHealthEndpoint:
    async def test_one_unreachable_noncritical_service_marks_degraded(self, engine, setup_database):
        from src.shared.config import settings
        import functools

        responses = {
            settings.chat_api_url: 200,
            settings.extraction_service_url: 200,
            settings.training_service_url: ConnectionError("unreachable"),
            settings.model_serving_url: 200,
        }
        fake_client = functools.partial(_FakeHealthClient, responses)
        with patch("src.gateway.api.v1.dashboard.httpx.AsyncClient", fake_client):
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        d = body["data"]
        assert d["big"] == "Degraded"
        metrics_by_k = {m["k"]: m["v"] for m in d["sideMetrics"]}
        rows_by_label = {r["label"]: r["val"] for r in d["sideRows"]}
        assert metrics_by_k["chat api"] == "Online"
        assert rows_by_label["Training Service"] == "Offline"
        assert rows_by_label["Model Serving"] == "Online"

    async def test_unreachable_model_serving_marks_critical_even_with_others_online(self, engine, setup_database):
        from src.shared.config import settings
        import functools

        responses = {
            settings.chat_api_url: 200,
            settings.extraction_service_url: 200,
            settings.training_service_url: 200,
            settings.model_serving_url: ConnectionError("unreachable"),
        }
        fake_client = functools.partial(_FakeHealthClient, responses)
        with patch("src.gateway.api.v1.dashboard.httpx.AsyncClient", fake_client):
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        assert body["data"]["big"] == "Critical"

    async def test_health_checks_run_concurrently_and_isolate_failures(self, engine, setup_database):
        from src.shared.config import settings
        import functools

        responses = {
            settings.chat_api_url: 200,
            settings.extraction_service_url: 200,
            settings.training_service_url: TimeoutError("timeout"),
            settings.model_serving_url: 200,
        }
        fake_client = functools.partial(_FakeHealthClient, responses, 0.3)
        with patch("src.gateway.api.v1.dashboard.httpx.AsyncClient", fake_client):
            start = time.monotonic()
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
            elapsed = time.monotonic() - start
        assert status == 200
        # 4 sequential 0.3s checks would take >=1.2s; concurrent fan-out stays near 0.3s
        assert elapsed < 0.9
        metrics_by_k = {m["k"]: m["v"] for m in body["data"]["sideMetrics"]}
        assert metrics_by_k["gateway"] == "Online"


@pytest.mark.asyncio
class TestSystemAdminSchemaExclusion:
    async def test_virtual_system_tenant_excluded_from_schema_iteration(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES ('system', 'System', 'system', 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                )
            )
        try:
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
            assert status == 200
        finally:
            async with engine.begin() as conn:
                await conn.execute(text("DELETE FROM public.tenants WHERE id = 'system'"))

    async def test_tenant_rows_without_schema_excluded_from_aggregates(self, engine, setup_database):
        # setup_database's baseline tenants (tenant-b, no-model, no-model-tenant) have no
        # backing schema created here, so a 200 with zeroed aggregates and no exception is
        # the assertion that missing schemas contribute nothing and don't blow up the request.
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        s = body["data"]["stats"]
        assert s[2]["value"] == "0"
        assert s[3]["value"] == "0"

    async def test_partial_training_aggregate_not_reported_complete(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.training_jobs CASCADE"))
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        assert body["sources"]["training"] is False


@pytest.mark.asyncio
class TestSystemAdminResponseShape:
    async def test_full_response_shape_has_no_model_quality_fields(self, engine, setup_database):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        d = body["data"]
        assert "platform operations" in d["kicker"].lower() or "platform" in d["kicker"].lower()
        assert d["pTitle"] == "Platform Activity"
        assert d["sideTop"] == "Platform Health"
        payload_str = str(body)
        for banned in ("precision", "recall", "f1", "F1", "SLA", "p95", "GPU"):
            assert banned not in payload_str
