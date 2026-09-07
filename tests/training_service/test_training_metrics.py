"""Training reports its lifecycle. Model quality stays in MLflow.

Verification rows 21, 22 and 23.

Row 23 is the one with teeth, and it is a registry walk rather than a source grep on
purpose. The boundary this test defends is the one that erodes: the first dashboard
request for "show me F1 over time" is what breaks it, and the natural way to satisfy that
request is a dynamically registered family — which a grep over `worker.py` would never
see. It should break with a failing build and a deliberate decision to amend, not quietly.

Why the boundary exists at all: `worker.py` already logs evaluation metrics to MLflow,
which versions them against the run, the params and the artifact. Mirroring them into
Prometheus creates a second source of truth with worse fidelity, no run linkage and a
retention window that will disagree with MLflow's. "Is the job stuck or failing" is an
operational question and belongs in metrics; "is this model good" is an experiment
question and belongs in MLflow. See design Decision 9.
"""

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]


def _transitions(state: str) -> float:
    value = REGISTRY.get_sample_value("ner_training_job_transitions_total", {"state": state})
    return float(value or 0.0)


def _duration_count(final_state: str) -> float:
    value = REGISTRY.get_sample_value(
        "ner_training_job_duration_seconds_count", {"final_state": final_state}
    )
    return float(value or 0.0)


def _failures(cause: str) -> float:
    value = REGISTRY.get_sample_value("ner_training_job_failures_total", {"cause": cause})
    return float(value or 0.0)


class TestACompletedJob:
    """Row 21."""

    def test_each_state_transition_is_counted(self):
        before = {state: _transitions(state) for state in ("running", "completed")}

        dm.record_training_transition("running")
        dm.record_training_transition("completed")

        assert _transitions("running") == before["running"] + 1
        assert _transitions("completed") == before["completed"] + 1

    def test_the_total_duration_is_recorded_against_the_final_state(self):
        before = _duration_count("completed")

        dm.record_training_completion("completed", 1830.0, epochs=3)

        assert _duration_count("completed") == before + 1

    def test_epoch_progress_is_recorded(self):
        before = float(
            REGISTRY.get_sample_value("ner_training_epochs_completed_sum", {}) or 0.0
        )

        dm.record_training_completion("completed", 60.0, epochs=3)

        after = float(REGISTRY.get_sample_value("ner_training_epochs_completed_sum", {}))
        assert after == before + 3

    def test_transitions_are_counted_at_the_single_status_write(self):
        """ADR-009 makes the `training_jobs` row the authority on a job's state, and
        `_update_job_progress` is the one funnel every status write passes through — so a
        transition cannot be written without being counted."""
        import inspect

        from src.training_service import worker

        source = inspect.getsource(worker._update_job_progress)

        assert "record_training_transition(str(status))" in source

    def test_job_identity_comes_from_the_row_not_a_request_payload(self):
        """ADR-009 again: hyperparameters are set at approval, so the worker's own view of
        the job is the row it reads back, and no metric is keyed off the submitted
        payload."""
        assert "job_id" not in dm.TRAINING_TRANSITIONS.label_names
        assert "hyperparameters" not in dm.TRAINING_TRANSITIONS.label_names
        assert dm.TRAINING_TRANSITIONS.label_names == ("state",)


class TestAFailedJob:
    """Row 22."""

    def test_a_failure_increments_under_an_enumerated_cause(self):
        before = _failures("training_error")

        dm.record_training_failure("training_error")

        assert _failures("training_error") == before + 1

    def test_the_final_state_is_recorded_with_the_duration(self):
        before = _duration_count("failed")

        dm.record_training_completion("failed", 300.0)

        assert _duration_count("failed") == before + 1

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (TimeoutError("ran out of time"), "timeout"),
            (FileNotFoundError("/models/v3 missing"), "export_error"),
            (ValueError("bad label alignment on row 41"), "training_error"),
        ],
    )
    def test_the_cause_is_derived_from_the_exception_class(self, exc, expected):
        from src.training_service.worker import _training_failure_cause

        assert _training_failure_cause(exc) == expected

    def test_no_exception_message_reaches_the_cause_label(self):
        from src.training_service.worker import _training_failure_cause

        cause = _training_failure_cause(ValueError("failed on tenant acme row 'Priya Raman'"))

        assert cause in dm.TRAINING_FAILURE_CAUSES
        assert "Priya" not in cause

    def test_an_unmapped_cause_is_coerced_rather_than_minting_a_series(self):
        before = _failures(dm.OTHER)

        dm.record_training_failure("a cause nobody declared")

        assert _failures(dm.OTHER) == before + 1


class TestModelQualityIsNotMirrored:
    """Row 23 — the registry walk."""

    FORBIDDEN = ("f1", "precision", "recall", "loss", "accuracy", "auc")

    def _offending(self, names):
        offenders = []
        for name in names:
            lowered = name.lower()
            for term in self.FORBIDDEN:
                # Word-boundary-ish: `precision` must match, `precision_recall` too, but
                # a family that merely contains the letters must not produce a false
                # positive that trains people to ignore this test.
                if any(
                    part == term
                    for part in lowered.replace("-", "_").replace(".", "_").split("_")
                ):
                    offenders.append((name, term))
        return offenders

    def test_no_declared_family_exposes_a_model_quality_metric(self):
        assert self._offending(dm.FAMILIES.keys()) == []

    def test_no_family_on_the_live_registry_exposes_one(self):
        """The walk, not the grep. A dynamically registered family — the natural way to
        satisfy 'show me F1 over time' without editing the declarations — is invisible to
        a source search and caught here."""
        live = [metric.name for metric in REGISTRY.collect()]
        ner_families = [name for name in live if name.startswith("ner_")]

        assert ner_families, "the registry walk found no platform families at all"
        assert self._offending(ner_families) == [], (
            "MLflow versions model quality against the run, the params and the artifact; "
            "a Prometheus copy is a second source of truth with worse fidelity. Link to "
            "MLflow from the dashboard instead."
        )

    def test_no_declared_label_value_names_a_quality_metric_either(self):
        """The other way in: `ner_training_metric{name="f1"}` satisfies the letter of the
        family check and none of its purpose."""
        values = [
            value
            for family in dm.FAMILIES.values()
            for label in family.labels
            for value in label.values
        ]
        assert self._offending(values) == []

    def test_the_worker_still_logs_them_to_mlflow(self):
        """The corollary — the boundary is about where they live, not about dropping
        them."""
        import inspect

        from src.training_service import worker

        assert "mlflow.log_metrics" in inspect.getsource(worker)
