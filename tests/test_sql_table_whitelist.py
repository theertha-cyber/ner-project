"""The whitelist check used to resolve only the first identifier after each FROM/JOIN.
A comma-separated table list has exactly one FROM, so

    SELECT d.filename FROM documents d, public.widget_api_keys k WHERE ...

resolved to `documents` alone and the second table was never examined. `public` holds
`tenants`, `tenant_users`, `widget_api_keys`, `entity_definitions`, and `audit_events`.

Covers verification.md rows 4, 8, 9, 10, 11, 12.
"""

import os

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_OPENAI_API_KEY", "test-key")

import pytest

from src.chat_api.services.sql_generator import (
    SQLGenerator,
    SQLValidationError,
    iter_table_references,
)
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface


def _validate(sql: str) -> str:
    return SQLGenerator.__new__(SQLGenerator).validate_sql(sql)


def _names(sql: str) -> list[str]:
    return [ref.name for ref in iter_table_references(sql)]


class TestTableReferenceEnumeration:
    """The routine that feeds the whitelist check. One routine resolves every
    reference — there is no second scan for it to fall out of step with."""

    def test_comma_separated_list_yields_every_entry(self):
        sql = (
            "SELECT d.filename, e.entity_value FROM documents d, document_entities e "
            "WHERE d.id = e.document_id LIMIT 100"
        )
        assert _names(sql) == ["documents", "document_entities"]

    def test_schema_qualifier_is_retained_not_stripped(self):
        sql = "SELECT k.id FROM documents d, public.widget_api_keys k LIMIT 100"
        assert _names(sql) == ["documents", "public.widget_api_keys"]

    def test_joined_table_is_resolved(self):
        sql = (
            "SELECT e.entity_value FROM document_entities e "
            "LEFT JOIN documents d ON d.id = e.document_id LIMIT 100"
        )
        assert _names(sql) == ["document_entities", "documents"]

    def test_subquery_source_is_resolved_by_the_same_routine(self):
        sql = (
            "SELECT * FROM document_entities WHERE document_id IN "
            "(SELECT id FROM documents) LIMIT 100"
        )
        assert _names(sql) == ["document_entities", "documents"]

    def test_derived_table_source_is_resolved(self):
        sql = (
            "SELECT sub.entity_type FROM (SELECT entity_type FROM document_entities) sub "
            "LIMIT 100"
        )
        assert _names(sql) == ["document_entities"]

    def test_from_inside_a_function_call_is_not_a_source(self):
        """`EXTRACT(YEAR FROM value_date)` carries a FROM that belongs to no SELECT."""
        sql = (
            "SELECT EXTRACT(YEAR FROM value_date) FROM document_entities "
            "WHERE value_date IS NOT NULL LIMIT 100"
        )
        assert _names(sql) == ["document_entities"]

    def test_table_name_inside_a_string_literal_is_not_a_source(self):
        sql = (
            "SELECT entity_value FROM document_entities "
            "WHERE normalized_value = 'select 1 from pg_authid' LIMIT 100"
        )
        assert _names(sql) == ["document_entities"]


