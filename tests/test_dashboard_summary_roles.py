import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
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


async def _seed_types(engine, tid, schema, counts: dict, define: bool = True):
    """Creates entity definitions (unless define=False) and the given number of
    spans per entity type, so readiness maths can be asserted exactly.

    public.entity_definitions is not torn down between tests (only the tenant
    schema is), so this clears the tenant's rows first — otherwise readiness
    counts leak across tests."""
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :tid"),
            {"tid": tid},
        )
        await conn.execute(
            text(
                "INSERT INTO " + schema + ".documents (id, tenant_id, filename) "
                "VALUES ('rt-doc', :tid, 'readiness.pdf') ON CONFLICT (id) DO NOTHING"
            ),
            {"tid": tid},
        )
        offset = 0
        for entity_type, n in counts.items():
            if define:
                await conn.execute(
                    text(
                        "INSERT INTO public.entity_definitions (id, tenant_id, name, is_active, version) "
                        "VALUES (:id, :tid, :name, true, 1)"
                    ),
                    {"id": str(uuid.uuid4()), "tid": tid, "name": entity_type},
                )
            for i in range(n):
                await conn.execute(
                    text(
                        "INSERT INTO " + schema + ".spans "
                        "(id, document_id, entity_type, char_start, char_end, text_content) "
                        "VALUES (:id, 'rt-doc', :et, :start, :end, 'x')"
                    ),
                    {
                        "id": "sp-" + entity_type + "-" + str(i),
                        "et": entity_type,
                        "start": offset + i,
                        "end": offset + i + 1,
                    },
                )
            offset += n + 1


async def _seed_tasks(engine, tid, schema, statuses: list, spans_per_doc: int = 0, user_id: str = "test-user"):
    """One document + one annotation task per status, in list order, so
    continue-work precedence and the assigned-task fraction can be asserted."""
    async with engine.begin() as conn:
        for i, status in enumerate(statuses):
            doc_id = "doc-" + str(i)
            await conn.execute(
                text(
                    "INSERT INTO " + schema + ".documents (id, tenant_id, filename) "
                    "VALUES (:did, :tid, :fn)"
                ),
                {"did": doc_id, "tid": tid, "fn": doc_id + ".pdf"},
            )
            await conn.execute(
                text(
                    "INSERT INTO " + schema + ".annotation_tasks "
                    "(id, document_id, annotator_user_id, status, created_at) "
                    "VALUES (:id, :did, :uid, :st, NOW() + (:i * INTERVAL '1 minute'))"
                ),
                {"id": "task-" + str(i), "did": doc_id, "uid": user_id, "st": status, "i": i},
            )
            for j in range(spans_per_doc):
                await conn.execute(
                    text(
                        "INSERT INTO " + schema + ".spans "
                        "(id, document_id, entity_type, char_start, char_end, text_content) "
                        "VALUES (:id, :did, 'PERSON', :start, :end, 'x')"
                    ),
                    {"id": "s-" + str(i) + "-" + str(j), "did": doc_id, "start": j, "end": j + 1},
                )


