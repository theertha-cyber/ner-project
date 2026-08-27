"""The labelled entity-quality fixture and its loader.

Every case is drawn from a real document in the development tenant and records what the
model actually predicted, so a configuration can be replayed against the same input the
production pipeline saw. The required-class check exists because a fixture that quietly
loses coverage of a failure class stops being evidence about that class while still
reporting a number."""

import json
from dataclasses import dataclass, field
from pathlib import Path

# Every failure class the forensic pass observed. A fixture missing one of these cannot
# say anything about it, so loading fails rather than reporting a partial score.
REQUIRED_CLASSES = (
    "correct_extraction",
    "entity_type_error",
    "fragmented_span",
    "malformed_value",
    "format_characters",
    "duplicate_mentions",
    "duration_numeric",
    "date_value",
    "organization_name",
    "person_name",
    "multi_token",
)


class FixtureError(Exception):
    pass


@dataclass(frozen=True)
class ExpectedEntity:
    entity_type: str
    entity_value: str
    value_number: float | None = None

    def key(self) -> tuple[str, str]:
        return (self.entity_type.upper(), self.entity_value)


@dataclass(frozen=True)
class FixtureCase:
    case_id: str
    document_id: str
    filename: str
    failure_class: str
    tokens: list[str]
    predictions: list[dict]
    expected: list[ExpectedEntity]
    page_number: int = 0
    notes: str | None = None
    entity_type_config: dict = field(default_factory=dict)

    @property
    def source_text(self) -> str:
        return " ".join(self.tokens)


def _parse_case(record: dict, line_no: int) -> FixtureCase:
    for required in ("case_id", "document_id", "failure_class", "tokens", "predictions", "expected"):
        if required not in record:
            raise FixtureError(f"fixture line {line_no}: missing '{required}'")

    if record["failure_class"] not in REQUIRED_CLASSES:
        raise FixtureError(
            f"fixture line {line_no}: unknown failure_class {record['failure_class']!r}"
        )

    tokens = record["tokens"]
    source_text = " ".join(tokens)
    expected = []
    for item in record["expected"]:
        value = item["entity_value"]
        # A fixture whose "correct" answer is not in the document would make every
        # configuration look like it hallucinated, or excuse one that did.
        if value not in source_text:
            raise FixtureError(
                f"fixture line {line_no}: expected value {value!r} is not present in the source text"
            )
        expected.append(ExpectedEntity(
            entity_type=item["entity_type"],
            entity_value=value,
            value_number=item.get("value_number"),
        ))

    return FixtureCase(
        case_id=record["case_id"],
        document_id=record["document_id"],
        filename=record.get("filename", ""),
        failure_class=record["failure_class"],
        tokens=tokens,
        predictions=record["predictions"],
        expected=expected,
        page_number=record.get("page_number", 0),
        notes=record.get("notes"),
        entity_type_config=record.get("entity_type_config", {}),
    )


def load_fixture(path: str | Path) -> list[FixtureCase]:
    """Loads the fixture and refuses a set that has lost coverage of a failure class."""
    cases: list[FixtureCase] = []
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FixtureError(f"fixture line {line_no}: invalid JSON: {exc}") from exc
            cases.append(_parse_case(record, line_no))

    if not cases:
        raise FixtureError("fixture is empty")

    covered = {case.failure_class for case in cases}
    missing = [name for name in REQUIRED_CLASSES if name not in covered]
    if missing:
        raise FixtureError(f"fixture has no case for required failure class(es): {', '.join(missing)}")

    return cases


def token_records(case: FixtureCase) -> list[dict]:
    """Rebuilds the worker's token records — whitespace tokenization with absolute
    offsets — so a configuration is replayed exactly as the pipeline would run it."""
    records = []
    offset = 0
    for token in case.tokens:
        records.append({
            "token": token,
            "page_number": case.page_number,
            "char_start": offset,
            "char_end": offset + len(token),
        })
        offset += len(token) + 1
    return records
