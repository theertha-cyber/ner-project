"""Tests for chat-response-token-streaming. Covers verification.md rows 1-27, 33, 35
(chat-response-streaming capability) and row 33 (chat-api RAG chat endpoint parity).

Node-level tests (`TestGenerationNodeStreaming`, `TestGraphTopologyUnchangedByStreaming`)
follow the direct-node-invocation pattern established in test_chat_graph_topology.py: no
HTTP, no DB, a scripted fake LLM client standing in for `AsyncOpenAI`.

Endpoint-level tests (`TestStreamingEndpoint*`) exercise the real `chat_api` FastAPI app
against the real test database (via the `engine`/`tenant_schema` fixtures, matching
test_chat_api_feedback.py), with the module-level `orchestrator` singleton's streaming
and non-streaming entry points patched to canned implementations. Full end-to-end
retrieval (pgvector search, SQL generation) is exercised nowhere in this test suite —
see test_chat_api_rag.py — so these tests patch at the same boundary rather than
standing up retrieval infrastructure the rest of the suite doesn't have either.
"""
import asyncio
import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient, ASGITransport

from src.shared.auth import create_access_token
from src.chat_api.api.v1 import chat as chat_module
from src.chat_api.graph.builder import build_chat_graph
from src.chat_api.graph.nodes import build_nodes
from src.chat_api.services.rag_orchestrator import RAGOrchestrator, STREAM_DONE
from src.shared.retrieval.tools import build_default_registry

pytestmark = [pytest.mark.verification]


# ---------------------------------------------------------------------------
# Node-level fakes (no HTTP, no DB) — mirrors test_chat_graph_topology.py
# ---------------------------------------------------------------------------

class NoopGuardrails:
    def enforce_sources(self, reply, sources):
        if not sources:
            return "I couldn't find relevant information to answer that question.", []
        return reply, sources


class ScriptedLLMClient:
    """Fake `AsyncOpenAI`-shaped client. Non-streaming calls return `full_reply`.
    Streaming calls (`stream=True`) yield `deltas` one at a time as an async
    generator, optionally raising after `raise_after` deltas and/or sleeping
    `delay` seconds between them."""

    def __init__(self, deltas=None, full_reply=None, raise_after=None, delay=0, empty_choices_chunks=False):
        self.deltas = deltas or []
        self.full_reply = full_reply if full_reply is not None else "".join(self.deltas)
        self.raise_after = raise_after
        self.delay = delay
        # Azure OpenAI (and some OpenAI-compatible backends) interleave chunks
        # with an empty `choices` list — e.g. a trailing content-filter/usage
        # chunk — rather than a choice with an empty delta. When set, one such
        # chunk is emitted before and after every real delta.
        self.empty_choices_chunks = empty_choices_chunks
        self.call_count = 0
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        if kwargs.get("stream"):
            return self._stream()

        class Message:
            content = self.full_reply
            tool_calls = None
        return SimpleNamespace(choices=[SimpleNamespace(message=Message())])

    def _stream(self):
        deltas, raise_after, delay = self.deltas, self.raise_after, self.delay
        empty_choices_chunks = self.empty_choices_chunks

        async def gen():
            if empty_choices_chunks:
                yield SimpleNamespace(choices=[])
            for i, d in enumerate(deltas):
                if delay:
                    await asyncio.sleep(delay)
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=d))])
                if empty_choices_chunks:
                    yield SimpleNamespace(choices=[])
                if raise_after is not None and i + 1 == raise_after:
                    raise RuntimeError("generation failed mid-stream")
        return gen()


def _make_orchestrator(guardrails=None, llm_client=None) -> RAGOrchestrator:
    orchestrator = RAGOrchestrator.__new__(RAGOrchestrator)
    orchestrator.retriever = None
    orchestrator.llm_client = llm_client or ScriptedLLMClient(full_reply="reply")
    orchestrator.llm_model = "fake-model"
    orchestrator.guardrails = guardrails or NoopGuardrails()
    orchestrator.sql_generator = None
    orchestrator.tool_registry = build_default_registry()
    return orchestrator


