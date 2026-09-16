"""The `render_chart` tool offered to the answer-generation model, and the
validation that decides whether a chart it proposes may be shown.

A chart reads as more authoritative than a sentence, so nothing here trusts the
model's arithmetic: every value it proposes must already be present in the rows
the turn retrieved.
"""

from __future__ import annotations

import json
import logging
import math
from decimal import Decimal

from pydantic import ValidationError

from src.chat_api.api.v1.schemas import ChartPayload

logger = logging.getLogger(__name__)

RENDER_CHART_TOOL_NAME = "render_chart"


class ChartFrame:
    """A chart travelling down the token sink ahead of the answer's first delta.

    The chart is decided before stage B produces any prose, and the SSE contract puts
    the `chart` event before the first `token` event so the client can render the shape
    while the commentary is still arriving. Sending it through the sink the deltas
    already use is what makes that ordering automatic rather than something the HTTP
    layer has to reconstruct."""

    __slots__ = ("payload",)

    def __init__(self, payload: dict):
        self.payload = payload

# Near-exact. Wide enough to absorb a database Decimal rendered as a float or a
# value restated with less trailing precision; far too tight to admit a number
# rounded to read nicely. On 143217 this permits a drift of about 0.14, so a
# chart claiming 143000 for that row is rejected rather than quietly drawn.
GROUNDING_REL_TOL = 1e-6

RENDER_CHART_SCHEMA = {
    "type": "function",
    "function": {
        "name": RENDER_CHART_TOOL_NAME,
        "description": (
            "Render a chart alongside your answer. Call this only when the question is "
            "answered by a small set of categories or by a series over a period — a "
            "trend, a comparison, or a breakdown that is easier to see than to read. "
            "Do not call it for a single figure, for data with no category or period "
            "dimension, or when the answer is narrative. Every number you pass must be "
            "copied exactly from the data you were given: do not round, rescale, or "
            "tidy the values, and do not supply a figure you cannot find in that data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie"],
                    "description": "bar to compare categories, line for a series over time, pie for parts of a whole.",
                },
                "title": {"type": "string", "description": "Short title describing what the chart shows."},
                "x_label": {"type": "string", "description": "Label for the category axis. Omit for a pie chart."},
                "y_label": {"type": "string", "description": "Label for the value axis, including the unit where known."},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One label per point, in the order they should appear.",
                },
                "series": {
                    "type": "array",
                    "description": "One entry per series. Each series must carry exactly one value per category.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "data": {"type": "array", "items": {"type": "number"}},
                        },
                        "required": ["name", "data"],
                    },
                },
            },
            "required": ["chart_type", "title", "categories", "series"],
        },
    },
}


def _numeric_values(sql_results: list[dict] | None) -> list[float]:
    """Every number reachable in the turn's rows, as floats. Booleans are excluded:
    SQLAlchemy returns them as ints, and a chart matching 1.0 against a true flag
    would be grounded in nothing."""
    values: list[float] = []
    for row in sql_results or []:
        for value in row.values():
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float, Decimal)):
                values.append(float(value))
    return values


def _is_grounded(value: float, candidates: list[float]) -> bool:
    return any(
        math.isclose(value, candidate, rel_tol=GROUNDING_REL_TOL, abs_tol=GROUNDING_REL_TOL)
        for candidate in candidates
    )


def validate_chart_grounding(payload: ChartPayload, sql_results: list[dict] | None) -> ChartPayload | None:
    """Returns the payload when every value it plots is present in `sql_results`,
    otherwise None. Rejection drops the chart only — the caller still delivers the
    turn's text answer."""
    candidates = _numeric_values(sql_results)
    if not candidates:
        logger.warning("chart rejected: turn has no numeric rows to ground it against")
        return None

    for entry in payload.series:
        for value in entry.data:
            if not _is_grounded(value, candidates):
                logger.warning(
                    "chart rejected: value %r in series %r is absent from the retrieved rows",
                    value,
                    entry.name,
                )
                return None
    return payload


def parse_chart_tool_call(tool_call, sql_results: list[dict] | None) -> ChartPayload | None:
    """Turns a `render_chart` tool call into a chart that is safe to render, or None.

    Never raises: a malformed tool call is a turn without a chart, not a failed turn.
    """
    if tool_call is None or getattr(tool_call.function, "name", None) != RENDER_CHART_TOOL_NAME:
        return None

    try:
        arguments = json.loads(tool_call.function.arguments)
    except (TypeError, ValueError):
        logger.warning("chart rejected: tool call arguments were not valid JSON", exc_info=True)
        return None

    try:
        payload = ChartPayload.model_validate(arguments)
    except ValidationError as exc:
        logger.warning("chart rejected: payload failed validation — %s", exc)
        return None

    return validate_chart_grounding(payload, sql_results)
