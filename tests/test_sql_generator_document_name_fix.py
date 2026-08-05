import pytest

from src.chat_api.services.sql_generator import SQLGenerator

pytestmark = pytest.mark.asyncio


class TestDocumentNameDeterministicFix:
    def setup_method(self):
        self.generator = SQLGenerator()

    def test_bare_document_name_with_existing_join_is_aliased(self):
        sql = (
            "SELECT normalized_value, confidence, document_name "
            "FROM document_entities AS de "
            "JOIN documents AS d ON d.id = de.document_id "
            "WHERE entity_type = 'CONTACT_DETAILS' LIMIT 100;"
        )
        result = self.generator.validate_sql(sql)
        assert "d.filename AS document_name" in result
        assert "SELECT normalized_value, confidence, d.filename AS document_name" in result

    def test_bare_document_name_without_join_gets_join_injected(self):
        sql = "SELECT entity_value, document_name FROM document_entities e WHERE e.entity_type = 'SKILL' LIMIT 50;"
        result = self.generator.validate_sql(sql)
        assert "JOIN documents AS d ON d.id = e.document_id" in result
        assert "d.filename AS document_name" in result

    def test_already_correct_query_is_untouched(self):
        sql = (
            "SELECT de.normalized_value, d.filename AS document_name "
            "FROM document_entities AS de JOIN documents AS d ON d.id = de.document_id LIMIT 10;"
        )
        result = self.generator.validate_sql(sql)
        assert result.count("document_name") == 1
        assert "d.filename AS document_name" in result

    def test_query_without_document_name_is_unaffected(self):
        sql = "SELECT normalized_value FROM document_entities WHERE entity_type = 'SKILL' LIMIT 10;"
        result = self.generator.validate_sql(sql)
        assert "document_name" not in result

    def test_no_bare_document_name_survives_the_fix(self):
        sql = (
            "SELECT normalized_value, confidence, document_name "
            "FROM document_entities AS de "
            "JOIN documents AS d ON d.id = de.document_id "
            "WHERE entity_type = 'CONTACT_DETAILS' LIMIT 100;"
        )
        result = self.generator.validate_sql(sql)
        # Every remaining "document_name" occurrence must be an "AS document_name"
        # alias target — a bare occurrence is what caused the UndefinedColumnError.
        assert result.count("document_name") == result.count("AS document_name")
