import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app
from src.gateway.api.v1.dashboard import DashboardSummaryResponse, StatItem, ActivityRow, SideMetric, SideRow, DashboardData


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
        assert d["pTitle"] == "Approval queue"
        assert isinstance(d["pRows"], list) and len(d["pRows"]) == 4
        assert d["sideTop"] == "Platform health"
        assert isinstance(d["sideMetrics"], list) and len(d["sideMetrics"]) == 3
        assert isinstance(d["sideRows"], list)

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
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"

    async def test_business_user_returns_correct_shape(self):
        status, body = await _get("business_user")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Your AI assistant workspace"
        assert len(d["stats"]) == 3
        assert [s["label"] for s in d["stats"]] == ["Conversations", "Messages Sent", "Helpful Responses"]
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
            status = "annotated" if i < completed else "open"
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

        assert s[0]["value"] == "8"
        assert sources["annotations"] is True

    async def test_completion_percentage(self, engine, tenant_schema):
        tid, schema = tenant_schema
        user_id = "ann-user-2"
        await _seed_annotator_tasks(engine, schema, user_id, 8, 6)

        status, body = await _get("annotator", tid, user_id)
        assert status == 200
        s = body["data"]["stats"]

        assert s[3]["value"] == "75"
        assert s[3]["unit"] == "%"

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
        assert s[0]["value"] == "1"

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
                        created_at TIMESTAMPTZ DEFAULT NOW()
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
                    INSERT INTO {healthy_schema}.model_versions (id, tenant_id, version, metrics, status, promoted_at)
                    VALUES ('mv-healthy-1', :tid, 1, :met, 'promoted', NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"tid": healthy_tid, "met": '{"f1": 0.9}'},
            )

        try:
            status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
            assert status == 200
            s = body["data"]["stats"]
            sources = body["sources"]

            pending_approvals = s[2]
            avg_f1 = s[3]
            assert pending_approvals["value"] == "1"
            assert avg_f1["value"] == "90.0"
            assert sources["models"] is True
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {healthy_schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": healthy_tid})
