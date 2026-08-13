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
