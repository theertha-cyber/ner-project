"""The retraining decision surface.

Covers verification.md rows 6-9.

Row 8 is the one with a wrong answer that looks right. A tenant with no trained model has zero
accumulation in the arithmetic sense, and returning that zero would be indistinguishable from a
tenant that has just retrained and seen nothing new since — the opposite situation, and the one
where doing nothing is correct. The test asserts the distinct state and asserts the absence of
the zero, because only the second half catches a response that reports both.

Row 9 is checked structurally as well as behaviourally. "Not compared against the readiness
threshold" is an absence, and absence is not observable in a response body: the surface could
report an unlabelled figure it had quietly compared to ADR-010's per-type threshold and look
identical. So the module is parsed for any import or mention of that threshold.
"""

import os
import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.shared.config import settings
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    add_training_job,
    auth_header,
    drop_test_schemas,
    make_tenant,
    review_spans,
)

pytestmark = pytest.mark.verification


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


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _decision(tenant) -> dict:
    async with _client() as client:
        resp = await client.get(
            "/api/v1/retraining-decision", headers=auth_header(tenant["tid"])
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestSurfaceReportsAccumulationAndVersion:
    """Row 6."""

    async def test_surface_reports_accumulation_and_version(self, engine):
        """The figure and the version it is a delta against, together.

        Together matters: a count with no version is not a delta, it is a total, and the two
        answer different questions.
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(_client, engine, tenant, doc_id, run_id, 9)

        decision = await _decision(tenant)

        assert decision["spans_accumulated"] == 9
        assert decision["serving_model_version"] == "3"
        assert decision["has_trained_model"] is True
        assert decision["training_run_in_flight"] is False

    async def test_in_flight_run_is_reported(self, engine):
        """tasks.md 1.5: the figure is stale while a run executes, and the surface says so."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(_client, engine, tenant, doc_id, run_id, 2)
        await add_training_job(engine, tenant, status="running")

        decision = await _decision(tenant)

        assert decision["training_run_in_flight"] is True
        assert "consumed only when a run completes" in decision["in_flight_detail"]


class TestAccumulationBrokenDownPerEntityType:
    """Row 7."""

    async def test_accumulation_broken_down_per_entity_type(self, engine):
        """The spec's 120/14 split at a smaller scale, with the same shape.

        The breakdown is the whole reason this surface is more than a number: 11 spans all of
        one type and 11 spread over two are the same total and different decisions.
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(
            _client, engine, tenant, doc_id, run_id, 8, entity_type="organization"
        )
        await review_spans(
            _client, engine, tenant, doc_id, run_id, 3, entity_type="person_name"
        )

        decision = await _decision(tenant)

        assert decision["spans_accumulated"] == 11
        assert decision["by_entity_type"] == {"organization": 8, "person_name": 3}
        # Largest first, so the type the decision turns on is the one read first.
        assert list(decision["by_entity_type"]) == ["organization", "person_name"]


class TestNoTrainedModelShownDistinctly:
    """Row 8."""

    async def test_no_trained_model_shown_distinctly(self, engine):
        """A base-model tenant is a distinct state, not a zero.

        ADR-008: the base model serves as version 0 when nothing has been trained. Change 5
        already excludes base-model spans from the figure, so such a tenant would otherwise
        always report zero — which reads as "nothing to do" when the truth is "nothing has been
        trained" (design.md Decision 5).
        """
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="0")
        # No promoted model version at all: ADR-008's fallback.
        await review_spans(
            _client, engine, tenant, doc_id, run_id, 4, model_version="0", base_model=True
        )

        decision = await _decision(tenant)

        assert decision["has_trained_model"] is False
        assert decision["serving_model_version"] is None
        assert decision["state"] == "no_trained_model"
        # The half that catches a response reporting both: there is no zero to misread.
        assert "spans_accumulated" not in decision
        assert "by_entity_type" not in decision
        # The reviewed work is still visible, classified rather than dropped.
        assert decision["spans_from_base_model"] == 4


class TestAccumulationNotPresentedAsReadiness:
    """Row 9."""

    async def test_accumulation_not_presented_as_readiness(self, engine):
        """The figure is labelled as what it is, and says in words what it is not."""
        tenant = await make_tenant(engine)
        doc_id = await add_document(engine, tenant)
        run_id = await add_run(engine, tenant, doc_id, model_version="3")
        await add_model_version(engine, tenant, 3, status="promoted")
        await review_spans(_client, engine, tenant, doc_id, run_id, 5)

        decision = await _decision(tenant)

        assert decision["kind"] == "accumulation_since_training"
        assert "not a dataset readiness measure" in decision["note"]
        # No readiness verdict, no threshold, no "ready" field of any kind.
        assert not [key for key in decision if "readiness" in key or "threshold" in key]
        assert not [key for key in decision if key.startswith("ready")]

    def test_surface_introduces_no_readiness_threshold(self):
        """ADR-010's threshold is neither imported nor named by this surface.

        Structural because the behavioural half cannot see it: a surface that read
        `NER_MIN_ENTITIES_PER_TYPE`, compared the figure against it, and reported only the
        figure would satisfy every assertion above while doing the thing task 3.3 forbids.
        """
        source = Path("src/annotation_service/api/v1/retraining_decision.py").read_text(
            encoding="utf-8"
        )
        code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        code = re.sub(r"#.*", "", code)

        assert "NER_MIN_ENTITIES_PER_TYPE" not in code
        assert "NER_MIN_TRAINING_ENTITIES" not in code
        assert "training_readiness" not in code
        # No numeric literal to compare a figure against. `200`, ADR-010's value, most of all.
        assert not re.search(r"\b\d{2,}\b", code)
