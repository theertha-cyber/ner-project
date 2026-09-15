"""chat-export / chat-api export field — verification.md scenarios 1-10 and
Hallucination Risks 1-6. The RAG pipeline is patched at the same
`orchestrator.execute_with_clarification` boundary test_chat_api_conversations.py
and test_chat_api_streaming.py use; ContextAssembler's own prompt-budget
truncation is exercised elsewhere (test_context_assembler.py) and is out of
scope here — this module proves that whatever `sql_results` the graph produces
is what gets persisted and exported, independent of `sources`/`admitted_evidence`.
"""
import io
import json
import pytest
from httpx import ASGITransport, AsyncClient
from src.chat_api.api.v1.schemas import Citation
from src.chat_api.services.export_rendering import cap_rows, render_csv, render_xlsx, MAX_EXPORT_ROWS

pytestmark = [pytest.mark.verification]


def _app():
    from src.chat_api.main import app
    return app


def _auth(tenant_id, role="business_user", user_id="test-user"):
    from src.shared.auth import create_access_token
    return {"Authorization": f"Bearer {create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)}"}


def _patch_orchestrator(monkeypatch, reply="Here are the candidates.", sources=None,
                         sql_results=None, retrieval_status=None):
    from src.chat_api.api.v1 import chat as chat_module

    async def fake(message, session, schema, tenant_id, jwt_token=None,
                    conversation_context=None, conversation_id=None):
        return (reply, sources or [], None, "answer", None, retrieval_status, sql_results)

    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification", fake)
    return fake


def _rows(n: int) -> list[dict]:
    return [{"document_id": f"doc-{i}", "name": f"Candidate {i}", "skill": "python"} for i in range(n)]


@pytest.mark.asyncio
class TestExportAvailabilityOnChatResponse:
    """Scenarios 9-10."""

    async def test_response_includes_export_metadata_when_structured_source_succeeded(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=_rows(60))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                      json={"message": "who knows python?", "conversation_id": None})

        assert resp.status_code == 200
        body = resp.json()
        assert body["export"]["row_count"] == 60
        assert set(body["export"]["formats"]) == {"csv", "xlsx"}
        assert body["export"]["message_id"] == body["message_id"]

    async def test_response_omits_export_key_when_no_structured_result_exists(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="document_chunk")],
                             sql_results=None)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                      json={"message": "what does the doc say?", "conversation_id": None})

        assert resp.status_code == 200
        assert "export" not in resp.json()


@pytest.mark.asyncio
class TestRowSnapshotPersistence:
    """Scenarios 7, 8, 16; Hallucination Risk 1."""

    async def test_snapshot_captures_the_full_sql_result_not_a_smaller_admitted_subset(
        self, engine, tenant_schema, monkeypatch,
    ):
        """`sources` here stands in for what the LLM prompt admitted — deliberately
        much smaller than `sql_results` — so this proves persistence follows the
        full result, not whatever the citations/sources list happens to contain."""
        tid, _ = tenant_schema
        _patch_orchestrator(
            monkeypatch,
            sources=[Citation(document_name="r.pdf", source_type="sql")],  # 1 citation
            sql_results=_rows(250),  # 250 underlying rows
        )

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                      json={"message": "who knows python?", "conversation_id": None})

        body = resp.json()
        assert len(body["sources"]) == 1
        assert body["export"]["row_count"] == 250

    async def test_no_snapshot_created_when_structured_retrieval_unused(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="document_chunk")],
                             sql_results=None)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "what does the doc say?", "conversation_id": None})
            conv_id = post_resp.json()["conversation_id"]
            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))
            message_id = next(m["id"] for m in detail.json()["messages"] if m["role"] == "assistant")

            export_resp = await client.get(
                f"/api/v1/chat/messages/{message_id}/export?format=csv", headers=_auth(tid),
            )

        assert export_resp.status_code == 404

    async def test_no_snapshot_created_when_structured_retrieval_matched_zero_rows(
        self, engine, tenant_schema, monkeypatch,
    ):
        """Found during live testing: a naive `sql_results is not None` check
        persists an empty, useless snapshot whenever the SQL generator's LLM
        targets an empty/wrongly-named relation but still produces a query that
        validates and executes cleanly — just against nothing. `sql_results = []`
        (validated, ran, matched nothing) must be treated the same as
        `sql_results = None` (never ran), not as "succeeded with 0 rows"."""
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=[])

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "how many candidates do we have?", "conversation_id": None})

            assert "export" not in post_resp.json()

            conv_id = post_resp.json()["conversation_id"]
            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))
            message_id = next(m["id"] for m in detail.json()["messages"] if m["role"] == "assistant")

            export_resp = await client.get(
                f"/api/v1/chat/messages/{message_id}/export?format=csv", headers=_auth(tid),
            )

        assert export_resp.status_code == 404


