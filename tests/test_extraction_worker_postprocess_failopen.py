"""Covers verification.md rows 48-52.

Post-processing is an optional enhancement over a successful extraction. Every failure
path persists the deterministic result and marks the run degraded; none of them fails the
run, which matters because `run_batch_extraction` declares `max_retries=0` and a failed
run is never retried."""

import os
import uuid

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

import pytest
from sqlalchemy import text

from src.extraction_service import worker as worker_module
from src.extraction_service.services import entity_postprocessor as pp
from src.extraction_service.services.entity_normalizer import NormalizedEntity, canonicalize
from src.extraction_service.services.entity_store import _schema
from src.shared.config import settings

SENTENCE = "Arjun Jayakumar works at Centizen Inc. as a Software Engineer"
TOKENS = SENTENCE.split()


def _token_records(tokens=TOKENS, page_number=0):
    records = []
    offset = 0
    for token in tokens:
        records.append({
            "token": token,
            "page_number": page_number,
            "char_start": offset,
            "char_end": offset + len(token),
        })
        offset += len(token) + 1
    return records


def _entity(entity_type, value, word_start=0, word_end=None, confidence=0.2):
    records = _token_records()
    end = word_end if word_end is not None else word_start
    return NormalizedEntity(
        entity_type=entity_type,
        entity_value=value,
        normalized_value=canonicalize(value),
        confidence=confidence,
        page_number=0,
        char_start=records[word_start]["char_start"],
        char_end=records[end]["char_end"],
        word_index_start=word_start,
        word_index_end=end,
    )


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeHeaders(dict):
    pass


class _FakeHttpResponse:
    """Minimal stand-in for an httpx response. `RateLimitError.__init__` reads
    `response.request`, so it has to be present even though nothing under test uses it."""

    def __init__(self, headers):
        self.headers = _FakeHeaders(headers)
        self.request = None
        self.status_code = 429


@pytest.fixture(autouse=True)
def stable_settings(monkeypatch):
    monkeypatch.setattr(settings, "postprocess_confidence_threshold", 0.60)
    monkeypatch.setattr(settings, "postprocess_context_chars", 1200)
    monkeypatch.setattr(settings, "postprocess_timeout_seconds", 5.0)
    monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")
    monkeypatch.setattr(settings, "postprocess_prompt_version", "v1")


class TestTimeoutKeepsTheDeterministicResult:
    """Row 48."""

    def test_the_entity_survives_a_timeout(self, monkeypatch):
        from openai import APITimeoutError

        entities = [_entity("COMPANY", "Centizen", word_start=4)]

        def _timeout(*args, **kwargs):
            raise pp.PostprocessUnavailable("provider error: request timed out")

        monkeypatch.setattr(pp, "call_postprocessor", _timeout)

        outcome, tokens = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert outcome.entities[0].entity_value == "Centizen"
        assert outcome.entities[0].postprocess_status == "failed"
        assert outcome.degraded is True
        assert tokens == 0

    def test_the_configured_timeout_is_passed_to_the_provider(self, monkeypatch):
        captured = {}

        class _Completions:
            def create(self, **kwargs):
                captured.update(kwargs)
                raise pp.PostprocessUnavailable("stop here")

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())
        monkeypatch.setattr(settings, "postprocess_timeout_seconds", 12.5)

        with pytest.raises(pp.PostprocessUnavailable):
            pp.call_postprocessor("system", "{}")

        assert captured["timeout"] == 12.5


class TestProviderErrorRetriesOnceThenDegrades:
    """Row 49."""

    def test_a_transient_error_is_retried_once_and_then_succeeds(self, monkeypatch):
        from openai import APIError

        attempts = {"count": 0}

        class _Completions:
            def create(self, **kwargs):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise APIError("boom", request=None, body=None)

                class _Message:
                    content = '{"decisions": []}'

                class _Choice:
                    message = _Message()

                class _Usage:
                    total_tokens = 42

                class _Response:
                    choices = [_Choice()]
                    usage = _Usage()

                return _Response()

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())

        body, tokens = pp.call_postprocessor("system", "{}")

        assert attempts["count"] == 2
        assert body == {"decisions": []}
        assert tokens == 42

    def test_a_second_failure_degrades(self, monkeypatch):
        from openai import APIError

        attempts = {"count": 0}

        class _Completions:
            def create(self, **kwargs):
                attempts["count"] += 1
                raise APIError("boom", request=None, body=None)

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())

        with pytest.raises(pp.PostprocessUnavailable):
            pp.call_postprocessor("system", "{}")

        assert attempts["count"] == 2

    def test_unparseable_output_is_not_retried(self, monkeypatch):
        """At temperature 0 the same prompt returns the same shape, so a retry spends
        tokens to fail again."""
        attempts = {"count": 0}

        class _Completions:
            def create(self, **kwargs):
                attempts["count"] += 1

                class _Message:
                    content = "Here are the decisions you asked for!"

                class _Choice:
                    message = _Message()

                class _Response:
                    choices = [_Choice()]
                    usage = None

                return _Response()

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())

        with pytest.raises(pp.PostprocessUnavailable):
            pp.call_postprocessor("system", "{}")

        assert attempts["count"] == 1