class TestWhitelistEnforcement:
    def test_non_whitelisted_table_rejected(self):
        with pytest.raises(SQLValidationError) as exc:
            _validate("SELECT * FROM pg_authid LIMIT 1")
        assert "not in the whitelist" in str(exc.value).lower()
        assert "pg_authid" in str(exc.value)

    def test_comma_joined_public_table_rejected(self):
        """The gap this change closes: the second entry of the FROM list was never
        examined, so a cross-tenant relation in `public` passed validation."""
        sql = (
            "SELECT d.filename, k.key_hash FROM documents d, public.widget_api_keys k "
            "WHERE d.tenant_id = k.tenant_id LIMIT 100"
        )
        with pytest.raises(SQLValidationError) as exc:
            _validate(sql)
        assert "public.widget_api_keys" in str(exc.value)

    def test_comma_joined_unqualified_table_rejected(self):
        sql = "SELECT d.filename FROM documents d, tenant_users u WHERE d.id = u.id LIMIT 100"
        with pytest.raises(SQLValidationError) as exc:
            _validate(sql)
        assert "tenant_users" in str(exc.value)

    def test_schema_qualified_whitelisted_name_is_rejected_not_normalised(self):
        """`public.documents` is not `documents` — the qualifier is grounds for
        rejection, never something to drop so the name matches the whitelist."""
        with pytest.raises(SQLValidationError) as exc:
            _validate("SELECT * FROM public.documents LIMIT 10")
        assert "schema-qualified" in str(exc.value).lower()

    def test_subquery_non_whitelisted_table_rejected(self):
        sql = (
            "SELECT * FROM document_entities WHERE document_id IN "
            "(SELECT id FROM public.tenants) LIMIT 100"
        )
        with pytest.raises(SQLValidationError) as exc:
            _validate(sql)
        assert "public.tenants" in str(exc.value)

    def test_function_call_source_rejected(self):
        with pytest.raises(SQLValidationError) as exc:
            _validate("SELECT * FROM generate_series(1, 10) LIMIT 10")
        assert "generate_series" in str(exc.value)

    def test_whitelisted_comma_join_accepted(self):
        """A legitimate comma join must keep working — the fix is a security fix, not
        a recall regression."""
        sql = (
            "SELECT e.entity_value, d.filename AS document_name "
            "FROM document_entities e, documents d "
            "WHERE d.id = e.document_id AND e.entity_type = 'SKILL' LIMIT 100"
        )
        result = _validate(sql)
        assert "LIMIT" in result.upper()

    def test_whitelisted_three_way_comma_join_accepted(self):
        sql = (
            "SELECT e.entity_value FROM document_entities e, documents d, document_chunks c "
            "WHERE d.id = e.document_id AND c.document_id = d.id LIMIT 100"
        )
        assert "LIMIT" in _validate(sql).upper()


class TestRoleSwitchRejection:
    def test_role_switch_statements_rejected(self):
        for sql in (
            "SELECT 1 FROM documents LIMIT 1; SET ROLE postgres",
            "SELECT 1 FROM documents LIMIT 1; SET LOCAL ROLE postgres",
            "SELECT 1 FROM documents LIMIT 1; SET SESSION AUTHORIZATION postgres",
            "SELECT 1 FROM documents LIMIT 1; SET LOCAL SESSION AUTHORIZATION postgres",
        ):
            with pytest.raises(SQLValidationError) as exc:
                _validate(sql)
            assert "SET ROLE" in str(exc.value)

    def test_ordinary_statement_is_not_caught_by_the_role_check(self):
        sql = "SELECT entity_value FROM document_entities WHERE entity_type = 'ROLE' LIMIT 100"
        assert "LIMIT" in _validate(sql).upper()


# ------------------------------------------- the resolved relational surface (rows 22-25, 38)

SURFACE = build_query_surface([
    EntityDefinitionSpec(name="Skill", sql_identifier="e_skill"),
    EntityDefinitionSpec(name="Email", sql_identifier="e_email", cardinality="single"),
    EntityDefinitionSpec(
        name="Years Experience", sql_identifier="e_years_experience",
        cardinality="single", value_kind="number",
    ),
])


def _validate_on_surface(sql: str, surface=SURFACE) -> str:
    return SQLGenerator.__new__(SQLGenerator).validate_sql(sql, surface)


class TestRelationalSurfaceValidation:
    """verification.md rows 22-25 — the accepted relation set is the resolved surface."""

    def test_valid_child_to_subject_join_accepted(self):
        """Row 24 — the shape the prompt teaches: a child table joined to `subject`."""
        sql = (
            "SELECT s.document_id, s.filename, k.value FROM e_skill k "
            "JOIN subject s ON s.document_id = k.document_id "
            "WHERE k.normalized_value = 'python' LIMIT 100"
        )
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_subject_column_of_a_single_definition_accepted(self):
        sql = "SELECT document_id, email, years_experience FROM subject LIMIT 100"
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_relation_off_the_surface_rejected(self):
        """Row 22 — a relation the resolver does not report is not readable."""
        with pytest.raises(SQLValidationError) as exc:
            _validate_on_surface("SELECT value FROM e_unknown LIMIT 10")
        assert "e_unknown" in str(exc.value)

    def test_child_table_retained_from_a_multi_era_rejected(self):
        # `e_email` is `single` now: its values are `subject.email`. The retained table is on
        # disk and unwritten since the flip, so accepting it answers every question with zero
        # rows — the silent wrong answer the surface rule exists to prevent.
        with pytest.raises(SQLValidationError):
            _validate_on_surface("SELECT value FROM e_email LIMIT 10")

    def test_another_tenants_relation_rejected(self):
        """Row 25 — the surface is per-tenant; `e_skill` elsewhere means nothing here."""
        with pytest.raises(SQLValidationError):
            _validate_on_surface(
                "SELECT value FROM e_skill LIMIT 10", build_query_surface([])
            )

    def test_no_surface_at_all_still_rejects_generated_relations(self):
        with pytest.raises(SQLValidationError):
            SQLGenerator.__new__(SQLGenerator).validate_sql("SELECT value FROM e_skill LIMIT 10")


