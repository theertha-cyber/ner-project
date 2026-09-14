"""`assert_tenant_schema` counts and logs; it never raises.

Verification rows 30 and 31.

Nine sites build a search path by f-string interpolation — `SET search_path TO {schema}`
— and until this change nothing anywhere noticed an unexpected value. The assertion is
deliberately not a hard failure: converting an interpolation site into a raise would
choose a failure mode for a condition we have no data about. It counts, so the decision
can be made later with a zero or non-zero counter in hand. See design Decision 5.
"""

import logging

import pytest
from prometheus_client import REGISTRY

from src.shared.observability import domain_metrics as dm

pytestmark = [pytest.mark.verification]

CODE_PATH = "shared.tenant_context.get_session"


def _violations(code_path: str = CODE_PATH) -> float:
    value = REGISTRY.get_sample_value(
        "ner_search_path_violations_total", {"code_path": code_path}
    )
    return float(value or 0.0)


class TestAWellFormedSchemaPasses:
    """Row 30."""

    @pytest.mark.parametrize(
        "schema",
        [
            # The form every `_schema()` helper in the codebase actually produces.
            "tenant_3f2a1b4c_9d8e_4f10_a1b2_c3d4e5f60718",
            # The hyphenated form design.md writes the pattern for.
            "tenant_3f2a1b4c-9d8e-4f10-a1b2-c3d4e5f60718",
            # The slug-named schemas the test fixtures seed.
            "tenant_test_tenant",
        ],
    )
    def test_it_passes_and_leaves_the_counter_alone(self, schema):
        before = _violations()

        assert dm.assert_tenant_schema(schema, CODE_PATH) is True
        assert _violations() == before, (
            "a counter that fires on every legitimate query is not a signal — it buries "
            "the one violation that mattered"
        )


class TestAMalformedSchemaIsCountedAndLogged:
    """Row 31."""

    def test_it_returns_false_rather_than_raising(self):
        """The behavioural commitment. A raise here would be a behavioural change smuggled
        into an instrumentation change, on a path that runs before every tenant query."""
        assert dm.assert_tenant_schema("public", CODE_PATH) is False

    def test_it_increments_the_violation_counter(self):
        before = _violations()

        dm.assert_tenant_schema("public; DROP SCHEMA tenant_a CASCADE", CODE_PATH)

        assert _violations() == before + 1

    def test_it_logs_at_error_naming_the_code_path(self, caplog):
        with caplog.at_level(logging.ERROR, logger="src.shared.observability.domain_metrics"):
            dm.assert_tenant_schema("public", CODE_PATH)

        records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert records, "a violation must be visible in Loki before an alert rule exists"
        assert getattr(records[-1], "code_path", None) == CODE_PATH, (
            "which of the nine interpolation sites fired is the whole diagnostic value"
        )

    def test_the_offending_value_is_recorded_in_a_sanitised_form(self, caplog):
        """A violating value is by definition one we did not expect, so it must not be
        able to inject structure into the record that reports it."""
        hostile = "tenant_a\"\n{\"level\": \"info\", \"msg\": \"all clear\"}"

        with caplog.at_level(logging.ERROR, logger="src.shared.observability.domain_metrics"):
            dm.assert_tenant_schema(hostile, CODE_PATH)

        logged = getattr(caplog.records[-1], "schema", "")
        assert "\n" not in logged and '"' not in logged and "{" not in logged
        assert "tenant_a" in logged

    def test_the_logged_value_is_bounded(self):
        assert len(dm.sanitize_schema_for_log("tenant_" + "x" * 5000)) <= 64

    @pytest.mark.parametrize("schema", [None, 42, ["tenant_a"]])
    def test_a_non_string_is_a_violation_rather_than_a_crash(self, schema):
        before = _violations()

        assert dm.assert_tenant_schema(schema, CODE_PATH) is False
        assert _violations() == before + 1


class TestTheCallSitesAreDeclared:
    """The `code_path` label is itself an enumerated value set — a free-form string here
    would reintroduce the unbounded-label failure mode inside the counter that exists to
    catch unbounded values."""

    def test_all_nine_interpolation_sites_are_named(self):
        declared = dm.SEARCH_PATH_CALL_SITES - {dm.OTHER}

        assert len(declared) == 9
        assert "shared.tenant_context.get_session" in declared
        assert sum(1 for s in declared if s.startswith("chat_api.sql_generator.")) == 5

    def test_an_undeclared_code_path_is_coerced_rather_than_minting_a_series(self):
        before = _violations(dm.OTHER)

        dm.assert_tenant_schema("public", "some.module.nobody.declared")

        assert _violations(dm.OTHER) == before + 1