class TestRateLimitIsRespectedWithinTheBudget:
    """Row 50."""

    def test_a_short_retry_after_is_waited_out(self, monkeypatch):
        from openai import RateLimitError

        slept: list[float] = []
        attempts = {"count": 0}

        class _Completions:
            def create(self, **kwargs):
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise RateLimitError(
                        "slow down", response=_FakeHttpResponse({"Retry-After": "1"}), body=None
                    )

                class _Message:
                    content = '{"decisions": []}'

                class _Choice:
                    message = _Message()

                class _Response:
                    choices = [_Choice()]
                    usage = None

                return _Response()

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())
        monkeypatch.setattr(pp.time, "sleep", lambda s: slept.append(s))

        body, _ = pp.call_postprocessor("system", "{}")

        assert slept == [1.0]
        assert body == {"decisions": []}

    def test_a_retry_after_beyond_the_budget_degrades_immediately(self, monkeypatch):
        from openai import RateLimitError

        slept: list[float] = []

        class _Completions:
            def create(self, **kwargs):
                raise RateLimitError(
                    "slow down", response=_FakeHttpResponse({"Retry-After": "600"}), body=None
                )

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        monkeypatch.setattr(pp, "_build_client", lambda: _Client())
        monkeypatch.setattr(pp.time, "sleep", lambda s: slept.append(s))
        monkeypatch.setattr(settings, "postprocess_timeout_seconds", 5.0)

        with pytest.raises(pp.PostprocessUnavailable):
            pp.call_postprocessor("system", "{}")

        assert slept == []


class TestTokenBudgetExhaustionDegradesTheRemainder:
    """Row 51."""

    def test_an_exhausted_budget_skips_the_provider_call(self, monkeypatch):
        def _fail(*args, **kwargs):
            raise AssertionError("no call may be made once the budget is exhausted")

        monkeypatch.setattr(pp, "call_postprocessor", _fail)
        entities = [_entity("COMPANY", "Centizen", word_start=4)]

        outcome, tokens = pp.postprocess_document(
            entities, _token_records(), {}, {"COMPANY"}, token_budget_remaining=0
        )

        assert outcome.degraded is True
        assert outcome.entities[0].entity_value == "Centizen"
        assert tokens == 0

    def test_the_budget_reason_is_recorded(self, monkeypatch):
        monkeypatch.setattr(pp, "call_postprocessor", lambda *a, **k: ({"decisions": []}, 0))
        entities = [_entity("COMPANY", "Centizen", word_start=4)]

        outcome, _ = pp.postprocess_document(
            entities, _token_records(), {}, {"COMPANY"}, token_budget_remaining=-5
        )

        assert any("token budget" in reason for reason in outcome.discarded)

    def test_tokens_consumed_are_reported_for_budget_accounting(self, monkeypatch):
        monkeypatch.setattr(pp, "call_postprocessor", lambda *a, **k: (
            {"decisions": [{"candidate_id": 0, "decision": "keep"}]}, 317
        ))
        entities = [_entity("COMPANY", "Centizen", word_start=4)]

        _, tokens = pp.postprocess_document(entities, _token_records(), {}, {"COMPANY"})

        assert tokens == 317


