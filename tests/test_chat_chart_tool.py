"""Covers verification.md rows 5-12: the render_chart tool contract and the
grounding check that decides whether a proposed chart may be shown."""

import json
import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.chat_api.api.v1.schemas import ChartPayload
from src.chat_api.services.chart_tool import (
    GROUNDING_REL_TOL,
    RENDER_CHART_SCHEMA,
    RENDER_CHART_TOOL_NAME,
    parse_chart_tool_call,
    validate_chart_grounding,
)

pytestmark = [pytest.mark.verification]

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
ROWS = [
    {"quarter": "Q1", "amount": Decimal("120000")},
    {"quarter": "Q2", "amount": Decimal("95000")},
    {"quarter": "Q3", "amount": Decimal("143000")},
    {"quarter": "Q4", "amount": Decimal("160000")},
]


def _payload(**overrides) -> dict:
    payload = {
        "chart_type": "bar",
        "title": "Billed per quarter",
        "categories": list(QUARTERS),
        "series": [{"name": "amount", "data": [120000, 95000, 143000, 160000]}],
    }
    payload.update(overrides)
    return payload


def _tool_call(arguments, name=RENDER_CHART_TOOL_NAME):
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=raw))


class TestToolContract:
    def test_5_well_formed_payload_is_accepted(self):
        """Row 5: four categories and one four-value series is structurally valid."""
        payload = ChartPayload.model_validate(_payload())
        assert payload.chart_type == "bar"
        assert len(payload.series[0].data) == len(payload.categories) == 4

    def test_6_series_length_mismatch_is_rejected(self):
        """Row 6: three categories against a four-value series."""
        with pytest.raises(ValidationError):
            ChartPayload.model_validate(
                _payload(categories=["Q1", "Q2", "Q3"], series=[{"name": "amount", "data": [1, 2, 3, 4]}])
            )

    def test_7_unsupported_chart_type_is_rejected(self):
        """Row 7: a chart_type outside bar/line/pie."""
        with pytest.raises(ValidationError):
            ChartPayload.model_validate(_payload(chart_type="donut"))

    def test_empty_categories_or_series_is_rejected(self):
        with pytest.raises(ValidationError):
            ChartPayload.model_validate(_payload(categories=[], series=[]))

    def test_tool_schema_declares_no_tenancy_parameter(self):
        """ADR-001: the tool is a return channel and must not be able to name a tenant."""
        properties = RENDER_CHART_SCHEMA["function"]["parameters"]["properties"]
        assert not {"tenant_id", "tenant", "schema", "schema_name"} & set(properties)
        assert RENDER_CHART_SCHEMA["function"]["parameters"]["required"] == [
            "chart_type",
            "title",
            "categories",
            "series",
        ]


class TestGrounding:
    def test_9_values_present_in_rows_are_accepted(self):
        """Row 9: every plotted value appears in the retrieved rows."""
        payload = ChartPayload.model_validate(_payload())
        assert validate_chart_grounding(payload, ROWS) is payload

    def test_10_invented_value_is_rejected_and_logged(self, caplog):
        """Row 10: 250000 appears nowhere in the rows."""
        payload = ChartPayload.model_validate(
            _payload(series=[{"name": "amount", "data": [120000, 95000, 250000, 160000]}])
        )
        with caplog.at_level(logging.WARNING):
            assert validate_chart_grounding(payload, ROWS) is None
        assert "250000" in caplog.text

    def test_11_precision_artifact_does_not_reject(self):
        """Row 11: a Decimal of 120000.004 restated as 120000.0 still matches."""
        rows = [{"quarter": "Q1", "amount": Decimal("120000.004")}]
        payload = ChartPayload.model_validate(
            _payload(categories=["Q1"], series=[{"name": "amount", "data": [120000.0]}])
        )
        assert validate_chart_grounding(payload, rows) is payload

    def test_12_value_restated_as_rounder_figure_is_rejected(self):
        """Row 12: 143217 drawn as 143000. This pins GROUNDING_REL_TOL — if this test
        starts passing, the tolerance has been widened and the guard is no longer picky."""
        rows = [{"quarter": "Q1", "amount": Decimal("143217")}]
        payload = ChartPayload.model_validate(
            _payload(categories=["Q1"], series=[{"name": "amount", "data": [143000]}])
        )
        assert validate_chart_grounding(payload, rows) is None

    def test_tolerance_constant_stays_near_exact(self):
        """A second guard on the same constant: 1e-6 admits representation noise only."""
        assert GROUNDING_REL_TOL <= 1e-6

    def test_every_series_is_checked_not_just_the_first(self):
        payload = ChartPayload.model_validate(
            _payload(
                series=[
                    {"name": "amount", "data": [120000, 95000, 143000, 160000]},
                    {"name": "forecast", "data": [120000, 95000, 143000, 999999]},
                ]
            )
        )
        assert validate_chart_grounding(payload, ROWS) is None

    def test_boolean_row_value_does_not_ground_a_chart(self):
        """A true flag must not let a chart claim 1.0 is real data."""
        payload = ChartPayload.model_validate(
            _payload(categories=["Q1"], series=[{"name": "amount", "data": [1.0]}])
        )
        assert validate_chart_grounding(payload, [{"is_final": True}]) is None

    def test_turn_with_no_numeric_rows_grounds_nothing(self):
        payload = ChartPayload.model_validate(
            _payload(categories=["Q1"], series=[{"name": "amount", "data": [1.0]}])
        )
        assert validate_chart_grounding(payload, []) is None


class TestToolCallParsing:
    def test_valid_tool_call_returns_payload(self):
        assert parse_chart_tool_call(_tool_call(_payload()), ROWS) is not None

    def test_malformed_json_returns_none_without_raising(self):
        assert parse_chart_tool_call(_tool_call("{not json"), ROWS) is None

    def test_structurally_invalid_payload_returns_none(self):
        bad = _payload(categories=["Q1", "Q2"], series=[{"name": "amount", "data": [1, 2, 3]}])
        assert parse_chart_tool_call(_tool_call(bad), ROWS) is None

    def test_ungrounded_payload_returns_none(self):
        bad = _payload(series=[{"name": "amount", "data": [1, 2, 3, 4]}])
        assert parse_chart_tool_call(_tool_call(bad), ROWS) is None

    def test_other_tool_name_is_ignored(self):
        assert parse_chart_tool_call(_tool_call(_payload(), name="semantic_retrieval"), ROWS) is None

    def test_none_tool_call_is_ignored(self):
        assert parse_chart_tool_call(None, ROWS) is None
