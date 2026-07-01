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
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Pipeline activity"
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
        assert d["kicker"] == "Extraction intelligence"
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Recent extractions"
        assert d["sideTop"] == "Active model"

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
                text(f"INSERT INTO {schema}.training_jobs (id, tenant_id, status, created_at) VALUES (:id, :tid, 'completed', NOW()) ON CONFLICT (id) DO NOTHING"),
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


async def _seed_extractions(engine, schema: str, doc_count: int = 25, entity_count: int = 340, auto_cleared: int = 200):
    async with engine.begin() as conn:
        for i in range(doc_count):
            doc_id = f"bd-{i}"
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, 'processed') ON CONFLICT (id) DO NOTHING"),
                {"id": doc_id, "tid": "test-tenant", "fn": f"report-{i}.pdf"},
            )
        run_id = "er-1"
        await conn.execute(
            text(f"INSERT INTO {schema}.extraction_runs (id, tenant_id, status, started_at) VALUES (:id, :tid, 'completed', NOW()) ON CONFLICT (id) DO NOTHING"),
            {"id": run_id, "tid": "test-tenant"},
        )
        for i in range(entity_count):
            rs = "auto_cleared" if i < auto_cleared else "unreviewed"
            conf = 0.5 + (i / entity_count) * 0.5
            doc_id = f"bd-{i % doc_count}"
            await conn.execute(
                text(f"INSERT INTO {schema}.extracted_entities (id, run_id, entity_id, value, confidence, review_status, document_id) VALUES (:id, :rid, :eid, :val, :conf, :rs, :did) ON CONFLICT (id) DO NOTHING"),
                {"id": f"ee-{i}", "rid": run_id, "eid": "PERSON_NAME", "val": "John", "conf": conf, "rs": rs, "did": doc_id},
            )


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

        expected_pct = f"{9 / 15 * 100:.0f}"
        assert s[1]["value"] == expected_pct

        expected_f1 = f"{0.872 * 100:.1f}"
        assert s[2]["value"] == expected_f1

        assert s[3]["value"] == "2"

    async def test_annotation_progress_calculates_correctly(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 20, 12)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]

        assert s[1]["value"] == "60"
        assert s[1]["unit"] == "%"

    async def test_active_model_f1_from_promoted_model(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_docs(engine, schema, 5)
        await _seed_promoted_model(engine, schema, 0.872)

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        s = body["data"]["stats"]

        assert s[2]["value"] == "87.2"

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

        assert s[3]["value"] is None
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
    async def test_stats_return_extraction_counts_and_confidence(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_extractions(engine, schema, 25, 340, 200)

        status, body = await _get("business_user", tid)
        assert status == 200
        s = body["data"]["stats"]
        sources = body["sources"]

        assert s[0]["value"] == "25"
        assert s[1]["value"] == "340"
        assert sources["extraction"] is True

    async def test_auto_cleared_percentage(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_extractions(engine, schema, 25, 340, 200)

        status, body = await _get("business_user", tid)
        assert status == 200
        s = body["data"]["stats"]

        expected = f"{200 / 340 * 100:.1f}"
        assert s[3]["value"] == expected
        assert s[3]["unit"] == "%"

    async def test_extraction_activity_rows(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_extractions(engine, schema, 3, 10, 5)

        status, body = await _get("business_user", tid)
        assert status == 200
        rows = body["data"]["pRows"]
        non_placeholder = [r for r in rows if r["title"] not in ("\u2014", "No extractions yet")]
        assert len(non_placeholder) > 0
        for r in non_placeholder:
            assert r["go"] == "extractions"

    async def test_business_user_side_panel_active_model(self, engine, tenant_schema):
        tid, schema = tenant_schema
        await _seed_extractions(engine, schema, 5, 20)
        await _seed_promoted_model(engine, schema, 0.89)

        status, body = await _get("business_user", tid)
        assert status == 200
        d = body["data"]

        expected_f1 = f"{0.89 * 100:.1f}"
        assert d["big"] == expected_f1
        assert d["bigUnit"] == "eval F1"


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
