import pytest
from src.chat_api.services.sql_generator import SQLGenerator, SQLValidationError

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class TestSQLValidation:
    def setup_method(self):
        self.generator = SQLGenerator()

    def test_6_valid_sql_passes_validation(self):
        sql = "SELECT entity_type, COUNT(*) FROM document_entities GROUP BY entity_type LIMIT 10"
        result = self.generator.validate_sql(sql)
        assert result is not None
        assert "LIMIT" in result.upper()

    def test_7_malicious_sql_rejected(self):
        sql = "DROP TABLE document_entities"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_8_non_whitelisted_table_rejected(self):
        sql = "SELECT * FROM pg_authid LIMIT 1"
        with pytest.raises(SQLValidationError) as exc:
            self.generator.validate_sql(sql)
        assert "not in the whitelist" in str(exc.value).lower()

    def test_9_insert_rejected(self):
        sql = "INSERT INTO document_entities (id) VALUES ('abc')"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_union_rejected(self):
        sql = "SELECT normalized_value FROM document_entities UNION SELECT name FROM documents LIMIT 10"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_limit_enforced_if_missing(self):
        sql = "SELECT * FROM document_entities"
        result = self.generator.validate_sql(sql)
        assert "LIMIT" in result.upper()

    def test_excessive_limit_capped(self):
        sql = "SELECT * FROM document_entities LIMIT 999999"
        result = self.generator.validate_sql(sql)
        assert "LIMIT 1000" in result or "LIMIT 999999" not in result

    def test_subquery_non_whitelisted_rejected(self):
        sql = "SELECT * FROM document_entities WHERE id IN (SELECT id FROM pg_authid) LIMIT 10"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_join_non_whitelisted_rejected(self):
        sql = "SELECT e.* FROM document_entities e JOIN pg_authid p ON e.id = p.id LIMIT 10"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_empty_sql_rejected(self):
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql("")

    def test_max_length_exceeded_rejected(self):
        long_sql = "SELECT * FROM document_entities WHERE 1=1" + " AND x=1" * 1000 + " LIMIT 1"
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(long_sql)

    def test_normalized_value_lookup_passes_validation(self):
        """verification.md row 33: entity lookups match on the canonical value."""
        sql = "SELECT d.filename AS document_name FROM document_entities e JOIN documents d ON d.id = e.document_id WHERE e.normalized_value = 'aws' LIMIT 10"
        result = self.generator.validate_sql(sql)
        assert "LIMIT" in result.upper()

    def test_raw_bio_token_table_is_rejected(self):
        """verification.md row 34: extracted_entities (raw BIO tokens) must not be
        reachable from chat SQL generation — only document_entities is whitelisted."""
        sql = "SELECT * FROM extracted_entities LIMIT 10"
        with pytest.raises(SQLValidationError) as exc:
            self.generator.validate_sql(sql)
        assert "not in the whitelist" in str(exc.value).lower()


class TestSQLPrompt:
    def test_prompt_includes_document_join_instruction(self):
        import inspect
        from src.chat_api.services import sql_generator as mod
        source = inspect.getsource(mod)
        assert "SHOULD" in source, "Prompt must use SHOULD for JOIN instruction"
        assert "AS d" in source or "as d" in source, "Prompt must alias documents as d"
        assert "d.filename AS document_name" in source or "d.filename" in source
        assert "documents" in source.lower()

    def test_prompt_references_document_entities_not_extracted_entities(self):
        import inspect
        from src.chat_api.services import sql_generator as mod
        source = inspect.getsource(mod)
        assert "document_entities" in source
        assert "extracted_entities" not in source