class TestColumnValidation:
    """verification.md rows 23, 38 — the first authoritative column list."""

    def test_undeclared_subject_column_rejected_and_named(self):
        """Row 23 — the rejection has to name the column, or the retry cannot fix it."""
        with pytest.raises(SQLValidationError) as exc:
            _validate_on_surface("SELECT s.salary FROM subject s LIMIT 10")
        assert "salary" in str(exc.value)
        assert "subject" in str(exc.value)

    def test_undeclared_child_column_rejected(self):
        with pytest.raises(SQLValidationError) as exc:
            _validate_on_surface("SELECT k.skill_name FROM e_skill k LIMIT 10")
        assert "skill_name" in str(exc.value)

    def test_undeclared_static_column_rejected(self):
        """Row 38 — the static tables get the same treatment from the same map."""
        with pytest.raises(SQLValidationError) as exc:
            _validate_on_surface("SELECT d.owner_name FROM documents d LIMIT 10")
        assert "owner_name" in str(exc.value)

    def test_column_of_another_relation_on_the_surface_rejected(self):
        # `value` is a child column; `subject` has no such column.
        with pytest.raises(SQLValidationError):
            _validate_on_surface("SELECT s.value FROM subject s LIMIT 10")

    def test_unaliased_table_qualifier_resolves(self):
        with pytest.raises(SQLValidationError):
            _validate_on_surface("SELECT subject.salary FROM subject LIMIT 10")
        assert "LIMIT" in _validate_on_surface(
            "SELECT subject.filename FROM subject LIMIT 10"
        ).upper()


class TestColumnValidationIsPermissiveOnAmbiguity:
    """design.md Decision 6 / Risk 5. The tokenizer is a reference parser, not a full SQL
    parser, so every gap in it must degrade into a database error — retryable, and already
    handled — rather than into rejecting a correct query."""

    def test_select_alias_ordered_on_is_accepted(self):
        sql = (
            "SELECT k.document_id, COUNT(*) AS skill_count FROM e_skill k "
            "GROUP BY k.document_id ORDER BY skill_count DESC LIMIT 10"
        )
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_computed_expression_columns_accepted(self):
        sql = (
            "SELECT s.document_id, EXTRACT(YEAR FROM s.start_date) AS y, "
            "UPPER(s.filename) AS f FROM subject s LIMIT 10"
        )
        # `start_date` is not declared, so this one is a genuine rejection…
        with pytest.raises(SQLValidationError):
            _validate_on_surface(sql)
        # …while the same shape over declared columns passes.
        assert "LIMIT" in _validate_on_surface(
            "SELECT s.document_id, UPPER(s.filename) AS f FROM subject s LIMIT 10"
        ).upper()

    def test_using_join_columns_accepted(self):
        sql = (
            "SELECT s.filename, k.value FROM subject s "
            "JOIN e_skill k USING (document_id) LIMIT 100"
        )
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_derived_table_alias_is_unattributable_and_accepted(self):
        sql = (
            "SELECT t.anything FROM (SELECT document_id AS anything FROM subject) t LIMIT 10"
        )
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_reused_alias_for_two_relations_is_ambiguous_and_accepted(self):
        sql = (
            "SELECT x.value FROM e_skill x WHERE x.document_id IN "
            "(SELECT x.document_id FROM subject x) LIMIT 10"
        )
        assert "LIMIT" in _validate_on_surface(sql).upper()

    def test_unqualified_column_is_never_rejected(self):
        # Attributable in principle here, but a select alias in ORDER BY / HAVING is not, and
        # the two are indistinguishable to a reference parser.
        assert "LIMIT" in _validate_on_surface(
            "SELECT salary FROM subject LIMIT 10"
        ).upper()

    def test_string_literal_containing_a_dot_is_not_a_column_reference(self):
        sql = "SELECT s.filename FROM subject s WHERE s.filename = 'a.b' LIMIT 10"
        assert "LIMIT" in _validate_on_surface(sql).upper()