@pytest_asyncio.fixture(autouse=True)
async def _clear_entity_definitions(engine, setup_database):
    """public.entity_definitions survives the per-test tenant-schema teardown,
    so stale rows would otherwise inflate per-type readiness in later tests.
    Depends on setup_database because that is what creates the public tables."""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id IN ('test-tenant', 'tenant-b')"))
    yield


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

    # ---- annotator: per-entity-type readiness, stat set, continue-work ----

    async def test_annotator_summary_returns_task_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert [s["label"] for s in d["stats"]] == ["Assigned tasks", "Completion"]
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"
        # The tenant-wide span count must not reappear as a personal stat.
        assert "Entities Annotated" not in [s["label"] for s in d["stats"]]

    async def test_annotator_stats_emit_no_placeholder_active_sub(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        assert all(s["sub"] != "active" for s in body["data"]["stats"])

    async def test_annotator_readiness_reflects_weakest_entity_type(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 400, "B_TYPE": 100, "C_TYPE": 0})
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        # mean(min(400/200,1), min(100/200,1), 0) = mean(1.0, 0.5, 0.0) = 50%
        assert d["bar"] == 50.0
        assert "1 of 3" in d["sideMeta"]

    async def test_annotator_readiness_caps_over_annotated_type(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 2000, "B_TYPE": 0})
        status, body = await _get("annotator", tid)
        assert status == 200
        # Uncapped this would read as ready; the cap is what stops one label
        # compensating for a starved one.
        assert body["data"]["bar"] == 50.0
        assert "1 of 2" in body["data"]["sideMeta"]

    async def test_annotator_readiness_includes_zero_span_defined_type(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 10, "NEVER_TAGGED": 0})
        status, body = await _get("annotator", tid)
        assert status == 200
        rows = {r["label"]: r for r in body["data"]["sideRows"]}
        assert "NEVER_TAGGED" in rows
        assert rows["NEVER_TAGGED"]["pct"] == 0
        assert rows["NEVER_TAGGED"]["val"].startswith("0/")

    async def test_annotator_readiness_orders_least_progress_first(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"HIGH": 180, "LOW": 20, "MID": 90})
        status, body = await _get("annotator", tid)
        assert status == 200
        assert [r["label"] for r in body["data"]["sideRows"]] == ["LOW", "MID", "HIGH"]

    async def test_annotator_readiness_excludes_inactive_type_with_no_spans(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 200})
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions (id, tenant_id, name, is_active, version) "
                    "VALUES (:id, :tid, 'LEGACY_FIELD', false, 1)"
                ),
                {"id": str(uuid.uuid4()), "tid": tid},
            )
        status, body = await _get("annotator", tid)
        assert status == 200
        assert body["data"]["bar"] == 100.0
        assert "LEGACY_FIELD" not in [r["label"] for r in body["data"]["sideRows"]]

    async def test_annotator_readiness_includes_spanned_type_with_no_definition(self, engine, tenant_schema):
        """demo-tenant's shape: real spans, no configured entity definitions.
        A definitions-only enumeration would blank the panel for this tenant."""
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"DATE": 105, "MONEY": 105}, define=False)
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert {r["label"] for r in d["sideRows"]} == {"DATE", "MONEY"}
        assert d["big"] != "\u2014"
        assert d["bar"] == 52.5  # mean(105/200, 105/200) = 52.5%

    async def test_annotator_readiness_unavailable_without_types_or_spans(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert d["big"] == "\u2014"
        assert d["bar"] != 100

    async def test_annotator_readiness_at_threshold(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 200, "B_TYPE": 250})
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert d["bar"] == 100.0
        assert "reached" in d["sideMeta"].lower()

    async def test_annotator_readiness_scoped_to_own_tenant(self, engine, tenant_schema):
        """entity_definitions lives in `public` keyed by tenant_id, so that
        filter is the isolation boundary (ADR-001) — spans are already
        physically separated by schema and cannot leak."""
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 100})
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions (id, tenant_id, name, is_active, version) "
                    "VALUES (:id, 'tenant-b', 'OTHER_TENANT_ONLY', true, 1)"
                ),
                {"id": str(uuid.uuid4())},
            )
        status, body = await _get("annotator", tid)
        assert status == 200
        labels = [r["label"] for r in body["data"]["sideRows"]]
        assert labels == ["A_TYPE"]
        assert "OTHER_TENANT_ONLY" not in labels

    async def test_annotator_assigned_tasks_fraction(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["completed"] * 3 + ["pending", "in-progress"])
        status, body = await _get("annotator", tid)
        assert status == 200
        stat = body["data"]["stats"][0]
        assert stat["value"] == "3/5"
        assert "2 remaining" in stat["sub"]

    @pytest.mark.parametrize("not_started", ["pending", "unannotated", "open"])
    async def test_annotator_all_not_started_vocabularies_count(self, engine, tenant_schema, not_started):
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["completed", "completed", not_started])
        status, body = await _get("annotator", tid)
        assert status == 200
        assert body["data"]["stats"][0]["value"] == "2/3"

    async def test_annotator_no_assigned_tasks(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        stat = body["data"]["stats"][0]
        assert stat["value"] == "0/0"
        assert "no tasks assigned" in stat["sub"].lower()

    async def test_annotator_continue_work_resumes_in_progress(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["in-progress"], spans_per_doc=12)
        status, body = await _get("annotator", tid)
        assert status == 200
        cw = body["data"]["continueWork"]
        assert cw is not None
        assert cw["mode"] == "resume"
        assert cw["documentName"] == "doc-0.pdf"
        assert cw["spanCount"] == 12

    async def test_annotator_continue_work_prefers_unstarted_over_completed(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["completed", "pending"], spans_per_doc=1)
        status, body = await _get("annotator", tid)
        assert status == 200
        cw = body["data"]["continueWork"]
        assert cw["mode"] == "start"
        assert cw["status"] == "pending"

    async def test_annotator_continue_work_reviews_completed_when_nothing_left(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["completed", "completed"], spans_per_doc=1)
        status, body = await _get("annotator", tid)
        assert status == 200
        cw = body["data"]["continueWork"]
        assert cw["mode"] == "review"
        assert cw["status"] == "completed"

    async def test_annotator_continue_work_null_without_tasks(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        assert body["data"]["continueWork"] is None

    async def test_annotator_continue_work_orders_by_span_activity(self, engine, tenant_schema):
        """annotation_tasks.updated_at has no writer and is always NULL, so
        ordering must fall through to the document's latest span timestamp."""
        tid, schema = tenant_schema
        await _seed_tasks(engine, tid, schema, ["in-progress", "in-progress"], spans_per_doc=1)
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE " + schema + ".annotation_tasks SET updated_at = NULL"))
            await conn.execute(
                text("UPDATE " + schema + ".spans SET updated_at = NOW() WHERE document_id = 'doc-1'")
            )
            await conn.execute(
                text(
                    "UPDATE " + schema + ".spans SET updated_at = NOW() - INTERVAL '2 days' "
                    "WHERE document_id = 'doc-0'"
                )
            )
        status, body = await _get("annotator", tid)
        assert status == 200
        assert body["data"]["continueWork"]["documentId"] == "doc-1"

    async def test_annotator_continue_work_failure_degrades_only_that_card(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_types(engine, tid, schema, {"A_TYPE": 100})
        with patch(
            "src.gateway.api.v1.dashboard._annotator_continue_work",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert d["continueWork"] is None
        assert d["stats"][0]["value"] is not None
        assert d["sideRows"]

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
