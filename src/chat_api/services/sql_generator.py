import re
import logging
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings

logger = logging.getLogger(__name__)

WHITELISTED_TABLES = {
    "document_entities": {"id", "document_id", "entity_type", "entity_value", "normalized_value", "confidence", "page_number", "char_start", "char_end", "created_at", "value_kind", "value_number", "value_number_high", "value_unit", "value_date", "value_date_high"},
    "document_chunks": {"id", "document_id", "chunk_index", "chunk_text", "created_at"},
    "documents": {"id", "tenant_id", "filename", "mime_type", "file_size_bytes", "status", "created_at"},
    "document_text_spans": {"id", "document_id", "page_no", "block_no", "text", "start_offset", "end_offset"},
    "extraction_runs": {"id", "tenant_id", "document_id", "model_version", "status", "started_at"},
}

MAX_SQL_LENGTH = 2000
DEFAULT_LIMIT = 100

_DOCUMENT_NAME_RE = re.compile(r'(?P<as>\bAS\s+)?\bdocument_name\b', re.IGNORECASE)


class SQLValidationError(Exception):
    pass


def _fix_document_name_reference(sql: str) -> str:
    """Deterministically repairs a `document_name` reference the LLM forgot to alias.
    The generator prompt tells the model to JOIN documents AS d and select
    `d.filename AS document_name`, but it sometimes selects the bare, nonexistent
    `document_name` column instead — this only surfaces as a Postgres
    UndefinedColumnError at execution time, which the guardrail then swallows into
    a generic "no sources" reply. Fixed here instead of relying on the LLM."""
    if not re.search(r'\bdocument_entities\b', sql, re.IGNORECASE):
        return sql
    # A reference to fix/support exists either as a bare `document_name` target or as
    # `d.filename` with no `documents` table in scope yet — either needs the `d` alias
    # to resolve, so both must be checked, not just the bare-`document_name` case.
    if not _DOCUMENT_NAME_RE.search(sql) and not re.search(r'\bd\.filename\b', sql, re.IGNORECASE):
        return sql

    # `FROM documents d` (e.g. inside a NOT EXISTS/EXISTS clause) resolves the alias
    # just as well as `JOIN documents d` does — both must count as "already resolved".
    join_match = re.search(r'\b(?:FROM|JOIN)\s+documents\s+(?:AS\s+)?(\w+)', sql, re.IGNORECASE)
    if join_match:
        alias = join_match.group(1)
    else:
        entities_match = re.search(r'\bFROM\s+document_entities\s+(?:AS\s+)?(\w+)?', sql, re.IGNORECASE)
        if not entities_match:
            return sql
        entities_alias = entities_match.group(1) or "document_entities"
        alias = "d"
        join_clause = f" JOIN documents AS {alias} ON {alias}.id = {entities_alias}.document_id"
        insert_pos = entities_match.end()
        sql = sql[:insert_pos] + join_clause + sql[insert_pos:]

    def _replace(m: re.Match) -> str:
        if m.group("as"):
            return m.group(0)  # "AS document_name" names a target alias — already correct
        return f"{alias}.filename AS document_name"

    return _DOCUMENT_NAME_RE.sub(_replace, sql)


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

    async def generate_sql(self, natural_language_query: str, conversation_context: str | None = None, known_entity_types: list[str] | None = None) -> str:
        tables_desc = "\n".join(
            f"- {tbl} ({', '.join(cols)})"
            for tbl, cols in WHITELISTED_TABLES.items()
        )
        context = f"\nConversation context:\n{conversation_context}" if conversation_context else ""
        entity_types_desc = (
            f"\nThis tenant's actual `document_entities.entity_type` values are exactly: {', '.join(known_entity_types)}. "
            "Every `entity_type` filter you write MUST use one of these exact values, verbatim, even if a different "
            "name (e.g. 'EMPLOYER' for a company, 'CANDIDATE' for a person) seems more natural for the question's "
            "wording — pick whichever value in this list is the closest semantic match instead of inventing a new one."
            if known_entity_types else ""
        )

        prompt = f"""You are a SQL query generator for a multi-tenant NER platform.
Generate a SELECT SQL query for the following natural language question.
Only use tables and columns from the whitelist below.
Always include a LIMIT clause.
Never use DDL, INSERT, UPDATE, DELETE, DROP, ALTER, or GRANT.
Never use UNION, subqueries without whitelisted tables, or JOINs on non-whitelisted tables.
When querying `document_entities`, you SHOULD JOIN with `documents` AS d ON d.id = document_entities.document_id and include `d.filename AS document_name` in the SELECT clause.
`document_entities` holds one row per complete logical entity (already reconstructed from BIO tokens), not per token — match on `normalized_value` for entity lookups (e.g. `normalized_value = 'aws'` matches both "AWS" and "Amazon Web Services"). `normalized_value` is always lowercase, so any literal you compare it against must be lowercased too (e.g. `normalized_value = 'natrajan'`, not `'Natrajan'`). For numeric or date comparisons and ranges (e.g. more than N years, before/after a date, salary greater than X), use `value_number` / `value_date` (and `CURRENT_DATE` for "today") rather than parsing `entity_value` or `normalized_value` as text.

A question naming an entity type (use the exact type name given in the question, e.g. "EMAIL", "YEARS_OF_EXP" — never substitute a different type name from these instructions) together with a restriction (a person's name, or an explicit "restrict results to document_id = '...'" clause appended to the question) means BOTH conditions apply together with AND — never drop the `entity_type` filter in favor of the restriction, and never drop the restriction in favor of the type filter.

If the question gives an explicit `document_id = '...'` restriction, that restriction ALREADY scopes the query to the one document about that person — AND only the literal `document_id` onto the `entity_type` filter, and do NOT additionally filter by the person's name (the row you're selecting is the entity value itself, e.g. an email address, not the person's name, so a `normalized_value = '<person>'` filter on that same row will never match). Template (substitute the entity type and document_id given in the actual question — do not reuse these example values):
  "<TYPE> of <person> (restrict results to document_id = '<doc-id>')"
    -> WHERE de.entity_type = '<TYPE>' AND de.document_id = '<doc-id>'

If instead the question only names a person with no explicit document_id restriction, resolve the person to their document via a self-join on `document_entities` before filtering by type (again, substitute the actual entity type and person from the question):
  "<TYPE> of <person>"
    -> SELECT de.entity_value, ... FROM document_entities de
       JOIN document_entities person ON person.document_id = de.document_id AND person.normalized_value = '<person, lowercased>'
       WHERE de.entity_type = '<TYPE>'

The self-join above ONLY applies when the question names a specific, identifiable individual (a proper name, e.g. "Natrajan", "Visakh Rajan"). A generic role/collective noun — "engineers", "candidates", "developers", "people", "employees" — is NOT a person to resolve via self-join; it is only describing which entity_type or value the question is about, and must never appear in a `normalized_value` filter. For these, filter directly on `entity_type` (and `normalized_value` for the skill/value itself, if one is named) with no self-join at all:
  "List the engineers who know Python"
    -> SELECT de.entity_value, ... FROM document_entities de
       WHERE de.entity_type = 'PROGRAMMING_LANGUAGE' AND de.normalized_value = 'python'
  "List candidates with programming language as Python" -> same shape, no self-join, no "candidates" filter.

Negation ("who does NOT ...", "doesn't have ...", "without ..."): never turn this into a positive filter on the negated value — that returns the exact opposite of what was asked. Use `NOT EXISTS` scoped to the document, so it correctly returns people missing the value entirely:
  "Who does not know Java?"
    -> SELECT d.filename AS document_name FROM documents d
       WHERE NOT EXISTS (
         SELECT 1 FROM document_entities de
         WHERE de.document_id = d.id AND de.entity_type = 'PROGRAMMING_LANGUAGE' AND de.normalized_value = 'java'
       )

Intersection ("both X and Y", "X and also Y", "who know all of ..."): this means the SAME document/person must satisfy every condition — never translate it into `normalized_value IN (...)`, which matches ANY one of them (that's what "X or Y" means, not "both"). Use one `EXISTS` per condition, ANDed together:
  "Developers who know both Python and JavaScript"
    -> SELECT d.filename AS document_name FROM documents d
       WHERE EXISTS (SELECT 1 FROM document_entities de WHERE de.document_id = d.id AND de.entity_type = 'PROGRAMMING_LANGUAGE' AND de.normalized_value = 'python')
       AND EXISTS (SELECT 1 FROM document_entities de WHERE de.document_id = d.id AND de.entity_type = 'PROGRAMMING_LANGUAGE' AND de.normalized_value = 'javascript')

Aggregation dimension: read carefully which noun is actually being ranked/counted before choosing your GROUP BY column — "which candidate has the most X" groups by the PERSON (`document_id`), not by X's value; "which X is most common" groups by X's `normalized_value`, not by person. These are different questions even when the wording overlaps:
  "Which candidate lists the most programming languages?" (ranking PEOPLE by a count)
    -> SELECT de.document_id, COUNT(DISTINCT de.normalized_value) AS language_count FROM document_entities de
       WHERE de.entity_type = 'PROGRAMMING_LANGUAGE' GROUP BY de.document_id ORDER BY language_count DESC LIMIT 1
  "Which programming language is most common?" (ranking VALUES by a count) -> GROUP BY de.normalized_value instead.

Free-text fields (DEGREE, ADDRESS, JOB_TITLE, and similar narrative/descriptive types) rarely match a full phrase exactly, because the extracted value is often a longer sentence fragment containing the term rather than the bare term itself — use `normalized_value ILIKE '%<lowercased term>%'` for these instead of `=`. Canonical short-token fields (skills, languages, tools, emails) should keep using exact `=` match as described above:
  "Which candidates have a degree in Computer Science?"
    -> WHERE de.entity_type = 'DEGREE' AND de.normalized_value ILIKE '%computer science%'

When ordering by `value_number` or `value_date` (e.g. "sorted by years of experience"), always append `NULLS LAST` — rows where that column wasn't populated must never outrank rows with a real value:
  "Show candidates sorted by years of experience, descending" -> ... ORDER BY de.value_number DESC NULLS LAST
{entity_types_desc}
Available tables and columns:
{tables_desc}
{context}
Question: {natural_language_query}

Return ONLY the SQL query, no explanations:"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )

        sql = response.choices[0].message.content.strip()
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip()
        return sql

    def validate_sql(self, sql: str) -> str:
        sql = _fix_document_name_reference(sql)

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

    async def _fetch_known_entity_types(self, session: AsyncSession, schema: str) -> list[str]:
        """Ground truth for the prompt's entity_type instruction — without this the
        LLM free-associates a plausible-sounding type name (e.g. 'EMPLOYER', 'CANDIDATE')
        instead of one that actually exists for this tenant."""
        try:
            await session.execute(text(f"SET search_path TO {schema}"))
            result = await session.execute(
                text("SELECT DISTINCT entity_type FROM document_entities ORDER BY entity_type")
            )
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning("Failed to fetch known entity types for prompt grounding: %s", str(e))
            return []

    async def generate_and_execute(self, natural_language_query: str, session: AsyncSession, schema: str, conversation_context: str | None = None) -> list[dict] | None:
        try:
            known_entity_types = await self._fetch_known_entity_types(session, schema)
            sql = await self.generate_sql(natural_language_query, conversation_context, known_entity_types)
            logger.info("Generated SQL: %s", sql)
            sql = self.validate_sql(sql)
            return await self.execute_sql(sql, session, schema)
        except SQLValidationError as e:
            logger.warning("SQL validation failed: %s", str(e))
            return None
        except Exception as e:
            logger.error("SQL execution error: %s", str(e))
            return None