@pytest.mark.asyncio
class TestARunIsNeverFailedByPostprocessingAlone:
    """Row 52 — end to end through the worker."""

    async def _setup(self, engine, sync_engine, tid, schema, doc_id, run_id):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE "{schema}".documents (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'processed', purpose VARCHAR(20) NOT NULL DEFAULT 'query'
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_text_spans (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, span_index INTEGER,
                    text TEXT, char_start INTEGER, page_number INTEGER
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".extraction_runs (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, document_id VARCHAR,
                    model_version VARCHAR, status VARCHAR NOT NULL DEFAULT 'queued',
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL, completed_at TIMESTAMP WITH TIME ZONE,
                    total_documents INTEGER NOT NULL DEFAULT 0, processed_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0, failed_count INTEGER NOT NULL DEFAULT 0,
                    processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
                    postprocess_model TEXT, postprocess_prompt_version TEXT,
                    postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".extracted_entities (
                    id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL, document_id VARCHAR NOT NULL,
                    entity_id VARCHAR, value TEXT, confidence DOUBLE PRECISION, review_status VARCHAR(20)
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER, char_start INTEGER, char_end INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    value_kind TEXT, value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,
                    value_unit TEXT, value_date DATE, value_date_high DATE,
                    source_entity_value TEXT, source_entity_type TEXT,
                    postprocess_status TEXT NOT NULL DEFAULT 'not_applied',
                    postprocess_model TEXT, postprocess_prompt_version TEXT,
                    postprocess_at TIMESTAMPTZ,
                    extraction_schema_version INTEGER NOT NULL DEFAULT 1,
                    occurrence_count INTEGER NOT NULL DEFAULT 1
                )
            """))
            conn.execute(text(f"""
                CREATE TABLE "{schema}".model_versions (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR, version_number INTEGER, status VARCHAR
                )
            """))
            conn.execute(
                text(f'INSERT INTO "{schema}".documents (id, tenant_id, filename, status) VALUES (:id, :tid, :fn, \'processed\')'),
                {"id": doc_id, "tid": tid, "fn": "resume.pdf"},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".document_text_spans (id, document_id, span_index, text, char_start, page_number) '
                     "VALUES (:id, :doc_id, 0, :body, 0, 0)"),
                {"id": "span-0", "doc_id": doc_id, "body": SENTENCE},
            )
            conn.execute(
                text(f'INSERT INTO "{schema}".extraction_runs (id, tenant_id, status, started_at, total_documents, processing_mode) '
                     "VALUES (:id, :tid, 'queued', now(), 1, 'bert_llm_postprocess')"),
                {"id": run_id, "tid": tid},
            )

    async def _teardown(self, engine, sync_engine, tid, schema):
        with sync_engine.begin() as conn:
            for table in ("document_entities", "extracted_entities", "extraction_runs",
                          "model_versions", "document_text_spans", "documents"):
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}".{table}'))
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
        sync_engine.dispose()

    async def test_every_postprocess_call_failing_still_completes_the_run(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine

        tid = f"pp-failopen-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        doc_id, run_id = "doc-pp-1", "run-pp-1"
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema, doc_id, run_id)

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [
                    {"token": "Centizen", "label": "B-COMPANY", "confidence": 0.21, "word_index": 4},
                    {"token": "Inc.", "label": "I-COMPANY", "confidence": 0.22, "word_index": 5},
                ],
                "model_version": "0",
            })

        monkeypatch.setattr(worker_module.requests, "post", mock_post)
        monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda t: "0")
        import src.shared.auth as auth_module
        monkeypatch.setattr(auth_module, "create_access_token", lambda **kwargs: "fake-token")

        def _always_fail(system_prompt, user_payload):
            raise pp.PostprocessUnavailable("provider error: 503")

        monkeypatch.setattr(pp, "call_postprocessor", _always_fail)

        try:
            worker_module.run_batch_extraction.run(tid, run_id, [doc_id], "bert_llm_postprocess")

            with sync_engine.begin() as conn:
                run = conn.execute(text(
                    f'SELECT status, processed_count, failed_count, processing_mode, postprocess_degraded '
                    f'FROM "{schema}".extraction_runs WHERE id = :id'
                ), {"id": run_id}).fetchone()
                rows = conn.execute(text(
                    f'SELECT entity_type, entity_value, postprocess_status FROM "{schema}".document_entities '
                    f'WHERE document_id = :doc_id'
                ), {"doc_id": doc_id}).fetchall()

            assert run.status == "completed"
            assert run.processed_count == 1
            assert run.failed_count == 0
            assert run.processing_mode == "bert_llm_postprocess"
            assert run.postprocess_degraded is True

            assert len(rows) == 1
            assert rows[0].entity_value == "Centizen Inc"
            assert rows[0].postprocess_status == "failed"
        finally:
            await self._teardown(engine, sync_engine, tid, schema)

    async def test_bert_only_mode_makes_no_postprocess_call(self, monkeypatch, engine, setup_database):
        from sqlalchemy import create_engine as sync_create_engine

        tid = f"pp-bertonly-{uuid.uuid4().hex[:8]}"
        schema = _schema(tid)
        doc_id, run_id = "doc-pp-2", "run-pp-2"
        sync_engine = sync_create_engine(settings.database_url_sync)
        await self._setup(engine, sync_engine, tid, schema, doc_id, run_id)

        def mock_post(url, headers=None, json=None, timeout=None):
            return _FakeResponse({
                "predictions": [
                    {"token": "Centizen", "label": "B-COMPANY", "confidence": 0.21, "word_index": 4},
                ],
                "model_version": "0",
            })

        monkeypatch.setattr(worker_module.requests, "post", mock_post)
        monkeypatch.setattr(worker_module, "_get_sync_engine", lambda: sync_engine)
        monkeypatch.setattr(worker_module, "_get_active_model_version", lambda t: "0")
        import src.shared.auth as auth_module
        monkeypatch.setattr(auth_module, "create_access_token", lambda **kwargs: "fake-token")

        def _forbidden(*args, **kwargs):
            raise AssertionError("bert_only must not reach the post-processor")

        monkeypatch.setattr(pp, "call_postprocessor", _forbidden)

        try:
            worker_module.run_batch_extraction.run(tid, run_id, [doc_id], "bert_only")

            with sync_engine.begin() as conn:
                run = conn.execute(text(
                    f'SELECT status, processing_mode, postprocess_degraded, postprocess_model '
                    f'FROM "{schema}".extraction_runs WHERE id = :id'
                ), {"id": run_id}).fetchone()
                row = conn.execute(text(
                    f'SELECT postprocess_status FROM "{schema}".document_entities WHERE document_id = :doc_id'
                ), {"doc_id": doc_id}).fetchone()

            assert run.status == "completed"
            assert run.processing_mode == "bert_only"
            assert run.postprocess_degraded is False
            assert run.postprocess_model is None
            assert row.postprocess_status == "not_applied"
        finally:
            await self._teardown(engine, sync_engine, tid, schema)