class TestGenerationNodeStreaming:
    """Covers verification.md rows 8, 9 (task 1.4, 1.5)."""

    async def test_sink_absent_preserves_non_streaming_behaviour(self):
        llm = ScriptedLLMClient(full_reply="complete non-streamed reply")
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        state = {
            "prompt_messages": [{"role": "user", "content": "hi"}],
            "sources": [SimpleNamespace()],
            "token_sink": None,
        }
        result = await nodes["generation"](state)

        assert llm.last_kwargs.get("stream") is not True
        assert result["reply"] == "complete non-streamed reply"

    async def test_sink_present_streams_and_accumulates(self):
        deltas = ["Based", " on", " the documents"]
        llm = ScriptedLLMClient(deltas=deltas)
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        sink: asyncio.Queue = asyncio.Queue()
        state = {
            "prompt_messages": [{"role": "user", "content": "hi"}],
            "sources": [SimpleNamespace()],
            "token_sink": sink,
        }
        result = await nodes["generation"](state)

        received = []
        while not sink.empty():
            received.append(sink.get_nowait())

        assert received == deltas
        assert result["reply"] == "".join(deltas)

    async def test_chunks_with_empty_choices_list_are_skipped_not_indexed(self):
        """Regression: Azure OpenAI interleaves chunks with `choices: []` (e.g. a
        trailing content-filter/usage chunk) rather than a choice with an empty
        delta. Indexing `chunk.choices[0]` unconditionally raises IndexError on
        those chunks and crashes the whole turn."""
        deltas = ["Based", " on", " the documents"]
        llm = ScriptedLLMClient(deltas=deltas, empty_choices_chunks=True)
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        sink: asyncio.Queue = asyncio.Queue()
        state = {
            "prompt_messages": [{"role": "user", "content": "hi"}],
            "sources": [SimpleNamespace()],
            "token_sink": sink,
        }
        result = await nodes["generation"](state)

        received = []
        while not sink.empty():
            received.append(sink.get_nowait())

        assert received == deltas
        assert result["reply"] == "".join(deltas)

    async def test_empty_sources_takes_non_streaming_path_even_with_sink(self):
        """Design Decision 3: source-emptiness is checked before entering the
        streaming branch, so the guardrail's fallback substitution never has to
        contradict already-emitted tokens."""
        llm = ScriptedLLMClient(deltas=["should", " not", " stream"])
        orchestrator = _make_orchestrator(llm_client=llm)
        nodes = build_nodes(orchestrator)

        sink: asyncio.Queue = asyncio.Queue()
        state = {
            "prompt_messages": [{"role": "user", "content": "hi"}],
            "sources": [],
            "token_sink": sink,
        }
        result = await nodes["generation"](state)

        assert sink.empty()
        assert llm.last_kwargs.get("stream") is not True
        assert result["reply"] == "I couldn't find relevant information to answer that question."
        assert result["sources"] == []


