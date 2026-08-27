"""Covers verification.md rows 24-28.

`_read_number` tried `_digits_to_number` (anchored, so it only reads a value that is
entirely a numeral) and then `_words_to_number` (alphabetic tokens only, so it never
consults the digit). "2 years of experience," therefore typed as nothing while
"2+ years of experience" typed as 2.0 — the same fact, opposite outcomes."""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

import pytest

from src.extraction_service.services.semantic_normalizer import normalize_value


class TestLeadingNumeralFollowedByProse:
    """Row 24 — the exact stored value from `Resume RENJIEAPEN.pdf`."""

    def test_two_years_of_experience_parses(self):
        result = normalize_value("2 years of experience,", "duration", "years")

        assert result is not None
        assert result.value_kind == "duration"
        assert result.number == 2.0
        assert result.unit == "years"

    def test_the_trimmed_form_parses_identically(self):
        assert normalize_value("2 years of experience", "duration", "years").number == 2.0

    def test_a_number_kind_also_reads_the_leading_numeral(self):
        result = normalize_value("3 open positions", "number", None)

        assert result is not None
        assert result.number == 3.0

    def test_a_magnitude_suffix_after_the_numeral_still_multiplies(self):
        result = normalize_value("12 lakh per annum", "money", "inr")

        assert result is not None
        assert result.number == 1_200_000.0


class TestEquivalentSurfaceFormsAgree:
    """Row 25."""

    def test_plus_and_bare_numeral_produce_the_same_value(self):
        with_plus = normalize_value("2+ years of experience", "duration", "years")
        without_plus = normalize_value("2 years of experience", "duration", "years")

        assert with_plus.number == without_plus.number == 2.0

    @pytest.mark.parametrize("value", [
        "5 years",
        "5 years of experience",
        "5 years of experience,",
        "5+ years of experience",
    ])
    def test_a_family_of_five_year_phrasings_all_read_five(self, value):
        assert normalize_value(value, "duration", "years").number == 5.0


class TestMergedMultiTokenDuration:
    """Row 26 — what the reconstruction fix now hands the parser."""

    def test_two_and_a_half_years_reads_as_two_point_five(self):
        result = normalize_value("two and a half years", "duration", "years")

        assert result is not None
        assert result.number == 2.5
        assert result.unit == "years"

    def test_a_mixed_digit_and_word_phrase_prefers_the_word_sum(self):
        """`_words_to_number` runs before the leading-numeral fallback, so a phrase that
        spells its number out is not truncated to a stray digit."""
        assert normalize_value("two and a half years", "duration", "years").number == 2.5


class TestExistingParsesAreUnchanged:
    """Row 27 — the regression set. Every one of these parsed before the change."""

    @pytest.mark.parametrize("value,kind,unit,expected", [
        ("5 years", "duration", "years", 5.0),
        ("2.5 years", "duration", "years", 2.5),
        ("3 yrs", "duration", "years", 3.0),
        ("over 4 years", "duration", "years", 4.0),
        ("more than 6 years", "duration", "years", 6.0),
        ("at least 7 years", "duration", "years", 7.0),
        ("two", "duration", "years", 2.0),
        ("half years", "duration", "years", 0.5),
        ("ten", "number", None, 10.0),
        ("twenty five", "number", None, 25.0),
        ("1,250", "number", None, 1250.0),
        ("12k", "money", "inr", 12_000.0),
        ("3 crore", "money", "inr", 30_000_000.0),
    ])
    def test_value_is_unchanged(self, value, kind, unit, expected):
        result = normalize_value(value, kind, unit)

        assert result is not None
        assert result.number == expected

    def test_ranges_still_produce_both_bounds(self):
        result = normalize_value("2-5 years", "duration", "years")

        assert result.number == 2.0
        assert result.number_high == 5.0

    def test_month_unit_conversion_is_unchanged(self):
        result = normalize_value("18 months", "duration", "years")

        assert result.unit == "years"
        assert result.number == pytest.approx(18 * 30 / 365)

    def test_dates_are_unaffected(self):
        result = normalize_value("2021-06-15", "date", None)

        assert result is not None
        assert result.value_kind == "date"
        assert result.date.isoformat() == "2021-06-15"

    def test_booleans_are_unaffected(self):
        assert normalize_value("yes", "boolean", None).number == 1.0
        assert normalize_value("no", "boolean", None).number == 0.0


class TestGenuinelyUnparseableValuesStillYieldNothing:
    """Row 28 — the fallback must not start inventing numbers."""

    @pytest.mark.parametrize("value", [
        "experience",
        "years of experience",
        "several years",
        "",
        "   ",
        "N/A",
    ])
    def test_no_typed_value_is_produced(self, value):
        assert normalize_value(value, "duration", "years") is None

    def test_a_numeral_in_the_middle_is_not_read_as_the_value(self):
        """The fallback anchors at the start of the phrase, so a trailing identifier
        cannot masquerade as a duration."""
        assert normalize_value("employee id 4471", "duration", "years") is None

    def test_text_kind_never_produces_a_typed_value(self):
        assert normalize_value("2 years of experience", "text", None) is None

    def test_unknown_kind_never_produces_a_typed_value(self):
        assert normalize_value("2 years of experience", "colour", None) is None
