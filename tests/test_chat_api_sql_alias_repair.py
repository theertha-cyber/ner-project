"""The generator reliably produces the right aggregate shape and then refers to the
aggregated relation by an alias it never declared — `FROM e_money e … SUM(d.value_number)`.
Postgres rejects it, the retry is told to reconsider everything, and it rewrites the query
into a worse shape: the display text instead of the typed column, or no grouping at all.

These cover the deterministic repair that rebinds such a qualifier when exactly one relation
in scope declares the column, and — just as importantly — the cases where it must not guess.
"""

import pytest

from src.chat_api.services.sql_generator import _fix_undefined_alias

pytestmark = [pytest.mark.verification]


class FakeSurface:
    def __init__(self, columns_by_relation):
        self._columns = columns_by_relation

    def columns_by_relation(self):
        return self._columns


MONEY_SURFACE = FakeSurface({
    "e_money": {"document_id", "value", "normalized_value", "value_number", "value_date"},
    "subject": {"document_id", "filename"},
})


class TestRebindsAnUndefinedQualifier:
    def test_the_observed_failure_is_repaired(self):
        """The exact SQL the generator produced in dev, which Postgres rejected with
        `missing FROM-clause entry for table "d"`."""
        broken = (
            "SELECT DATE_TRUNC('quarter', d.value_date) AS quarter, "
            "SUM(e.value_number) AS total_billed "
            "FROM e_money e JOIN subject s ON e.document_id = s.document_id "
            "WHERE e.value_date >= '2026-01-01' GROUP BY quarter LIMIT 100"
        )
        repaired = _fix_undefined_alias(broken, MONEY_SURFACE)

        assert "d.value_date" not in repaired
        assert "e.value_date" in repaired
        # Only the qualifier moves; everything else is untouched.
        assert repaired == broken.replace("d.value_date", "e.value_date")

    def test_every_occurrence_of_the_qualifier_is_rebound(self):
        broken = (
            "SELECT d.value_date, SUM(d.value_number) FROM e_money e "
            "GROUP BY d.value_date LIMIT 100"
        )
        repaired = _fix_undefined_alias(broken, MONEY_SURFACE)

        assert "d." not in repaired
        assert repaired.count("e.") == 3

    def test_relation_queried_without_an_alias_is_a_valid_target(self):
        broken = "SELECT d.value_number FROM e_money LIMIT 100"
        assert "e_money.value_number" in _fix_undefined_alias(broken, MONEY_SURFACE)


class TestRefusesToGuess:
    def test_column_owned_by_two_relations_is_left_alone(self):
        """`document_id` exists on both relations, so nothing here says which was meant.
        Rebinding on a guess would turn a loud failure into a quiet wrong answer."""
        ambiguous = (
            "SELECT x.document_id FROM e_money e "
            "JOIN subject s ON e.document_id = s.document_id LIMIT 100"
        )
        assert _fix_undefined_alias(ambiguous, MONEY_SURFACE) == ambiguous

    def test_column_owned_by_no_relation_in_scope_is_left_alone(self):
        unknown = "SELECT d.invented_column FROM e_money e LIMIT 100"
        assert _fix_undefined_alias(unknown, MONEY_SURFACE) == unknown

    def test_sql_with_no_surface_is_untouched(self):
        sql = "SELECT d.value_date FROM e_money e LIMIT 100"
        assert _fix_undefined_alias(sql, None) == sql

    def test_already_valid_sql_is_untouched(self):
        for sql in (
            "SELECT d.value_date FROM e_money d LIMIT 100",
            "SELECT e.value_number FROM e_money AS e LIMIT 100",
            "SELECT e_money.value_number FROM e_money LIMIT 100",
            "SELECT COUNT(*) FROM e_money LIMIT 100",
        ):
            assert _fix_undefined_alias(sql, MONEY_SURFACE) == sql, sql

    def test_a_qualifier_that_only_partly_matches_is_left_alone(self):
        """One column belongs to e_money and the other to subject, so no single relation
        can own the qualifier — the query means something the repair cannot recover."""
        mixed = "SELECT d.value_number, d.filename FROM e_money e LIMIT 100"
        assert _fix_undefined_alias(mixed, MONEY_SURFACE) == mixed


class TestDoesNotMisreadSql:
    def test_keywords_after_join_are_not_treated_as_aliases(self):
        sql = (
            "SELECT d.value_number FROM e_money e "
            "LEFT JOIN subject s ON e.document_id = s.document_id LIMIT 100"
        )
        assert "e.value_number" in _fix_undefined_alias(sql, MONEY_SURFACE)

    def test_numeric_literals_are_not_mistaken_for_qualifiers(self):
        sql = "SELECT d.value_number FROM e_money e WHERE e.value_number > 1.5 LIMIT 100"
        repaired = _fix_undefined_alias(sql, MONEY_SURFACE)

        assert "1.5" in repaired
        assert "e.value_number > 1.5" in repaired