class TestGraphTopologyUnchangedByStreaming:
    """Covers verification.md row 10 (task 1.6). Streaming is a runtime `state`
    value only (`token_sink`), never a compile-time topology input, so the compiled
    graph must be byte-for-byte whatever `settings.entity_resolution_enabled`
    already produces today — this test derives the expected shape from that flag
    rather than hardcoding one topology, so it holds regardless of local `.env`."""

    def test_topology_identical_with_streaming_available(self):
        from src.shared.config import settings

        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        graph = compiled.get_graph()

        nodes = set(graph.nodes.keys())
        edges = {(e.source, e.target) for e in graph.edges}

        expected_nodes = {
            "__start__", "__end__", "guardrail", "orchestrator",
            "retrieval_execution", "source_assembly", "prompt_assembly", "generation",
        }
        expected_edges = {
            ("__start__", "guardrail"),
            ("guardrail", "__end__"),
            ("retrieval_execution", "source_assembly"),
            ("source_assembly", "prompt_assembly"),
            ("prompt_assembly", "generation"),
            ("generation", "__end__"),
        }
        if settings.entity_resolution_enabled:
            expected_nodes.add("entity_resolution")
            expected_edges |= {
                ("guardrail", "orchestrator"),
                ("orchestrator", "entity_resolution"),
                ("entity_resolution", "__end__"),
                ("entity_resolution", "retrieval_execution"),
            }
        else:
            expected_edges |= {
                ("guardrail", "orchestrator"),
                ("orchestrator", "retrieval_execution"),
            }

        assert nodes == expected_nodes
        assert edges == expected_edges

    def test_compiled_graph_has_no_cycle(self):
        orchestrator = _make_orchestrator()
        compiled = build_chat_graph(orchestrator)
        graph = compiled.get_graph()

        adjacency: dict[str, list[str]] = {}
        for e in graph.edges:
            adjacency.setdefault(e.source, []).append(e.target)

        visiting, visited = set(), set()

        def has_cycle(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for nxt in adjacency.get(node, []):
                if has_cycle(nxt):
                    return True
            visiting.discard(node)
            visited.add(node)
            return False

        assert not any(has_cycle(n) for n in adjacency)


# ---------------------------------------------------------------------------
# Endpoint-level tests — real chat_api app + real test DB, orchestrator patched
# at the streaming/non-streaming entry-point boundary.
# ---------------------------------------------------------------------------

def auth_header(tenant_id: str, role: str = "business_user", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


class CannedStreamOrchestrator:
    """Patched onto `chat_module.orchestrator` for endpoint tests. Both entry points
    return the same canned 5-tuple; the streaming one additionally pushes `deltas`
    (or raises after `raise_after` of them) onto the sink, mirroring exactly what
    `generation_node`'s streaming branch would do for the same reply."""

    def __init__(self, reply="Based on the documents, there are 5 organizations.",
                 sources=None, pending_clarification=None, answer_kind="answer",
                 model_version=None, deltas=None, raise_after=None, delay=0):
        self.reply = reply
        self.sources = sources if sources is not None else [_fake_citation()]
        self.pending_clarification = pending_clarification
        self.answer_kind = answer_kind
        self.model_version = model_version
        self.deltas = deltas if deltas is not None else ["Based", " on", " the documents, there are 5 organizations."]
        self.raise_after = raise_after
        self.delay = delay
        self.stream_calls = 0
        self.non_stream_calls = 0

    async def execute_with_clarification(self, message, session, schema, tenant_id,
                                          jwt_token=None, conversation_context=None, conversation_id=None):
        self.non_stream_calls += 1
        return (self.reply, self.sources, self.pending_clarification, self.answer_kind, self.model_version)

    async def execute_with_clarification_stream(self, message, session, schema, tenant_id, token_sink,
                                                 jwt_token=None, conversation_context=None, conversation_id=None):
        self.stream_calls += 1
        try:
            for i, delta in enumerate(self.deltas):
                if self.delay:
                    await asyncio.sleep(self.delay)
                await token_sink.put(delta)
                if self.raise_after is not None and i + 1 == self.raise_after:
                    raise RuntimeError("generation failed mid-stream")
        finally:
            await token_sink.put(STREAM_DONE)
        return (self.reply, self.sources, self.pending_clarification, self.answer_kind, self.model_version)


def _fake_citation():
    from src.chat_api.api.v1.schemas import Citation
    return Citation(document_name="report.pdf", document_id="doc-1", source_type="document_chunk", context_snippet="snippet")


def _patch_orchestrator(monkeypatch, fake: CannedStreamOrchestrator):
    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification", fake.execute_with_clarification)
    monkeypatch.setattr(chat_module.orchestrator, "execute_with_clarification_stream", fake.execute_with_clarification_stream)


async def _read_sse_events(resp) -> list[tuple[str, dict]]:
    """Parses an httpx streaming response body into a list of (event, data) pairs."""
    events = []
    event_name, data_lines = None, []
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
        elif line == "" and event_name is not None:
            events.append((event_name, json.loads("".join(data_lines)) if data_lines else {}))
            event_name, data_lines = None, []
    return events


class TestStreamingEndpointHeaders:
    """Covers verification.md row 1 (task 2.6)."""

    async def test_streaming_endpoint_returns_event_stream_headers(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, CannedStreamOrchestrator())

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "How many organizations?", "conversation_id": None}) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                assert resp.headers["cache-control"] == "no-cache"
                assert resp.headers["x-accel-buffering"] == "no"
                await resp.aread()


def _app():
    from src.chat_api.main import app
    return app


