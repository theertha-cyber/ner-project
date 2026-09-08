"""Evidence for the promotion decision, and the verdict it must not produce.

Covers verification.md rows 18-21.

Row 20 supplies a candidate with strictly better metrics than the promoted version and asserts
the response still says nothing about which is better. That is the shape the test needs: a
surface that produced a verdict only when one version won clearly would pass a test over two
similar versions and fail a real decision. Given an obvious winner, the response must remain
evidence (design.md Decision 4, verification.md Risk 7).

Row 19's flag exists because change 3 established that metrics from runs over materially
different data are not comparable. The threshold behind it gates a sentence and nothing else,
which is checked structurally alongside.
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

from src.annotation_service.main import app as annotation_app
from src.shared.config import settings
from src.training_service.api.v1.promotion_evidence import (
    MATERIAL_DATASET_DIFFERENCE,
    dataset_sizes_comparable,
)
from src.training_service.main import app as training_app
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    auth_header,
    complete_run,
    drop_test_schemas,
    make_tenant,
    review_spans,
)

pytestmark = pytest.mark.verification

# Any word that would turn evidence into advice. Asserted absent from the whole serialized
# response, so it catches a verdict smuggled into a note as readily as one in a field name.
VERDICT_WORDS = (
    "better",
    "worse",
    "recommend",
    "improve",
    "regress",
    "superior",
    "should promote",
    "winner",
    "outperform",
    "verdict",
)

STRONG_METRICS = {"eval_f1": 0.91, "eval_precision": 0.93, "eval_recall": 0.89}
WEAK_METRICS = {"eval_f1": 0.72, "eval_precision": 0.70, "eval_recall": 0.74}


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


def _annotation_client():
    return AsyncClient(transport=ASGITransport(app=annotation_app), base_url="http://test")


def _training_client():
    return AsyncClient(transport=ASGITransport(app=training_app), base_url="http://test")


async def _evidence(tenant, version_number) -> dict:
    async with _training_client() as client:
        resp = await client.get(
            f"/api/v1/training-promotion-evidence/{version_number}",
            headers=auth_header(tenant["tid"]),
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _tenant_with_consumed_spans(engine, counts: dict[int, int]):
    """A tenant whose versions have recorded the given numbers of consumed spans.

    `counts` maps version number to how many spans that version's run consumed. The spans are
    real production-review spans resolved through the review endpoint and then recorded through
    the production writer, so `trained_on_span_count` is read from the same table the worker
    fills rather than from a number this file made up.
    """
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id, model_version="3")
    for version_number, count in counts.items():
        span_ids = await review_spans(
            _annotation_client, engine, tenant, doc_id, run_id, count
        )
        await complete_run(engine, tenant, span_ids, version_number=version_number)
    return tenant, doc_id, run_id


class TestCandidateAndCurrentMetricsPresented:
    """Row 18."""

    async def test_candidate_and_current_metrics_presented(self, engine):
        """Both versions' metrics, and what each was trained on, in one response."""
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {3: 5, 4: 5})
        await add_model_version(engine, tenant, 3, status="promoted", metrics=WEAK_METRICS)
        await add_model_version(engine, tenant, 4, status="completed", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 4)

        assert evidence["candidate"]["version_number"] == 4
        assert evidence["candidate"]["metrics"]["eval_f1"] == STRONG_METRICS["eval_f1"]
        assert evidence["candidate"]["trained_on_span_count"] == 5

        assert evidence["current"]["version_number"] == 3
        assert evidence["current"]["metrics"]["eval_f1"] == WEAK_METRICS["eval_f1"]
        assert evidence["current"]["trained_on_span_count"] == 5


