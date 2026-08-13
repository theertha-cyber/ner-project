import os

import pytest

from src.shared.retrieval.eval.gate import BaselineNotFoundError, check_regression, load_baseline
from src.shared.retrieval.eval.metrics import LEGACY_SCORING_RULE, SCORING_RULE
from src.shared.retrieval.eval.runner import SYNTHETIC_CORPUS, TENANT_CORPUS

pytestmark = []

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "retrieval_eval")

BASELINE = {
    "recall_at_k": 0.80, "ndcg_at_k": 0.80, "precision_at_k": 0.6, "mrr_at_k": 0.7,
    "scoring_rule": SCORING_RULE, "corpus": SYNTHETIC_CORPUS,
}


class TestRegressionBelowToleranceFails:
    """Covers verification.md row 39."""

    def test_regression_below_tolerance_fails(self):
        observed = {**BASELINE, "ndcg_at_k": 0.70}
        result = check_regression(observed, BASELINE, tolerance=0.02)

        assert result.passed is False
        assert "ndcg_at_k" in result.message
        assert "0.8" in result.message
        assert "0.7" in result.message


class TestWithinToleranceP:
    """Covers verification.md row 40."""

    def test_within_tolerance_passes(self):
        observed = {**BASELINE, "ndcg_at_k": 0.79}
        result = check_regression(observed, BASELINE, tolerance=0.02)

        assert result.passed is True


class TestImprovementReported:
    """Covers verification.md row 41."""

    def test_improvement_passes_and_reports_deltas(self):
        observed = {**BASELINE, "recall_at_k": 0.85, "ndcg_at_k": 0.88}
        result = check_regression(observed, BASELINE, tolerance=0.02)

        assert result.passed is True
        assert "Improvements" in result.message
        assert any(d.metric == "recall_at_k" and d.delta > 0 for d in result.deltas)
        assert any(d.metric == "ndcg_at_k" and d.delta > 0 for d in result.deltas)


class TestComparabilityIsRequired:
    """verification.md rows 84, 93. A score means something only relative to the rule
    that produced it and the corpus it ran against — under the old `skip-degraded` rule
    a degraded query dropped out of the mean entirely, so the two sets of numbers
    measure different things."""

    def test_gate_requires_baseline_matching_scoring_rule(self):
        legacy = {**BASELINE, "scoring_rule": LEGACY_SCORING_RULE}
        result = check_regression(BASELINE, legacy, tolerance=0.02)

        assert result.passed is False
        assert "scoring rule mismatch" in result.message
        assert LEGACY_SCORING_RULE in result.message

    def test_baseline_without_a_scoring_rule_is_rejected(self):
        unlabelled = {k: v for k, v in BASELINE.items() if k != "scoring_rule"}
        result = check_regression(BASELINE, unlabelled, tolerance=0.02)

        assert result.passed is False
        assert "Regenerate" in result.message

    def test_corpus_mismatch_rejected(self):
        tenant_run = {**BASELINE, "corpus": TENANT_CORPUS}
        result = check_regression(tenant_run, BASELINE, tolerance=0.02)

        assert result.passed is False
        assert "corpus mismatch" in result.message
        assert TENANT_CORPUS in result.message
        assert SYNTHETIC_CORPUS in result.message

    def test_matching_rule_and_corpus_compares_normally(self):
        observed = {**BASELINE, "ndcg_at_k": 0.70}
        result = check_regression(observed, BASELINE, tolerance=0.02)

        assert result.passed is False
        assert "ndcg_at_k" in result.message


class TestMissingBaselineFailsExplicitly:
    """Covers verification.md row 43."""

    def test_missing_baseline_fails_with_instructions(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.json"
        with pytest.raises(BaselineNotFoundError, match="Generate one"):
            load_baseline(str(missing_path))


class TestGateExcludedFromDefaultRun:
    """Covers verification.md row 42."""

    def test_pytest_ini_excludes_eval_gate_marker_by_default(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pytest.ini"), encoding="utf-8") as f:
            content = f.read()
        assert 'addopts = -m "not eval_gate"' in content
        assert "eval_gate:" in content


@pytest.mark.eval_gate
class TestFullGateAgainstCommittedBaseline:
    """End-to-end sanity check: only runs when explicitly invoked with `-m eval_gate`
    (needs the live test Postgres from tests/conftest.py). Not run by default — see
    TestGateExcludedFromDefaultRun."""

    def test_committed_baseline_loads_and_gate_logic_applies(self):
        baseline = load_baseline(os.path.join(FIXTURES_DIR, "baseline.json"))
        result = check_regression(baseline, baseline, tolerance=0.02)
        assert result.passed is True
