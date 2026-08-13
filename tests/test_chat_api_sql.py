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


class TestValidatedStatementExecution:
    """verification.md rows 6, 7, 13 — the execution path either runs a validated
    statement read-only, or reports the SQL source as unavailable. It never lets a
    rejected or timed-out statement look like an empty answer.

    Completeness reporting for the same path (rows 56, 57, 58) is covered in
    tests/test_chat_api_sql_retry.py, alongside the FakeSession that drives it."""

    async def test_valid_select_passes_and_executes(self):
        from tests.test_chat_api_sql_retry import SCHEMA, FakeLLM, FakeSession, make_generator

        sql = "SELECT normalized_value FROM document_entities WHERE entity_type = 'SKILL' LIMIT 100"
        session = FakeSession(data_results=[[("python",)]])

        rows = await make_generator(FakeLLM(sql)).generate_and_execute("q", session, SCHEMA)

        assert rows == [{"normalized_value": "python"}]
        assert session.statements.count("BEGIN READ ONLY") == 1
        assert "COMMIT" in session.statements

    async def test_ddl_rejected_and_reported_unavailable(self):
        from src.chat_api.services.sql_generator import SQLGenerationFailed
        from tests.test_chat_api_sql_retry import SCHEMA, FakeLLM, FakeSession, make_generator

        session = FakeSession()
        generator = make_generator(FakeLLM("DROP TABLE document_entities"))

        with pytest.raises(SQLGenerationFailed):
            await generator.generate_and_execute("q", session, SCHEMA)

        # Rejected before execution — the statement never reached the database, and the
        # failure propagates rather than being laundered into an empty row list.
        assert session.data_queries == []

    async def test_execution_timeout_cancels_and_skips_source(self):
        """A statement that outruns the 10s bound is cancelled, the transaction is
        rolled back, and the turn reports the source as unavailable — never as an
        empty answer. The timeout is raised directly here rather than waited out."""
        import asyncio

        from src.chat_api.services.sql_generator import SQLGenerator, SQLValidationError
        from tests.test_chat_api_sql_retry import SCHEMA, FakeSession

        class _TimingOutSession(FakeSession):
            async def execute(self, statement, params=None):
                if str(statement).strip().upper().startswith("SELECT NORMALIZED_VALUE"):
                    raise asyncio.TimeoutError
                return await super().execute(statement, params)

        generator = SQLGenerator.__new__(SQLGenerator)
        session = _TimingOutSession()

        with pytest.raises(SQLValidationError) as exc:
            await generator.execute_sql(
                "SELECT normalized_value FROM document_entities LIMIT 100", session, SCHEMA,
            )

        assert "timed out" in str(exc.value).lower()
        assert "ROLLBACK" in session.statements


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