@pytest.mark.asyncio
class TestConversationHistoryRetainsExportAvailability:
    """Scenario 15 — found during implementation: without this, a message's file
    card would vanish on page reload/conversation switch (design.md Decision 3
    sibling finding)."""

    async def test_reloaded_conversation_carries_export_metadata_for_past_snapshot(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=_rows(60))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "who knows python?", "conversation_id": None})
            conv_id = post_resp.json()["conversation_id"]

            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))

        assistant_msg = next(m for m in detail.json()["messages"] if m["role"] == "assistant")
        assert assistant_msg["export"]["row_count"] == 60
        assert set(assistant_msg["export"]["formats"]) == {"csv", "xlsx"}

    async def test_reloaded_message_without_snapshot_has_null_export(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="document_chunk")],
                             sql_results=None)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "what does the doc say?", "conversation_id": None})
            conv_id = post_resp.json()["conversation_id"]

            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))

        assistant_msg = next(m for m in detail.json()["messages"] if m["role"] == "assistant")
        assert assistant_msg["export"] is None


class TestOrchestratorSurfacesFullSqlResults:
    """Hallucination Risk 1, at the orchestrator boundary: proves
    `execute_with_clarification`'s 7th return value is the graph's raw
    `sql_results`, not something derived from `admitted_evidence`/`sources`."""

    @pytest.mark.asyncio
    async def test_returns_state_sql_results_not_admitted_evidence(self, monkeypatch):
        from src.chat_api.services.rag_orchestrator import RAGOrchestrator

        orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)

        class _FakeAdmitted:
            rows = _rows(40)  # deliberately smaller than sql_results below

        async def fake_run_graph(*args, **kwargs):
            return {
                "reply": "answer",
                "sources": [],
                "sql_results": _rows(250),
                "admitted_evidence": _FakeAdmitted(),
            }

        monkeypatch.setattr(orchestrator, "_run_graph", fake_run_graph)

        result = await orchestrator.execute_with_clarification(
            "who knows python?", session=None, schema="tenant_x", tenant_id="x",
        )
        sql_results = result[-1]
        assert sql_results is not None
        assert len(sql_results) == 250


@pytest.mark.asyncio
class TestExportEndpoint:
    """Scenarios 1-6."""

    async def test_export_returns_valid_csv(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        rows = _rows(250)
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=rows)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "who knows python?", "conversation_id": None})
            message_id = post_resp.json()["message_id"]

            resp = await client.get(f"/api/v1/chat/messages/{message_id}/export?format=csv",
                                     headers=_auth(tid))

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip("\r\n").split("\r\n")
        assert len(lines) == 251  # header + 250 rows
        assert "doc-0" in lines[1]

    async def test_export_unavailable_for_message_with_no_structured_result(
        self, engine, tenant_schema, monkeypatch,
    ):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="document_chunk")],
                             sql_results=None)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "what does the doc say?", "conversation_id": None})
            conv_id = post_resp.json()["conversation_id"]
            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=_auth(tid))
            message_id = next(m["id"] for m in detail.json()["messages"] if m["role"] == "assistant")

            resp = await client.get(f"/api/v1/chat/messages/{message_id}/export?format=csv",
                                     headers=_auth(tid))

        assert resp.status_code == 404

    async def test_export_rejects_request_from_non_owning_user(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=_rows(10))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid, user_id="user-a"),
                                           json={"message": "who knows python?", "conversation_id": None})
            message_id = post_resp.json()["message_id"]

            resp = await client.get(f"/api/v1/chat/messages/{message_id}/export?format=csv",
                                     headers=_auth(tid, user_id="user-b"))

        assert resp.status_code == 404

    async def test_export_without_authentication_returns_401(self, engine, tenant_schema):
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.get("/api/v1/chat/messages/nonexistent/export?format=csv")

        assert resp.status_code == 401

    async def test_export_returns_valid_xlsx(self, engine, tenant_schema, monkeypatch):
        from openpyxl import load_workbook

        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=_rows(40))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "who knows python?", "conversation_id": None})
            message_id = post_resp.json()["message_id"]

            resp = await client.get(f"/api/v1/chat/messages/{message_id}/export?format=xlsx",
                                     headers=_auth(tid))

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        workbook = load_workbook(io.BytesIO(resp.content))
        sheet = workbook.active
        assert sheet.max_row == 41  # header + 40 rows

    async def test_unsupported_format_returns_422(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=_rows(5))

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            post_resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                           json={"message": "who knows python?", "conversation_id": None})
            message_id = post_resp.json()["message_id"]

            resp = await client.get(f"/api/v1/chat/messages/{message_id}/export?format=pdf",
                                     headers=_auth(tid))

        assert resp.status_code == 422