class TestDifferentDatasetSizesFlagged:
    """Row 19."""

    async def test_different_dataset_sizes_flagged(self, engine):
        """The spec's 300-versus-1200 at the same ratio: 4 against 16.

        The ratio is what the check reads, not the absolute counts, so a smaller pair with the
        same relative gap exercises the same rule without 1500 resolutions.
        """
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {3: 4, 4: 16})
        await add_model_version(engine, tenant, 3, status="promoted", metrics=WEAK_METRICS)
        await add_model_version(engine, tenant, 4, status="completed", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 4)

        assert evidence["comparable"] is False
        assert "materially different dataset sizes" in evidence["note"]
        assert "not directly comparable" in evidence["note"]
        assert evidence["candidate"]["trained_on_span_count"] == 16
        assert evidence["current"]["trained_on_span_count"] == 4

    async def test_similar_dataset_sizes_not_flagged(self, engine):
        """Close counts are reported as such, so the flag means something when it appears."""
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {3: 9, 4: 10})
        await add_model_version(engine, tenant, 3, status="promoted", metrics=WEAK_METRICS)
        await add_model_version(engine, tenant, 4, status="completed", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 4)

        assert evidence["comparable"] is True
        assert "similar dataset sizes" in evidence["note"]

    def test_unknown_dataset_size_is_not_comparable(self):
        """An unrecorded size is unknown, not similar.

        A version trained before the consumed-span writer existed has no rows, and returning
        `True` there would assert comparability from an absence of evidence — the mistake this
        surface exists to avoid, made by the check meant to prevent it.
        """
        assert dataset_sizes_comparable(0, 300) is None
        assert dataset_sizes_comparable(300, 0) is None
        assert dataset_sizes_comparable(0, 0) is None

    def test_threshold_is_the_decided_value_and_gates_only_a_sentence(self):
        """tasks.md 1.4's 25%, and nothing behind it.

        The constant is the only comparison constant this change defines, so it is the one place
        a reader might reasonably fear an action hides. Structurally: the module enqueues
        nothing, promotes nothing, and creates nothing.
        """
        assert MATERIAL_DATASET_DIFFERENCE == 0.25
        assert dataset_sizes_comparable(100, 74) is False
        assert dataset_sizes_comparable(100, 76) is True

        source = Path("src/training_service/api/v1/promotion_evidence.py").read_text(
            encoding="utf-8"
        )
        code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
        code = re.sub(r"#.*", "", code)
        # Write-shaped tokens only. `promoted` appears legitimately and often — the module
        # reads `promoted_at` and selects `WHERE status = 'promoted'` to find the version to
        # compare against — so the bare word is not the thing to forbid. What must be absent is
        # anything that *changes* a promotion, which is a call or a write.
        for token in (
            "send_task",
            "apply_async",
            ".delay(",
            "INSERT",
            "UPDATE",
            "DELETE",
            "promote_model",
            "mlflow_promote",
        ):
            assert token not in code, token


class TestNoVerdictProduced:
    """Row 20."""

    async def test_no_verdict_produced(self, engine):
        """A strictly better candidate still gets no verdict.

        Every metric on version 4 beats version 3's and the dataset sizes are similar, so a
        surface inclined to judge has every excuse. It must still only report.
        """
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {3: 10, 4: 10})
        await add_model_version(engine, tenant, 3, status="promoted", metrics=WEAK_METRICS)
        await add_model_version(engine, tenant, 4, status="completed", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 4)

        assert evidence["candidate"]["metrics"]["eval_f1"] > evidence["current"]["metrics"]["eval_f1"]

        serialized = str(evidence).lower()
        for word in VERDICT_WORDS:
            assert word not in serialized, word

        # No field could carry one either: the response is two blocks, a comparability flag, and
        # a note about that flag.
        assert set(evidence) == {"candidate", "current", "comparable", "note"}


class TestNoPromotedVersionToCompare:
    """Row 21."""

    async def test_no_promoted_version_to_compare(self, engine):
        """A first model has its own metrics and an explicit absence, not a fabricated pair."""
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {1: 6})
        await add_model_version(engine, tenant, 1, status="completed", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 1)

        assert evidence["candidate"]["version_number"] == 1
        assert evidence["candidate"]["metrics"]["eval_f1"] == STRONG_METRICS["eval_f1"]
        assert evidence["candidate"]["trained_on_span_count"] == 6
        assert evidence["current"] is None
        assert evidence["comparable"] is None
        assert "no other promoted model version to compare against" in evidence["note"]

    async def test_candidate_that_is_itself_promoted_has_nothing_to_compare(self, engine):
        """Comparing a version with itself would produce a reassuring identical pair."""
        tenant, _, _ = await _tenant_with_consumed_spans(engine, {2: 6})
        await add_model_version(engine, tenant, 2, status="promoted", metrics=STRONG_METRICS)

        evidence = await _evidence(tenant, 2)

        assert evidence["current"] is None
        assert evidence["comparable"] is None

    async def test_unknown_version_is_404(self, engine):
        tenant = await make_tenant(engine)
        async with _training_client() as client:
            resp = await client.get(
                "/api/v1/training-promotion-evidence/99",
                headers=auth_header(tenant["tid"]),
            )
        assert resp.status_code == 404
