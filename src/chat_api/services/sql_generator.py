import re
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings

logger = logging.getLogger(__name__)

WHITELISTED_TABLES = {
    "extracted_entities": {"id", "run_id", "entity_id", "value", "confidence", "normalized_value", "source_span_id", "review_status", "corrected_value", "corrected_by", "correction_notes", "document_id"},
    "document_chunks": {"id", "document_id", "chunk_index", "chunk_text", "created_at"},
    "documents": {"id", "tenant_id", "filename", "mime_type", "file_size_bytes", "status", "created_at"},
    "document_text_spans": {"id", "document_id", "page_no", "block_no", "text", "start_offset", "end_offset"},
    "extraction_runs": {"id", "tenant_id", "document_id", "model_version", "status", "started_at"},
}

MAX_SQL_LENGTH = 2000
DEFAULT_LIMIT = 100


class SQLValidationError(Exception):
    pass


class SQLGenerator:
    def __init__(self):
        if settings.azure_openai_endpoint:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
            self.model = settings.azure_openai_chat_deployment
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.model = "gpt-4o"

    async def generate_sql(self, natural_language_query: str, conversation_context: str | None = None) -> str:
        tables_desc = "\n".join(
            f"- {tbl} ({', '.join(cols)})"
            for tbl, cols in WHITELISTED_TABLES.items()
        )
        context = f"\nConversation context:\n{conversation_context}" if conversation_context else ""

        prompt = f"""You are a SQL query generator for a multi-tenant NER platform.
Generate a SELECT SQL query for the following natural language question.
Only use tables and columns from the whitelist below.
Always include a LIMIT clause.
Never use DDL, INSERT, UPDATE, DELETE, DROP, ALTER, or GRANT.
Never use UNION, subqueries without whitelisted tables, or JOINs on non-whitelisted tables.
When querying `extracted_entities`, you SHOULD JOIN with `documents` ON documents.id = extracted_entities.document_id and include `d.filename AS document_name` in the SELECT clause.

Available tables and columns:
{tables_desc}
{context}
Question: {natural_language_query}

Return ONLY the SQL query, no explanations:"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )

        sql = response.choices[0].message.content.strip()
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()
        return sql

    def validate_sql(self, sql: str) -> str:
        if len(sql) > MAX_SQL_LENGTH:
            raise SQLValidationError(f"SQL exceeds maximum length of {MAX_SQL_LENGTH}")

        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise SQLValidationError("Only SELECT queries are allowed")

        for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE", "EXECUTE"]:
            if keyword in sql_upper.split():
                raise SQLValidationError(f"Disallowed SQL keyword: {keyword}")

        table_refs = re.findall(r'\bFROM\s+(\w+)', sql_upper, re.IGNORECASE) + \
                     re.findall(r'\bJOIN\s+(\w+)', sql_upper, re.IGNORECASE)
        for tbl in table_refs:
            tbl_lower = tbl.lower()
            if tbl_lower not in WHITELISTED_TABLES:
                raise SQLValidationError(f"Table '{tbl}' is not in the whitelist")

        if "LIMIT" not in sql_upper.split("SELECT")[-1] if "SELECT" in sql_upper else True:
            sql = sql.rstrip().rstrip(";") + f" LIMIT {DEFAULT_LIMIT}"
        else:
            limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
            if limit_match:
                limit_val = int(limit_match.group(1))
                if limit_val > 1000:
                    sql = re.sub(r'LIMIT\s+\d+', 'LIMIT 1000', sql, flags=re.IGNORECASE)

        if re.search(r'\bUNION\b', sql_upper):
            raise SQLValidationError("UNION queries are not allowed")

        subquery_tables = re.findall(r'\(\s*SELECT.*?FROM\s+(\w+)', sql, re.IGNORECASE | re.DOTALL)
        for tbl in subquery_tables:
            if tbl.lower() not in WHITELISTED_TABLES:
                raise SQLValidationError(f"Subquery references non-whitelisted table '{tbl}'")

        return sql

    async def execute_sql(self, sql: str, session: AsyncSession, schema: str) -> list[dict]:
        import asyncio
        try:
            async with asyncio.timeout(10):
                result = await session.execute(
                    text(f"SET search_path TO {schema}")
                )
                await session.execute(text("BEGIN READ ONLY"))
                result = await session.execute(text(sql))
                await session.execute(text("COMMIT"))
                rows = result.fetchall()
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
        except asyncio.TimeoutError:
            await session.execute(text("ROLLBACK"))
            logger.warning("SQL query timed out after 10s")
            raise SQLValidationError("Query execution timed out")

    async def generate_and_execute(self, natural_language_query: str, session: AsyncSession, schema: str, conversation_context: str | None = None) -> list[dict] | None:
        try:
            sql = await self.generate_sql(natural_language_query, conversation_context)
            logger.info("Generated SQL: %s", sql)
            sql = self.validate_sql(sql)
            return await self.execute_sql(sql, session, schema)
        except SQLValidationError as e:
            logger.warning("SQL validation failed: %s", str(e))
            return None
        except Exception as e:
            logger.error("SQL execution error: %s", str(e))
            return None