class TestExportRowDataNeverInlinedInChatResponse:
    """Hallucination Risk 2."""

    @pytest.mark.asyncio
    async def test_response_body_contains_no_row_array(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        rows = _rows(5)
        _patch_orchestrator(monkeypatch, sources=[Citation(document_name="r.pdf", source_type="sql")],
                             sql_results=rows)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat", headers=_auth(tid),
                                      json={"message": "who knows python?", "conversation_id": None})

        raw = resp.text
        assert set(resp.json()["export"].keys()) == {"message_id", "row_count", "formats"}
        # None of the actual row payload leaked into the body anywhere else.
        for row in rows:
            assert row["document_id"] not in raw


class TestExportOwnershipCheckIsStructural:
    """Hallucination Risk 3, distinct from scenario 3's black-box HTTP test: confirms
    the ownership check is structurally a JOIN filtered by `user_id` (so it happens
    at the database layer, before any row data is fetched) rather than, say, an
    in-Python comparison applied after the data was already read."""

    def test_export_query_joins_conversations_filtered_by_user_id(self):
        import inspect
        from src.chat_api.api.v1 import chat as chat_module

        source = inspect.getsource(chat_module.export_message)
        assert "JOIN" in source.upper()
        assert "conversations" in source
        assert "c.user_id = :uid" in source


class TestConversationHistoryExcludesExportRows:
    """Hallucination Risk 4: the conversation-history endpoint may select the
    small `export_row_count` integer (needed for scenario 15's file-card-on-
    reload behaviour) but must NEVER select the bulky `export_rows` JSONB
    snapshot — a source-level guard against a shared-query regression, since a
    DB-level test can't distinguish "column not selected" from "column selected
    but not serialized" as reliably as reading the SQL."""

    def test_get_conversation_query_does_not_select_export_rows_blob(self):
        import inspect
        from src.chat_api.api.v1 import chat as chat_module

        source = inspect.getsource(chat_module.get_conversation)
        assert "m.export_rows" not in source
        assert "export_row_count" in source  # intentionally selected — scenario 15


class TestFormulaInjectionMitigation:
    """Hallucination Risk 5."""

    def test_csv_neutralizes_leading_formula_trigger_characters(self):
        rows = [{"name": "=cmd|' /C calc'!A1", "skill": "+SUM(1,1)"}]
        csv_bytes = render_csv(rows)
        text = csv_bytes.decode("utf-8")
        data_line = text.strip().split("\r\n")[1]
        assert not data_line.startswith("=")
        assert "'=cmd" in data_line
        assert "'+SUM" in data_line

    def test_xlsx_neutralizes_leading_formula_trigger_characters(self):
        from openpyxl import load_workbook

        rows = [{"name": "=cmd|' /C calc'!A1"}]
        xlsx_bytes = render_xlsx(rows)
        workbook = load_workbook(io.BytesIO(xlsx_bytes))
        sheet = workbook.active
        cell_value = sheet.cell(row=2, column=1).value
        assert cell_value.startswith("'")
        assert not cell_value.startswith("=")

    def test_values_not_starting_with_trigger_characters_are_untouched(self):
        rows = [{"name": "Jane Doe", "skill": "python"}]
        csv_bytes = render_csv(rows)
        assert "Jane Doe" in csv_bytes.decode("utf-8")


class TestSnapshotRowCap:
    """Hallucination Risk 6."""

    def test_cap_rows_truncates_to_max_export_rows(self):
        rows = _rows(1500)
        capped = cap_rows(rows)
        assert len(capped) == MAX_EXPORT_ROWS == 1000

    def test_cap_rows_passes_through_smaller_result_unchanged(self):
        rows = _rows(10)
        assert cap_rows(rows) == rows

    def test_cap_rows_handles_none_and_empty(self):
        assert cap_rows(None) == []
        assert cap_rows([]) == []
