from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app


def auth_header(tenant_id: str, role: str = "tenant_admin", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _get(role: str, tenant_id: str = "test-tenant", user_id: str = "test-user") -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/summary", headers=auth_header(tenant_id, role, user_id))
        return resp.status_code, resp.json() if resp.text else {}


@pytest.mark.asyncio
class TestDashboardSummaryRoles:
    async def test_system_admin_summary_returns_role_specific_data(self, engine, setup_database):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Platform control plane"
        assert len(d["stats"]) == 4
        assert [s["label"] for s in d["stats"]] == [
            "Active Tenants", "Active Users", "Pending Approvals", "Training Jobs Running",
        ]
        assert d["pTitle"] == "Platform Activity"
        assert d["sideTop"] == "Platform Health"
        assert d["big"] in ("Healthy", "Degraded", "Critical")

    async def test_tenant_admin_summary_returns_pipeline_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        assert len(d["stats"]) == 3
        assert d["pTitle"] == "Recent Activity"
        assert len(d["pRows"]) == 4
        assert d["sideTop"] == "Active model"

    async def test_annotator_summary_returns_task_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert len(d["stats"]) == 3
        assert d["stats"][1]["label"] == "Entities Annotated"
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"

    async def test_annotator_dataset_readiness_shows_progress(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename) VALUES ('doc-1', :tid, 'f.pdf')"),
                {"tid": tid},
            )
            for i in range(113):
                await conn.execute(
                    text(
                        f"""
                        INSERT INTO {schema}.spans
                            (id, document_id, entity_type, char_start, char_end, text_content)
                        VALUES (:id, 'doc-1', 'PERSON', :start, :end, 'x')
                        """
                    ),
                    {"id": f"span-{i}", "start": i, "end": i + 1},
                )

        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert d["bar"] == 22.6
        assert "387" in d["sideMeta"]
        assert "needed" in d["sideMeta"].lower()
        assert "500" in d["sideBot"]

    async def test_annotator_dataset_readiness_at_threshold(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename) VALUES ('doc-1', :tid, 'f.pdf')"),
                {"tid": tid},
            )
            for i in range(500):
                await conn.execute(
                    text(
                        f"""
                        INSERT INTO {schema}.spans
                            (id, document_id, entity_type, char_start, char_end, text_content)
                        VALUES (:id, 'doc-1', 'PERSON', :start, :end, 'x')
                        """
                    ),
                    {"id": f"span-{i}", "start": i, "end": i + 1},
                )

        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert d["bar"] == 100
        assert "needed" not in d["sideMeta"].lower()

    async def test_business_user_summary_returns_conversation_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("business_user", tid, user_id="biz-user-1")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Your AI assistant workspace"
        assert [s["label"] for s in d["stats"]] == ["Conversations", "Messages Sent", "Responses Marked Helpful"]
        assert d["pTitle"] == "Recent Conversations"
        assert d["sideTop"] == "AI Assistant Status"
        assert d["sideBot"] == ""
        assert d["sideRows"] == []
        assert "eval F1" not in d["bigUnit"]
        assert set(body["sources"].keys()) >= {"conversations", "feedback", "assistant_health"}

    async def test_business_user_summary_scopes_to_own_conversations(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES ('conv-mine', :tid, 'biz-user-1', 'How do I export invoices')"),
                {"tid": tid},
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.conversations (id, tenant_id, user_id, title) VALUES ('conv-other', :tid, 'biz-user-2', 'Refund policy question')"),
                {"tid": tid},
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content) VALUES ('msg-mine-1', 'conv-mine', 'user', 'How do I export invoices?')"),
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content) VALUES ('msg-mine-2', 'conv-mine', 'assistant', 'Here is how...')"),
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_messages (id, conversation_id, role, content) VALUES ('msg-other-1', 'conv-other', 'user', 'What is the refund policy?')"),
            )
            await conn.execute(
                text(f"INSERT INTO {schema}.chat_message_feedback (id, message_id, tenant_id, user_id, rating) VALUES ('fb-mine', 'msg-mine-2', :tid, 'biz-user-1', 'up')"),
                {"tid": tid},
            )

        status, body = await _get("business_user", tid, user_id="biz-user-1")
        assert status == 200
        d = body["data"]
        assert d["stats"][0]["value"] == "1"  # Conversations — only mine
        assert d["stats"][1]["value"] == "1"  # Messages Sent — only my user-role message
        assert d["stats"][2]["value"] == "1"  # Helpful Responses — only my up-rating
        assert len(d["pRows"]) == 4
        first_row = d["pRows"][0]
        assert first_row["title"] == "How do I export invoices"
        assert first_row["go"] == "chat"
        assert first_row["id"] == "conv-mine"

    async def test_unavailable_training_service_returns_null_values(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.training_jobs CASCADE"))

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        training_stat = d["stats"][2]
        assert training_stat["value"] is None
        assert body["sources"]["training"] is False

    async def test_business_user_summary_shows_online_when_chat_api_healthy(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        with patch(
            "src.gateway.api.v1.dashboard._fetch_assistant_health",
            new=AsyncMock(return_value=("Online", "12:00:00", True)),
        ):
            status, body = await _get("business_user", tid, user_id="biz-user-1")
        assert status == 200
        d = body["data"]
        assert d["sideMeta"] == "Online"
        assert body["sources"]["assistant_health"] is True

    async def test_business_user_summary_shows_offline_when_chat_api_unreachable(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        with patch(
            "src.gateway.api.v1.dashboard._fetch_assistant_health",
            new=AsyncMock(return_value=("Offline", "12:00:00", False)),
        ):
            status, body = await _get("business_user", tid, user_id="biz-user-1")
        assert status == 200
        d = body["data"]
        assert d["sideMeta"] == "Offline"
        assert body["sources"]["assistant_health"] is False

    async def test_unauthenticated_request_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    async def test_tenant_admin_workspace_overview_copy(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        assert d["title"] == "Workspace overview."
        assert "pipeline" not in d["line"].lower()
        assert "processing" not in d["line"].lower()
        assert d["pTitle"] == "Recent Activity"
        assert len(d["pRows"]) == 4
        for row in d["pRows"]:
            assert row["icon"] != ""
            assert row["time"] != ""

    async def test_tenant_admin_active_model_card_shows_deployment_info_only(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        with patch(
            "src.gateway.api.v1.dashboard._fetch_active_model",
            new=AsyncMock(return_value={
                "run_name": "run-003-20260805",
                "version_number": 3,
                "promoted_at": "2026-08-05T10:00:00Z",
                "metrics": {"eval_f1": 0.87, "eval_precision": 0.9, "eval_recall": 0.85, "eval_loss": 0.1},
            }),
        ):
            status, body = await _get("tenant_admin", tid)
        assert status == 200
        active_model = body["data"]["activeModel"]
        assert active_model["name"] == "run-003-20260805"
        assert active_model["status"] == "active"
        assert active_model["version"] == "v3"
        assert active_model["deployedAt"] == "5 Aug 2026"
        # deployment-only: no eval metric keys leak into the activeModel payload
        assert set(active_model.keys()) == {"name", "status", "version", "deployedAt"}

    async def test_tenant_admin_active_model_card_null_when_no_model_deployed(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        with patch(
            "src.gateway.api.v1.dashboard._fetch_active_model",
            new=AsyncMock(return_value=None),
        ):
            status, body = await _get("tenant_admin", tid)
        assert status == 200
        assert body["data"]["activeModel"] is None

    async def test_tenant_admin_activity_pads_placeholders(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        assert len(d["pRows"]) == 4
        assert all(row["title"] == "—" for row in d["pRows"])

    async def test_tenant_admin_business_user_added_event(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status) "
                    "VALUES ('biz-added-1', :tid, 'biz@example.com', 'x', 'business_user', 'active')"
                ),
                {"tid": tid},
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        matches = [r for r in rows if r["title"] == "Business User added"]
        assert len(matches) == 1
        assert matches[0]["go"] == "users"

    async def test_tenant_admin_annotator_added_event(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status) "
                    "VALUES ('ann-added-1', :tid, 'ann@example.com', 'x', 'annotator', 'active')"
                ),
                {"tid": tid},
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        matches = [r for r in rows if r["title"] == "Annotator added"]
        assert len(matches) == 1
        assert matches[0]["go"] == "users"

    async def test_tenant_admin_model_deployment_event(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.model_versions (id, tenant_id, version, status, promoted_at) "
                    "VALUES ('mv-promoted-1', :tid, 1, 'promoted', NOW())"
                ),
                {"tid": tid},
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        matches = [r for r in rows if r["title"] == "Model deployment"]
        assert len(matches) == 1
        assert matches[0]["go"] == "models"

    async def test_tenant_admin_training_failure_event(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, failed_at) "
                    "VALUES ('tj-failed-1', :tid, 'failed', NOW())"
                ),
                {"tid": tid},
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        matches = [r for r in rows if r["title"] == "Model training failure"]
        assert len(matches) == 1
        assert matches[0]["go"] == "training"
        assert matches[0]["tk"] == "failed"

    async def test_tenant_admin_curated_activity_excludes_raw_rows(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            for i in range(50):
                await conn.execute(
                    text(
                        f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) "
                        "VALUES (:id, :tid, :fn, 'uploaded')"
                    ),
                    {"id": f"raw-doc-{i}", "tid": tid, "fn": f"raw-doc-{i}.pdf"},
                )
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, completed_at) "
                    "VALUES ('tj-completed-1', :tid, 'completed', NOW())"
                ),
                {"tid": tid},
            )

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        assert len(rows) == 4
        assert not any(r["title"] == "Document upload" for r in rows)
        assert any(r["title"] == "Model training completed" for r in rows)
