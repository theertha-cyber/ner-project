import ast
import inspect

from src.extraction_service.services import semantic_normalizer
from src.extraction_service.services.semantic_normalizer import (
    PARSERS,
    normalize_value,
)


class TestSupportedKindDispatch:
    """Covers verification.md row 3: supported kind is accepted / dispatched."""

    def test_duration_kind_dispatches_duration_parser(self):
        result = normalize_value("5 yrs", "duration", "years")
        assert result is not None
        assert result.value_kind == "duration"

    def test_unsupported_kind_returns_none(self):
        assert normalize_value("anything", "geo", None) is None

    def test_text_kind_returns_none(self):
        assert normalize_value("anything", "text", None) is None


class TestParsersArePureAndOffline:
    """Covers verification.md row 7. Only the registered parsers themselves must be
    pure/offline — `load_entity_type_config` is a separate DB-reading helper, not a
    parser, and is intentionally excluded from this check."""

    def test_parsers_reference_no_network_db_or_llm_names(self):
        forbidden = {"requests", "httpx", "openai", "asyncpg", "psycopg2", "socket", "conn", "session", "db"}
        for kind, parser in PARSERS.items():
            source = inspect.getsource(parser)
            tree = ast.parse(source)
            names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            assert not (names & forbidden), f"parser for kind={kind!r} references forbidden name(s)"

    def test_deterministic_repeated_calls(self):
        first = normalize_value("two and a half years", "duration", "years")
        second = normalize_value("two and a half years", "duration", "years")
        assert first.number == second.number
        assert first.unit == second.unit


class TestNumericAndDurationNormalization:
    """Covers verification.md rows 8-11."""

    def test_spelled_out_fractional_duration(self):
        result = normalize_value("two and a half years", "duration", "years")
        assert result.number == 2.5
        assert result.unit == "years"

    def test_digit_form_with_unit_suffix(self):
        result = normalize_value("5 yrs", "duration", "years")
        assert result.number == 5.0

    def test_source_unit_differs_from_canonical_unit(self):
        result = normalize_value("2 months", "duration", "days")
        assert result.number == 60.0
        assert result.unit == "days"

    def test_thousands_separators_and_magnitude_suffixes(self):
        a = normalize_value("1,200,000", "money", "INR")
        b = normalize_value("12 lakh", "money", "INR")
        assert a.number == 1200000.0
        assert a.unit == "INR"
        assert b.number == 1200000.0
        assert b.unit == "INR"


class TestOpenBoundsAndClosedRanges:
    """Covers verification.md rows 12-14."""

    def test_open_lower_bound(self):
        result = normalize_value("5+ years", "duration", "years")
        assert result.number == 5.0
        assert result.number_high is None

    def test_phrased_open_bound(self):
        result = normalize_value("more than three years", "duration", "years")
        assert result.number == 3.0

    def test_closed_range(self):
        result = normalize_value("3-5 years", "duration", "years")
        assert result.number == 3.0
        assert result.number_high == 5.0


class TestDateNormalization:
    """Covers verification.md rows 15-17."""

    def test_full_date(self):
        result = normalize_value("15 March 2027", "date", None)
        assert result.date.isoformat() == "2027-03-15"

    def test_month_and_year_only(self):
        result = normalize_value("March 2027", "date", None)
        assert result.date.isoformat() == "2027-03-01"

    def test_unresolvable_date_yields_none(self):
        assert normalize_value("next spring", "date", None) is None


class TestParserRegistryCoversSupportedKinds:
    def test_every_non_text_kind_has_a_parser(self):
        for kind in semantic_normalizer.SUPPORTED_KINDS - {"text"}:
            assert kind in PARSERS