class TestStreamingEndpointAuthAndRateLimit:
    """Covers verification.md rows 2, 3 (tasks 2.7, 2.8)."""

    async def test_unauthenticated_request_returns_401_no_stream(self, engine, tenant_schema, monkeypatch):
        _patch_orchestrator(monkeypatch, CannedStreamOrchestrator())
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat/stream", json={"message": "hi", "conversation_id": None})
        assert resp.status_code == 401
        assert not resp.headers.get("content-type", "").startswith("text/event-stream")

    async def test_rate_limited_request_returns_429_no_stream(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        _patch_orchestrator(monkeypatch, CannedStreamOrchestrator())
        from src.chat_api.services.rate_limiter import INTERNAL_RATE_LIMIT, INTERNAL_WINDOW
        chat_module.rate_limiter._buckets[f"internal:{tid}"] = [__import__("time").time()] * INTERNAL_RATE_LIMIT

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            resp = await client.post("/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None})
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert not resp.headers.get("content-type", "").startswith("text/event-stream")
        chat_module.rate_limiter._buckets.pop(f"internal:{tid}", None)


class TestStreamingEventSequence:
    """Covers verification.md rows 4, 7, 33 (tasks 2.9, 2.10)."""

    async def test_tokens_then_done_no_error(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        deltas = ["Based", " on", " the documents"]
        fake = CannedStreamOrchestrator(reply="".join(deltas), deltas=deltas)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "How many organizations?", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        token_events = [e for e in events if e[0] == "token"]
        assert [e[1]["delta"] for e in token_events] == deltas
        assert [e[0] for e in events[len(token_events):]] == ["done"]
        assert "error" not in [e[0] for e in events]

        done_data = events[-1][1]
        assert done_data["reply"] == "".join(t[1]["delta"] for t in token_events)

    async def test_done_matches_non_streaming_body(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(reply="There are 5 organizations.", model_version="v3")
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            non_stream_resp = await client.post("/api/v1/chat", headers=auth_header(tid),
                                                  json={"message": "How many organizations?", "conversation_id": None})
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "How many organizations?", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        non_stream_body = non_stream_resp.json()
        done_data = next(e[1] for e in events if e[0] == "done")

        for key in ("reply", "answer_kind", "model_version", "disclaimer"):
            assert done_data[key] == non_stream_body[key]
        assert [s.get("document_name") for s in done_data["sources"]] == [s.get("document_name") for s in non_stream_body["sources"]]
        assert "conversation_id" in done_data and "conversation_id" in non_stream_body
        assert "message_id" in done_data and "message_id" in non_stream_body


class TestPendingClarificationOmission:
    """Covers verification.md row 6 (task 2.11)."""

    async def test_null_pending_clarification_omitted_from_done(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(pending_clarification=None)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        done_data = next(e[1] for e in events if e[0] == "done")
        assert "pending_clarification" not in done_data


class TestThinkingUntilFirstToken:
    """Covers verification.md rows 11, 12 (task 2.12)."""

    async def test_first_token_arrives_before_done(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(deltas=["slow", " delta"], delay=0.05)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None}) as resp:
                seen_event_before_done = None
                async for event, data in _iter_sse_events_live(resp):
                    if seen_event_before_done is None:
                        seen_event_before_done = event
                    if event == "done":
                        break

        assert seen_event_before_done == "token"


async def _iter_sse_events_live(resp):
    event_name, data_lines = None, []
    async for line in resp.aiter_lines():
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
        elif line == "" and event_name is not None:
            yield event_name, (json.loads("".join(data_lines)) if data_lines else {})
            event_name, data_lines = None, []


class TestNoTokenTerminalPaths:
    """Covers verification.md rows 13, 14, 15, 35 (tasks 2.13, 2.14)."""

    async def test_guardrail_decline_emits_no_tokens(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(
            reply="I can only answer questions about your tenant's documents and the entities extracted from them. I can't help with that.",
            sources=[], answer_kind="out_of_domain", deltas=[],
        )
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "Tell me a joke.", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        assert [e[0] for e in events] == ["done"]
        assert events[0][1]["answer_kind"] == "out_of_domain"

    async def test_clarification_emits_no_tokens(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        pending = {"mention": "John", "candidates": []}
        fake = CannedStreamOrchestrator(
            reply="Which John did you mean?", sources=[], answer_kind="clarification",
            pending_clarification=pending, deltas=[],
        )
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "Tell me about John", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        assert [e[0] for e in events] == ["done"]
        assert events[0][1]["pending_clarification"] == pending
        assert events[0][1]["answer_kind"] == "clarification"

    async def test_empty_sources_emits_no_tokens_and_fallback_reply(self, engine, tenant_schema, monkeypatch):
        """Covers row 35 (chat-api guardrail spec): a turn whose sources come back
        empty must not have streamed any generated text before the fallback."""
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(
            reply="I couldn't find relevant information to answer that question.",
            sources=[], answer_kind="answer", deltas=[],
        )
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        assert [e[0] for e in events] == ["done"]
        assert events[0][1]["reply"] == "I couldn't find relevant information to answer that question."
        assert events[0][1]["sources"] == []


class TestStreamingPersistence:
    """Covers verification.md rows 16, 17 (task 2.15)."""

    async def test_one_assistant_row_with_full_reply(self, engine, tenant_schema, monkeypatch):
        from sqlalchemy import text
        tid, schema = tenant_schema
        deltas = ["Based", " on", " the documents"]
        fake = CannedStreamOrchestrator(reply="".join(deltas), deltas=deltas)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "How many organizations?", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        done_data = next(e[1] for e in events if e[0] == "done")

        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"SELECT content, role FROM {schema}.chat_messages WHERE conversation_id = :cid ORDER BY created_at ASC"),
                {"cid": done_data["conversation_id"]},
            )
            rows = result.fetchall()

        assistant_rows = [r for r in rows if r.role == "assistant"]
        user_rows = [r for r in rows if r.role == "user"]
        assert len(assistant_rows) == 1
        assert len(user_rows) == 1
        assert assistant_rows[0].content == done_data["reply"]

    async def test_reloaded_conversation_preserves_message_order(self, engine, tenant_schema, monkeypatch):
        """Regression: both rows of a turn used to take the column's NOW() default,
        which is transaction_timestamp() and therefore identical for the pair, so
        `ORDER BY created_at` could hand the assistant row back first. That only
        showed after a page refresh, when the UI drops its optimistic order and
        renders whatever GET /conversations/{id} returns."""
        from sqlalchemy import text
        tid, schema = tenant_schema

        conv_id = None
        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            for turn in range(3):
                deltas = [f"answer {turn}"]
                _patch_orchestrator(monkeypatch, CannedStreamOrchestrator(reply="".join(deltas), deltas=deltas))
                async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                          json={"message": f"question {turn}", "conversation_id": conv_id}) as resp:
                    events = await _read_sse_events(resp)
                conv_id = next(e[1] for e in events if e[0] == "done")["conversation_id"]

            detail = await client.get(f"/api/v1/chat/conversations/{conv_id}", headers=auth_header(tid))

        assert detail.status_code == 200
        messages = detail.json()["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"] * 3
        assert [m["content"] for m in messages] == [
            "question 0", "answer 0", "question 1", "answer 1", "question 2", "answer 2",
        ]

        # The stored timestamps must themselves be strictly increasing, so the
        # ordering does not lean on the role tiebreak that protects legacy rows.
        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"SELECT created_at FROM {schema}.chat_messages WHERE conversation_id = :cid ORDER BY created_at ASC"),
                {"cid": conv_id},
            )
            stamps = [r.created_at for r in result.fetchall()]
        assert len(set(stamps)) == len(stamps)

    async def test_failed_stream_persists_nothing(self, engine, tenant_schema, monkeypatch):
        from sqlalchemy import text
        tid, schema = tenant_schema
        fake = CannedStreamOrchestrator(deltas=["partial", " text"], raise_after=2)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        assert [e[0] for e in events] == ["token", "token", "error"]

        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"SELECT id FROM {schema}.chat_messages"),
            )
            rows = result.fetchall()
        assert rows == []


class TestStreamingErrorEvent:
    """Covers verification.md row 18 (task 2.16)."""

    async def test_error_after_two_tokens_no_done(self, engine, tenant_schema, monkeypatch):
        tid, _ = tenant_schema
        fake = CannedStreamOrchestrator(deltas=["one", " two", " three"], raise_after=2)
        _patch_orchestrator(monkeypatch, fake)

        async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as client:
            async with client.stream("POST", "/api/v1/chat/stream", headers=auth_header(tid),
                                      json={"message": "hi", "conversation_id": None}) as resp:
                events = await _read_sse_events(resp)

        assert [e[0] for e in events] == ["token", "token", "error"]
        error_data = events[-1][1]
        assert "code" in error_data and "message" in error_data
        assert "done" not in [e[0] for e in events]
