"""The review queue and its human resolution route.

Covers verification.md rows 8-12.

The human-route tests resolve through the HTTP endpoint rather than by calling
`resolve_prediction` directly. The service function is exercised on its own in
`test_review_outcomes.py`; what these tests are for is the property that a human reviewer's
decision reaches it — including that the route is stamped `human` by the endpoint and not taken
from the request body.

The LLM-route tests (rows 11-12) drive the real Celery task body with a stub provider. Only the
provider is stubbed: the outcome record, the span, and the discard are all the real shared path,
which is what lets row 12 assert that no span exists without an outcome behind it.
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.shared.config import settings
from tests.confidence_review_support import (
    ORG_END,
    ORG_START,
    add_document,
    add_prediction,
    add_run,
    auth_header,
    drop_test_schemas,
    make_tenant,
)


@pytest.fixture
async def engine():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    await drop_test_schemas(engine)


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _queued(engine, **kwargs):
    """A tenant with one queued prediction over `Acme Corp` at 36-45."""
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id)
    pred_id = await add_prediction(engine, tenant, run_id, doc_id, **kwargs)
    return tenant, doc_id, pred_id


async def _outcomes(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT outcome, route, entity_type, char_start, char_end, reviewer, origin, "
                f"       predicted_entity_type, predicted_char_start, predicted_char_end "
                f"FROM {schema}.review_outcomes"
            )
        )
        return result.fetchall()


async def _spans(engine, schema):
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                f"SELECT id, entity_type, char_start, char_end, text_content FROM {schema}.spans "
                "ORDER BY char_start"
            )
        )
        return result.fetchall()


class TestReviewQueueListing:
    """Not a numbered row on its own — the listing is what task 8.1's screen reads, and the
    resolution scenarios below are meaningless if the queue cannot be seen."""

    async def test_only_queued_predictions_are_listed(self, engine):
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)
        await add_prediction(engine, tenant, run_id, doc_id, confidence=0.62, disposition="queued")
        await add_prediction(
            engine, tenant, run_id, doc_id, confidence=0.95, disposition="accepted"
        )

        async with await _client() as client:
            resp = await client.get(
                "/api/v1/review-queue", headers=auth_header(tenant["tid"])
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1, "an auto-accepted prediction is not review-queue work"
        assert [item["confidence"] for item in body["items"]] == [0.62]

    async def test_listing_carries_document_context(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.get(
                "/api/v1/review-queue", headers=auth_header(tenant["tid"])
            )

        item = resp.json()["items"][0]
        assert item["char_start"] == ORG_START
        assert item["char_end"] == ORG_END
        # What the document says at the offsets, which is what the reviewer is actually judging.
        assert item["text_at_offsets"] == "Acme Corp"
        assert "Acme Corp" in item["context"]
        assert item["filename"] == "review-test.txt"


class TestHumanConfirmsPrediction:
    """Row 8."""

    async def test_confirming_records_a_confirmed_outcome_on_the_human_route(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["outcome"] == "confirmed"
        assert resp.json()["route"] == "human"

        rows = await _outcomes(engine, tenant["schema"])
        assert len(rows) == 1
        outcome, route, entity_type, char_start, char_end = rows[0][:5]
        assert outcome == "confirmed"
        assert route == "human"
        # Confirmed means as-is: the outcome carries the prediction's own type and offsets.
        assert (entity_type, char_start, char_end) == ("organization", ORG_START, ORG_END)

    async def test_the_route_is_stamped_not_taken_from_the_body(self, engine):
        """A body claiming the LLM route must not produce an LLM-route outcome.

        The route is the evidence Decision 10 is waiting on — it is what makes LLM-reviewer
        agreement comparable against human-reviewer agreement. A human surface that recorded
        whatever route it was told would make that comparison meaningless.
        """
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed", "route": "llm"},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 200, resp.text
        rows = await _outcomes(engine, tenant["schema"])
        assert rows[0][1] == "human"

    async def test_the_reviewer_is_recorded(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )

        rows = await _outcomes(engine, tenant["schema"])
        assert rows[0][5] == "test-reviewer"
        assert rows[0][6] == "queue"


class TestHumanCorrectsOffsets:
    """Row 9."""

    async def test_correcting_offsets_records_the_corrected_offsets(self, engine):
        """The spec's scenario, at this document's offsets: 36-45 corrected to 36-50, which
        widens `Acme Corp` to `Acme Corp in`."""
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "corrected", "char_start": ORG_START, "char_end": 50},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 200, resp.text
        rows = await _outcomes(engine, tenant["schema"])
        outcome, _, entity_type, char_start, char_end = rows[0][:5]
        assert outcome == "corrected"
        assert (char_start, char_end) == (ORG_START, 50)
        # The type was not part of the correction, so it stays what the model said.
        assert entity_type == "organization"

    async def test_the_prediction_is_kept_alongside_the_correction(self, engine):
        """What the model said survives the correction, so agreement stays measurable after the
        prediction row is discarded."""
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "corrected", "char_start": ORG_START, "char_end": 50},
                headers=auth_header(tenant["tid"]),
            )

        rows = await _outcomes(engine, tenant["schema"])
        predicted_type, predicted_start, predicted_end = rows[0][7:10]
        assert (predicted_type, predicted_start, predicted_end) == (
            "organization",
            ORG_START,
            ORG_END,
        )

    async def test_a_correction_that_changes_nothing_is_rejected(self, engine):
        """A `corrected` outcome identical to the prediction is a confirmation wearing the wrong
        label, and would pollute the corrected-rate with non-corrections."""
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "corrected", "char_start": ORG_START, "char_end": ORG_END},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 422
        assert await _outcomes(engine, tenant["schema"]) == []


class TestReviewerRejectsPrediction:
    """Row 10."""

    async def test_rejecting_records_the_outcome_and_creates_no_span(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "rejected"},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["span_id"] is None

        rows = await _outcomes(engine, tenant["schema"])
        assert len(rows) == 1
        assert rows[0][0] == "rejected"
        assert await _spans(engine, tenant["schema"]) == []

    async def test_rejection_writes_no_negative_training_signal(self, engine):
        """Decision 12: a rejection records an outcome and stops. No span, and in particular no
        explicit `O` span over the rejected region — the reviewer rejected this type at these
        offsets, not every type over that text."""
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "rejected"},
                headers=auth_header(tenant["tid"]),
            )

        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.spans")
            )
            assert result.scalar() == 0
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.span_review_provenance")
            )
            assert result.scalar() == 0


class TestResolutionLifecycle:
    """The retention half of Decision 11, and the shape of a second attempt."""

    async def test_a_resolved_prediction_is_discarded(self, engine):
        """Decision 11's resolution half: the prediction row goes once its information lives in
        an outcome. The outcome is what survives."""
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )

        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.routed_predictions")
            )
            assert result.scalar() == 0
        assert len(await _outcomes(engine, tenant["schema"])) == 1

    async def test_resolving_twice_is_a_404(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            first = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )
            second = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )

        assert first.status_code == 200
        assert second.status_code == 404
        assert len(await _outcomes(engine, tenant["schema"])) == 1

    async def test_an_auto_accepted_prediction_is_not_queue_work(self, engine):
        """It is reachable through an audit draw, which resolves it with `origin='audit'` — not
        through the queue endpoint, which would record it as ordinary review."""
        tenant, doc_id, pred_id = await _queued(engine, confidence=0.95, disposition="accepted")

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "confirmed"},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 409
        assert await _outcomes(engine, tenant["schema"]) == []

    async def test_an_unknown_outcome_is_rejected(self, engine):
        tenant, doc_id, pred_id = await _queued(engine)

        async with await _client() as client:
            resp = await client.post(
                f"/api/v1/review-queue/{pred_id}/resolve",
                json={"outcome": "maybe"},
                headers=auth_header(tenant["tid"]),
            )

        assert resp.status_code == 422
        assert await _outcomes(engine, tenant["schema"]) == []


class TestLLMReviewRoute:
    """Rows 11-12.

    The LLM route is exercised through `run_llm_review_sync` with a stub provider. The stub is
    the provider only — everything downstream of the provider's answer is the real code, which
    is what makes row 12's claim ("no span was written directly by the job") worth asserting:
    the spans these tests find were made by `create_span_from_outcome` or not at all.
    """

    async def _llm_tenant(self, engine, **kwargs):
        tenant = await make_tenant(engine, review_policy="llm")
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)
        pred_id = await add_prediction(engine, tenant, run_id, doc_id, **kwargs)
        return tenant, doc_id, pred_id

    async def test_llm_review_outcome_structure(self, engine):
        """Row 11: the outcome is one of the three, and records the LLM route."""
        from src.annotation_service.services.llm_client import StubLLMClient
        from src.annotation_service.worker import run_llm_review_async

        tenant, doc_id, pred_id = await self._llm_tenant(engine)
        stub = StubLLMClient({"outcome": "confirmed", "reason": "reads as an organisation"})

        result = await run_llm_review_async(tenant["tid"], llm_client=stub)

        assert result["skipped"] is False
        assert result["reviewed"] == 1
        assert stub.call_count == 1

        rows = await _outcomes(engine, tenant["schema"])
        assert len(rows) == 1
        outcome, route = rows[0][0], rows[0][1]
        assert outcome in ("confirmed", "corrected", "rejected")
        assert route == "llm"

    async def test_the_llm_can_correct_offsets(self, engine):
        from src.annotation_service.services.llm_client import StubLLMClient
        from src.annotation_service.worker import run_llm_review_async

        tenant, doc_id, pred_id = await self._llm_tenant(engine)
        stub = StubLLMClient(
            {
                "outcome": "corrected",
                "entity_type": "organization",
                "char_start": ORG_START,
                "char_end": 50,
                "reason": "the boundary excluded a trailing token",
            }
        )

        await run_llm_review_async(tenant["tid"], llm_client=stub)

        rows = await _outcomes(engine, tenant["schema"])
        assert rows[0][0] == "corrected"
        assert (rows[0][3], rows[0][4]) == (ORG_START, 50)
        assert rows[0][1] == "llm"

    async def test_llm_review_does_not_bypass_outcome_path(self, engine):
        """Row 12: every span the job produced came from a recorded outcome.

        Asserted as a join rather than a count: a span written directly by the job would have no
        `span_review_provenance` row pointing at an outcome, so the left join finds it.
        """
        from src.annotation_service.services.llm_client import StubLLMClient
        from src.annotation_service.worker import run_llm_review_async

        tenant, doc_id, pred_id = await self._llm_tenant(engine)
        stub = StubLLMClient({"outcome": "confirmed", "reason": "correct as given"})

        await run_llm_review_async(tenant["tid"], llm_client=stub)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    f"SELECT s.id, o.id, o.route FROM {tenant['schema']}.spans s "
                    f"LEFT JOIN {tenant['schema']}.span_review_provenance p ON p.span_id = s.id "
                    f"LEFT JOIN {tenant['schema']}.review_outcomes o ON o.id = p.outcome_id"
                )
            )
            rows = result.fetchall()

        assert rows, "the job produced a span"
        for span_id, outcome_id, route in rows:
            assert outcome_id is not None, (
                f"span {span_id} has no review outcome behind it — the job wrote it directly"
            )
            assert route == "llm"

    async def test_the_job_contains_no_span_write(self):
        """The structural half of row 12, and of Hallucination Risk 4.

        `create_span_from_outcome` is the only function in this change that inserts into
        `spans`. The LLM job must reach it through `resolve_prediction` and have no write of
        its own — checked by reading the source, because the property is about absence and no
        single run can demonstrate it.

        Scoped to the LLM-review section of `worker.py` rather than the whole module: that file
        also hosts change 1's pre-labeling job, which legitimately writes `suggested_spans`.
        A whole-file grep would fail on that unrelated code and prove nothing about this job.
        """
        import ast
        import pathlib

        def sql_literals(path, only_after=None):
            """Every string literal in the module that is not a docstring.

            Parsed rather than grepped because prose is not code: this file's own comments
            discuss `spans` at length, and a text search cannot tell an explanation of the rule
            from a violation of it. Only string constants can carry SQL.
            """
            source = path.read_text(encoding="utf-8")
            if only_after is not None:
                assert only_after in source, "the section marker this test scopes to has moved"
                source = source[source.index(only_after):]
                # Re-parsed as a fragment: the section is top-level code, so it stands alone.
            tree = ast.parse(source)
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                     ast.ClassDef)):
                    body = getattr(node, "body", None)
                    if body and isinstance(body[0], ast.Expr) and isinstance(
                        body[0].value, ast.Constant
                    ) and isinstance(body[0].value.value, str):
                        docstrings.add(id(body[0].value))
            return [
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ]

        root = pathlib.Path(__file__).resolve().parents[1] / "src"
        worker = root / "annotation_service" / "worker.py"
        llm_review = root / "annotation_service" / "services" / "llm_review.py"

        checked = {
            "worker.py LLM review section": sql_literals(
                worker, only_after="def _tenant_review_policy"
            ),
            "llm_review.py": sql_literals(llm_review),
        }
        for name, literals in checked.items():
            joined = " ".join(literals)
            assert "INSERT INTO" not in joined.upper(), f"{name} contains a direct INSERT"
            assert ".spans" not in joined, f"{name} names the span table in SQL"

        # And it does reach the shared path.
        worker_src = worker.read_text(encoding="utf-8")
        assert "resolve_prediction" in worker_src[worker_src.index("LLM review route"):]

    async def test_a_tenant_on_the_human_policy_is_skipped_without_a_provider_call(self, engine):
        """Decision 10 as shipped: the route exists, is tested, and runs for nobody until a
        tenant is switched to it deliberately."""
        from src.annotation_service.services.llm_client import StubLLMClient
        from src.annotation_service.worker import run_llm_review_async

        tenant = await make_tenant(engine)  # defaults to the human policy
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id)
        await add_prediction(engine, tenant, run_id, doc_id)
        stub = StubLLMClient({"outcome": "confirmed"})

        result = await run_llm_review_async(tenant["tid"], llm_client=stub)

        assert result["skipped"] is True
        assert result["policy"] == "human"
        assert stub.call_count == 0, "no provider call for a tenant that did not opt in"
        assert await _outcomes(engine, tenant["schema"]) == []

    async def test_an_unusable_provider_answer_leaves_the_prediction_queued(self, engine):
        """A prediction the provider could not answer for has not been reviewed. Recording an
        outcome for it would claim otherwise and put an unreviewed span into training data."""
        from src.annotation_service.services.llm_client import StubLLMClient
        from src.annotation_service.worker import run_llm_review_async

        tenant, doc_id, pred_id = await self._llm_tenant(engine)
        stub = StubLLMClient({"outcome": "probably fine"})

        result = await run_llm_review_async(tenant["tid"], llm_client=stub)

        assert result["reviewed"] == 0
        assert result["failed"] == 1
        assert await _outcomes(engine, tenant["schema"]) == []
        async with engine.connect() as conn:
            remaining = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.routed_predictions")
            )
            assert remaining.scalar() == 1, "still queued, for a human or a later retry"
