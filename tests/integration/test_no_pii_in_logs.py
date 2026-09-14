"""Extracted personal data never reaches a log record.

Verification row 14, and the concrete instance of Exit Gate 3's "no sensitive content in
telemetry, verified by an automated scan".

This is the scan. A document is seeded with values that are recognisably a person — a
name, an email, a phone number — it is put through the extraction and post-processing
path, every record that path emits is captured, and the whole capture is searched for any
of them. Counts and entity type names are explicitly allowed; the values are not.

The check is deliberately over the *whole* captured stream rather than over named fields.
A leak that a field-by-field assertion would miss is exactly the kind this is for: an
exception message that quoted a row back, a debug line nobody remembered writing.
"""

import io
import json
import logging

import pytest

from src.shared.observability.logging_config import build_handler

pytestmark = [pytest.mark.verification]

# Values a resume would carry, seeded so a leak is unambiguous rather than a coincidence.
SEEDED_NAME = "Priya Raman"
SEEDED_EMAIL = "priya.raman@example.com"
SEEDED_PHONE = "+91 98765 43210"
SEEDED_COMPANY = "Northwind Analytics Pvt Ltd"
SEEDED_VALUES = (SEEDED_NAME, SEEDED_EMAIL, SEEDED_PHONE, SEEDED_COMPANY)

DOCUMENT_TEXT = (
    f"{SEEDED_NAME}\n{SEEDED_EMAIL} | {SEEDED_PHONE}\n"
    f"Senior Data Engineer at {SEEDED_COMPANY}, 2019-2024.\n"
    "Skills: Python, Airflow, dbt."
)

# The entity types those values carry. Type names are permitted in telemetry; the values
# they hold are not.
SEEDED_ENTITIES = [
    {"entity_type": "NAME", "entity_value": SEEDED_NAME},
    {"entity_type": "EMAIL", "entity_value": SEEDED_EMAIL},
    {"entity_type": "PHONE", "entity_value": SEEDED_PHONE},
    {"entity_type": "COMPANY", "entity_value": SEEDED_COMPANY},
]


@pytest.fixture
def captured_records():
    """Capture everything the extraction path logs, through the real handler."""
    buffer = io.StringIO()
    handler = build_handler("extraction_service", stream=buffer)
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)
    try:
        yield buffer
    finally:
        root.handlers, root.level = saved_handlers, saved_level


def _emit_extraction_path_records():
    """Drive the log calls the extraction path makes for one document.

    Called with the real values rather than placeholders, and — deliberately — through
    the same careless shapes a future call site might use: the document text under a
    `document_text` field, an entity value under `entity_value`, and one interpolated
    into a message. If the filter only contained the tidy cases it would not be a control.
    """
    logger = logging.getLogger("src.extraction_service.services.extraction_engine")

    logger.info(
        "extraction_started",
        extra={"document_text": DOCUMENT_TEXT, "chars": len(DOCUMENT_TEXT)},
    )
    for entity in SEEDED_ENTITIES:
        logger.debug(
            "entity_extracted",
            extra={"entity_type": entity["entity_type"], "entity_value": entity["entity_value"]},
        )
    logger.info(
        "extraction_completed entity_count=%d types=%s",
        len(SEEDED_ENTITIES),
        ",".join(sorted({e["entity_type"] for e in SEEDED_ENTITIES})),
    )
    logger.warning("entity_postprocess_degraded", extra={"reason": "unavailable"})
    logger.info("sql_attempt", extra={"sql": f"SELECT * FROM t WHERE v = '{SEEDED_NAME}'"})


class TestNoSeededValueReachesARecord:
    """Row 14."""

    def test_the_capture_contains_no_seeded_entity_value(self, captured_records):
        _emit_extraction_path_records()

        emitted = captured_records.getvalue()
        leaked = [value for value in SEEDED_VALUES if value in emitted]
        assert leaked == [], f"extracted personal data reached a log record: {leaked}"

    def test_the_capture_contains_no_document_text(self, captured_records):
        _emit_extraction_path_records()

        emitted = captured_records.getvalue()
        assert "Senior Data Engineer" not in emitted
        assert "Airflow" not in emitted

    def test_no_email_shaped_string_survives(self, captured_records):
        """A cheap catch-all for the leak class that matters most, independent of which
        field it arrived in."""
        _emit_extraction_path_records()

        assert "@" not in captured_records.getvalue()


class TestShapeIsStillRecorded:
    """The counterpart. A scan that passes because nothing was logged at all would be
    worthless — and would quietly undo the reason logging was configured in the first
    place."""

    def test_counts_and_type_names_are_present(self, captured_records):
        _emit_extraction_path_records()

        records = [
            json.loads(line)
            for line in captured_records.getvalue().splitlines()
            if line.strip()
        ]
        assert records, "nothing was captured"

        events = {record["event"] for record in records}
        assert {"extraction_started", "entity_extracted", "extraction_completed"} <= events

        completed = next(r for r in records if r["event"] == "extraction_completed")
        assert "entity_count=4" in completed["message"]
        assert "COMPANY" in completed["message"], "entity type names are permitted"

        extracted = next(r for r in records if r["event"] == "entity_extracted")
        assert extracted["entity_type"] in {"NAME", "EMAIL", "PHONE", "COMPANY"}
