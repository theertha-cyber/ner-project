import re
import logging
import time
from dataclasses import dataclass, field
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

# Bounds on everything the recovery loop puts into a prompt or a log line.
MAX_ERROR_FEEDBACK_CHARS = 300
MAX_SAMPLE_VALUE_CHARS = 60

# Marks a defect as the filename-filter kind rather than the entity_type kind, so the
# retry feedback can explain the right thing. Both share SQLAttempt.defect.
_FILENAME_DEFECT_PREFIX = "filename:"


class SQLAttemptOutcome:
    """Closed set of per-attempt outcomes. `EMPTY_WITH_DEFECT` is the *only* way a
    zero-row result becomes retryable — a zero-row result with no deterministic
    defect is classified SUCCESS, because nothing in this architecture can tell
    "genuinely no matching records" from "the query misrepresented the question",
    and a retry prompted by row count alone pushes the model to loosen filters
    until something — anything — comes back. See design.md Decision 3."""

    SUCCESS = "success"
    GENERATION_ERROR = "generation_error"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    EMPTY_WITH_DEFECT = "empty_with_defect"


RETRYABLE_OUTCOMES = frozenset({
    SQLAttemptOutcome.GENERATION_ERROR,
    SQLAttemptOutcome.VALIDATION_ERROR,
    SQLAttemptOutcome.EXECUTION_ERROR,
    SQLAttemptOutcome.EMPTY_WITH_DEFECT,
})


@dataclass
class SQLAttempt:
    """One pass of generate -> validate -> execute -> classify."""

    attempt: int  # 1-based
    max_attempts: int
    outcome: str
    sql: str | None = None
    row_count: int | None = None
    error: str | None = None
    defect: str | None = None

    def as_trace_dict(self) -> dict:
        return {
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "outcome": self.outcome,
            "sql": self.sql,
            "row_count": self.row_count,
            "error": self.error,
            "defect": self.defect,
        }


class SQLGenerationFailed(Exception):
    """Raised when every attempt failed. Deliberately an exception rather than a
    `None` return: `run_tool` converts it into a `ToolResult.error`, which is what
    makes a failed structured retrieval distinguishable downstream from one that
    legitimately found nothing. A legitimate empty result still returns []."""

    def __init__(self, attempts: list[SQLAttempt]):
        self.attempts = attempts
        last = attempts[-1] if attempts else None
        detail = f"{last.outcome}: {last.error or last.defect or ''}".strip(": ") if last else "no attempts"
        super().__init__(f"SQL generation failed after {len(attempts)} attempt(s) ({detail})")


@dataclass
class EntityProfile:
    """What the generator is told about this tenant's data. `entity_types` is the
    complete list; `samples` is bounded and may omit a type entirely (e.g. one whose
    rows all carry a NULL normalized_value)."""

    entity_types: list[str] = field(default_factory=list)
    samples: dict[str, list[str]] = field(default_factory=dict)


# Strips SQLAlchemy's echo of the executed statement and its bound parameters, which
# `DBAPIError.__str__` appends. Without this the retry prompt — and the log line —
# would carry tenant values back out for no diagnostic benefit.
_DRIVER_ECHO_RE = re.compile(r"\[(?:SQL|parameters):.*", re.DOTALL)

# Only positive equality against a literal proves a type mismatch. `!=`/`<>` against a
# nonexistent type matches everything rather than nothing, so it is never a defect.
_ENTITY_TYPE_EQ_RE = re.compile(r"entity_type\s*=\s*'([^']*)'", re.IGNORECASE)
_ENTITY_TYPE_IN_RE = re.compile(r"entity_type\s+IN\s*\(([^)]*)\)", re.IGNORECASE)
_QUOTED_LITERAL_RE = re.compile(r"'([^']*)'")


def _sanitize_error(exc: BaseException) -> str:
    """Renders an exception into a single bounded line safe to put in a prompt."""
    message = _DRIVER_ECHO_RE.sub("", str(exc)).split("\n", 1)[0].strip()
    text_out = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
    if len(text_out) > MAX_ERROR_FEEDBACK_CHARS:
        text_out = text_out[: MAX_ERROR_FEEDBACK_CHARS - 1].rstrip() + "…"
    return text_out


def _entity_type_defect(sql: str, entity_types: list[str]) -> str | None:
    """Returns the first `entity_type` literal in `sql` that does not exist for this
    tenant, or None. Such a comparison cannot match any row whatever the data holds,
    so a zero-row result from it is explained rather than guessed at. Returns None
    when the tenant's type list is unavailable — an empty list means "we don't know",
    never "no type exists"."""
    if not entity_types:
        return None

    known = {t.upper() for t in entity_types}
    literals: list[str] = list(_ENTITY_TYPE_EQ_RE.findall(sql))
    for group in _ENTITY_TYPE_IN_RE.findall(sql):
        literals.extend(_QUOTED_LITERAL_RE.findall(group))

    for literal in literals:
        if literal and literal.upper() not in known:
            return literal
    return None


# Positive filters on `filename`. Only `=`/`ILIKE`/`LIKE` against a literal narrow the
# result set to files whose name must contain that text; negations and comparisons
# against columns are not evidence of anything.
_FILENAME_FILTER_RE = re.compile(
    r"(?:\w+\.)?filename\s+(?:I?LIKE)\s*'([^']*)'|(?:\w+\.)?filename\s*=\s*'([^']*)'",
    re.IGNORECASE,
)


def _filename_filter_literals(sql: str) -> list[str]:
    """The literals a query requires `documents.filename` to match, with any SQL
    wildcards stripped so the caller can test them against real filenames."""
    literals = []
    for like_literal, eq_literal in _FILENAME_FILTER_RE.findall(sql):
        literal = (like_literal or eq_literal).strip("%").strip()
        if literal:
            literals.append(literal)
    return literals


_DOCUMENT_NAME_RE = re.compile(r'(?P<as>\bAS\s+)?\bdocument_name\b', re.IGNORECASE)
_DESC_WITHOUT_NULLS_RE = re.compile(r'\bDESC\b(?!\s+NULLS\b)', re.IGNORECASE)


def _force_nulls_last_on_desc(sql: str) -> str:
    """Appends NULLS LAST to every descending sort that doesn't already specify it.
    Postgres sorts NULLs FIRST under DESC, so any ranking over `value_number` /
    `value_date` — or an aggregate of them, which is NULL for a group where nothing
    parsed — puts the unparsed rows above the real answer. The prompt asks for
    NULLS LAST, but the model reliably omits it when ordering by a select alias
    rather than the column, so it is enforced here instead."""
    return _DESC_WITHOUT_NULLS_RE.sub("DESC NULLS LAST", sql)


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


def _render_attempt_feedback(attempts: list[SQLAttempt]) -> str:
    """Renders prior attempts into the corrective block appended to a retry prompt.
    At temperature 0 a retry without the previous SQL in front of it regenerates the
    same query and burns the budget, so the SQL is always included."""
    if not attempts:
        return ""

    blocks = []
    for a in attempts:
        lines = [f"Attempt {a.attempt} SQL:", (a.sql or "(no SQL was produced)")[:MAX_SQL_LENGTH]]
        if a.outcome == SQLAttemptOutcome.EMPTY_WITH_DEFECT:
            lines.append(f"Execution result: {a.row_count or 0} rows returned.")
            if a.defect and a.defect.startswith(_FILENAME_DEFECT_PREFIX):
                literal = a.defect[len(_FILENAME_DEFECT_PREFIX):]
                lines.append(
                    f"This query required documents.filename to match '{literal}', but no "
                    "document in this tenant has that in its filename, so it could not have "
                    "matched anything. Filenames are not the subject's name — if you meant "
                    "to constrain to a named person, join document_entities again on the "
                    "same document_id using the entity type that holds people's names and "
                    "match that row's normalized_value instead."
                )
            else:
                lines.append(
                    f"This query filtered on entity_type '{a.defect}', which does not exist for "
                    "this tenant, so it could not have matched anything."
                )
        elif a.outcome == SQLAttemptOutcome.VALIDATION_ERROR:
            lines.append(f"Rejected by the SQL validation layer: {a.error}")
        elif a.outcome == SQLAttemptOutcome.EXECUTION_ERROR:
            lines.append(f"Database error: {a.error}")
        else:
            lines.append(f"Could not produce a usable query: {a.error}")
        blocks.append("\n".join(lines))

    return (
        "\n\n## Previous attempts (all failed — do not repeat them)\n\n"
        + "\n\n".join(blocks)
        + "\n\nThe previous attempt did not produce a useful result. Reconsider the entity "
        "types, values, operators, joins, filters, and other assumptions, and generate a "
        "corrected query. Do not re-emit a query that failed above.\n"
    )


class SQLGenerator:
    def __init__(self):
        # Read once; `sql_max_attempts = 1` is the config-only rollback to the
        # pre-existing one-shot behaviour. This is the only place the cap is read.
        self.max_attempts = max(1, settings.sql_max_attempts)
        self.sample_values_per_type = max(0, settings.sql_entity_sample_values_per_type)
        self.sample_max_values = max(0, settings.sql_entity_sample_max_values)
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

    def _render_entity_profile(self, profile: EntityProfile | None) -> str:
        """Renders the tenant's types, each with a bounded sample of the values that
        actually occur under it. Showing real values is the highest-leverage input to
        first-attempt success: the model's hardest job on this data is guessing how a
        concept is spelled, and a sample replaces that guess with evidence."""
        if not profile or not profile.entity_types:
            return ""

        lines = [
            "",
            "The only `entity_type` values that exist for this tenant are listed below, each with "
            "a few representative values drawn from the tenant's own data. Questions rarely use "
            "these names verbatim, so map the wording onto whichever type fits best — a type not "
            "on this list matches nothing at all, however natural its name sounds. The sample is "
            "partial: a value's absence from it does not mean the value is absent from the data, "
            "but the samples do show how values under that type are actually written.",
            "",
            "Available entity types:",
            "",
        ]
        for entity_type in profile.entity_types:
            lines.append(f"{entity_type}")
            for value in profile.samples.get(entity_type, []):
                lines.append(f"- {value}")
        lines.append("")
        return "\n".join(lines)

    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_context: str | None = None,
        entity_profile: EntityProfile | None = None,
        previous_attempts: list[SQLAttempt] | None = None,
    ) -> str:
        tables_desc = "\n".join(
            f"- {tbl} ({', '.join(cols)})"
            for tbl, cols in WHITELISTED_TABLES.items()
        )
        context = f"\nConversation context:\n{conversation_context}" if conversation_context else ""
        entity_types_desc = self._render_entity_profile(entity_profile)
        feedback = _render_attempt_feedback(previous_attempts or [])

        prompt = f"""You are a SQL query generator for a multi-tenant NER platform.
Generate a SELECT SQL query answering the natural language question below.

## The data model

Documents are uploaded files; entities are the structured facts extracted from them. Each row in
`document_entities` is one complete logical fact found in one document — an email address, a skill,
a job title — identified by `entity_type` (which kind of fact) and carrying its text in
`entity_value` (verbatim, as it appeared) and `normalized_value` (lowercased and canonicalised, so
'aws' matches both "AWS" and "Amazon Web Services").

The single most important thing to understand: **`document_id` is the identity of the subject**.
One document describes one subject — a candidate, a contract, an invoice — and every entity sharing
a `document_id` is a fact about that same subject. So any question about a *person or subject*
(who has X, who lacks Y, who has the most Z, whose X is highest) is really a question about
*documents*, answered by asking what does or doesn't exist among the entities sharing that
`document_id`. Reason at that level rather than filtering rows in isolation — a set of rows matching
separate conditions is not the same as one subject satisfying all of them.

**Your result set is the entire evidence for the final answer.** These rows are handed to another
model that must answer the user's question using nothing else — it cannot see your SQL. A condition
written in `WHERE` filters the rows and is then thrown away, so a result of bare filenames proves
nothing: asked "who knows Python", that model receives a list of documents with no mention of Python
anywhere and can only reply that it doesn't know. So **select the facts that justify each row**, not
merely the identity of what matched. Where a subject has a name entity, include it too — an answer
should be able to say "Reshma U", not "Resume-1a2b.pdf".

With that in mind, what the question returns decides the query's shape:

- **Facts** ("her email", "every company named", "which languages does X know") — select the entity
  rows themselves, joined to `documents` for identification. Scope them to a subject by their shared
  `document_id`.
- **Subjects filtered by what they have** ("who knows Python", "who knows both X and Y") — join the
  matching entity rows and project their values, so each row carries the evidence for its own
  inclusion. Use `EXISTS` for any *additional* conditions you only need to test rather than show.
- **Subjects filtered by what they lack** ("who doesn't know Java") — here the justification is an
  absence and cannot be shown, so `NOT EXISTS` over the entity rows is right; select the subject's
  identity and name.
- **Counts and rankings** ("how many know Python", "who lists the most languages", "most common
  language") — aggregate over the entity rows directly. `EXISTS` only reports whether something is
  there, so nothing countable survives it and a ranking built on it has nothing real to sort by.

## Reasoning guidelines

Translate the meaning of the question, not its surface words. A few things follow from the model above:

- **Every condition in the question is a real constraint.** They compose with AND; dropping one, or
  substituting one for another, silently answers a different question than the one asked.
- **English quantifiers are set operations over subjects.** "Both X and Y" means one subject
  satisfies each condition (typically an `EXISTS` per condition); "X or Y" means either suffices;
  "not X" / "without X" means the subject has no such entity at all (`NOT EXISTS`) — never a
  positive filter on the negated value, which returns precisely the opposite set.
- **Distinguish what identifies the subject from what you're reading off it.** A row holds one fact
  and only its own value: the row carrying someone's email contains the email, never their name. So
  a person's name can never be a filter on the row you're selecting — asking for
  `entity_type = 'EMAIL' AND normalized_value = '<their name>'` describes a row that cannot exist,
  and always returns nothing. Their name lives in a *different* row of the same document, so it
  identifies the subject only through the shared `document_id`. Words for a category of subject
  ("candidates", "engineers", "people") aren't values at all — they say who is being asked about,
  and belong in no filter. Only concrete values named in the question are matched directly.
- **`documents.filename` is never the subject's name.** Filenames are whatever the uploader
  happened to call the file — "Resume 4.pdf", "CV_final_v2.pdf", a bare hash — and a person named
  in the question is almost never in one. `d.filename ILIKE '%<their name>%'` therefore returns
  nothing while looking perfectly reasonable, which is the single most common way a query for a
  named subject silently comes back empty. To constrain to a named person, join
  `document_entities` again on the same `document_id` with whichever listed entity type holds
  people's names, and match *that* row's `normalized_value` (which is lowercased and
  punctuation-stripped, so compare against a lowercased literal, and use `ILIKE '%…%'` when the
  question gives only part of the name). `filename` is for identifying a result to the reader —
  select it, never filter on it.
- **When aggregating, group by exactly the thing being ranked and nothing else.** Grouping by
  subject (`document_id`) ranks people; grouping by `normalized_value` ranks the values themselves —
  similar wording, opposite questions. Every extra column in the GROUP BY changes what one row
  means, so a superlative about people ("who lists the most languages") splits into one row per
  person *per language* if the value is grouped too, and no longer answers the question. Select only
  the grouping key and the aggregate itself — pulling in an extra descriptive column drags it into
  the GROUP BY and silently splits the groups apart. A singular superlative wants a single row.
- **Match values at the right precision.** Short canonical values (skills, languages, tools, emails)
  compare cleanly with `=` against a lowercased literal. Narrative values (degrees, addresses, job
  titles) are almost never stored as the bare term — a degree is extracted as "B.Tech in Computer
  Science and Engineering", an address as a whole postal line — so `=` finds nothing and a substring
  match (`ILIKE '%…%'`) is what actually retrieves them.
- **Prefer the typed columns for anything quantitative.** `value_number` / `value_date` hold parsed
  numeric and date values (with `CURRENT_DATE` available for "today"); comparing or ordering the raw
  text instead gives wrong results. They are NULL wherever a value couldn't be parsed, so a subject
  with several such entities is best summarised with an aggregate (`MAX(value_number)`) rather than
  read from an arbitrary row.

Prefer the simplest query that faithfully expresses the question. Whenever the result is a list of
facts or subjects, identify where each came from: you SHOULD JOIN `documents` AS d ON
d.id = document_entities.document_id and select `d.filename AS document_name` alongside it. (An
aggregate is the exception — there the grouping key and the aggregate are the whole answer, and an
extra column would only distort the grouping.)

Because the person's own name is just another entity row, reaching it means joining
`document_entities` again on the same `document_id` with the type that holds names, left-joined so a
subject whose name was never extracted still appears.

## Hard constraints

Only use tables and columns from the whitelist below.
Always include a LIMIT clause. Unless the question itself asks for a specific number of results
("the top 3", "who has the most"), leave room for every answer — use `LIMIT {DEFAULT_LIMIT}` rather
than a small number that would silently truncate the result.
Never use DDL, INSERT, UPDATE, DELETE, DROP, ALTER, or GRANT.
Never use UNION, subqueries without whitelisted tables, or JOINs on non-whitelisted tables.
{entity_types_desc}
Available tables and columns:
{tables_desc}
{context}{feedback}
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
        sql = _force_nulls_last_on_desc(sql)

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

    async def _fetch_entity_value_samples(self, session: AsyncSession, schema: str) -> dict[str, list[str]]:
        """Bounded, representative values per entity type. Ranked by frequency so the
        *dominant* spelling surfaces — which is the one worth matching against on a
        dataset with fragmented vocabulary. Three hard caps apply: per-type count,
        total count, and per-value length. The ROW_NUMBER() window is applied over the
        grouped counts, so the outer LIMIT can never distort the ranking."""
        if self.sample_values_per_type == 0 or self.sample_max_values == 0:
            return {}
        try:
            await session.execute(text(f"SET search_path TO {schema}"))
            result = await session.execute(
                text(
                    """
                    SELECT entity_type, normalized_value
                    FROM (
                        SELECT entity_type,
                               normalized_value,
                               ROW_NUMBER() OVER (
                                   PARTITION BY entity_type
                                   ORDER BY COUNT(*) DESC, normalized_value
                               ) AS rn
                        FROM document_entities
                        WHERE normalized_value IS NOT NULL AND normalized_value <> ''
                        GROUP BY entity_type, normalized_value
                    ) ranked
                    WHERE rn <= :per_type
                    ORDER BY entity_type, rn
                    LIMIT :total
                    """
                ),
                {"per_type": self.sample_values_per_type, "total": self.sample_max_values},
            )
            samples: dict[str, list[str]] = {}
            for entity_type, value in result.fetchall():
                samples.setdefault(entity_type, []).append(str(value)[:MAX_SAMPLE_VALUE_CHARS])
            return samples
        except Exception as e:
            logger.warning("Failed to fetch entity value samples for prompt grounding: %s", str(e))
            return {}

    async def _fetch_entity_profile(self, session: AsyncSession, schema: str) -> EntityProfile:
        """Fetched once per invocation and reused by every attempt, so a retry differs
        from its predecessor only by the feedback block. The type list is fetched
        separately from the samples so a type whose rows all carry a NULL
        normalized_value is still named in the prompt."""
        entity_types = await self._fetch_known_entity_types(session, schema)
        samples = await self._fetch_entity_value_samples(session, schema)
        return EntityProfile(entity_types=entity_types, samples=samples)

    async def _filename_defect(self, sql: str, session: AsyncSession, schema: str) -> str | None:
        """Returns the first `filename` literal the query requires that no document in
        this tenant actually carries, or None.

        A named person is almost never in a filename ("Resume 4.pdf"), so a query that
        constrains on one returns zero rows while looking correct — the failure this
        catches. Testing the literal against real filenames rather than banning the
        filter outright keeps a genuine "in Resume 4.pdf" query working: that literal
        does match a document, so it is not a defect, and a zero-row result from it
        stays a real answer."""
        literals = _filename_filter_literals(sql)
        if not literals:
            return None
        try:
            await session.execute(text(f"SET search_path TO {schema}"))
            for literal in literals:
                result = await session.execute(
                    text("SELECT 1 FROM documents WHERE filename ILIKE :pattern LIMIT 1"),
                    {"pattern": f"%{literal}%"},
                )
                if result.first() is None:
                    return f"{_FILENAME_DEFECT_PREFIX}{literal}"
        except Exception as e:
            logger.warning("Filename defect check failed: %s", _sanitize_error(e))
            return None
        return None

    @staticmethod
    async def _rollback_quietly(session: AsyncSession) -> None:
        """Best-effort transaction reset between attempts. A failure here must not
        replace the execution error the caller is about to report."""
        try:
            await session.execute(text("ROLLBACK"))
        except Exception as e:
            logger.warning("Rollback between SQL attempts failed: %s", _sanitize_error(e))

    async def _run_attempt(
        self,
        attempt_number: int,
        natural_language_query: str,
        session: AsyncSession,
        schema: str,
        conversation_context: str | None,
        profile: EntityProfile,
        previous_attempts: list[SQLAttempt],
    ) -> tuple[SQLAttempt, list[dict] | None]:
        """One generate -> validate -> execute -> classify pass. `schema` is passed in
        already bound from authenticated request context and is only ever forwarded;
        nothing here derives it from generated SQL or from the question."""
        def record(outcome: str, **kw) -> SQLAttempt:
            return SQLAttempt(
                attempt=attempt_number, max_attempts=self.max_attempts, outcome=outcome, **kw
            )

        try:
            sql = await self.generate_sql(natural_language_query, conversation_context, profile, previous_attempts)
        except Exception as e:
            return record(SQLAttemptOutcome.GENERATION_ERROR, error=_sanitize_error(e)), None

        if not sql or not sql.strip():
            return record(
                SQLAttemptOutcome.GENERATION_ERROR,
                sql=sql,
                error="the generator returned no usable query text",
            ), None

        try:
            validated_sql = self.validate_sql(sql)
        except SQLValidationError as e:
            return record(SQLAttemptOutcome.VALIDATION_ERROR, sql=sql, error=_sanitize_error(e)), None

        try:
            rows = await self.execute_sql(validated_sql, session, schema)
        except Exception as e:
            # `execute_sql` opens a READ ONLY transaction and only commits on success,
            # so a failed statement leaves the session in an aborted transaction. That
            # was harmless when there was one attempt and the session was then dropped;
            # with a retry, the next attempt's `SET search_path` would fail with
            # "current transaction is aborted" and mask the real error.
            await self._rollback_quietly(session)
            return record(SQLAttemptOutcome.EXECUTION_ERROR, sql=validated_sql, error=_sanitize_error(e)), None

        if rows:
            return record(SQLAttemptOutcome.SUCCESS, sql=validated_sql, row_count=len(rows)), rows

        defect = _entity_type_defect(validated_sql, profile.entity_types)
        if defect is None:
            defect = await self._filename_defect(validated_sql, session, schema)
        if defect is not None:
            return record(
                SQLAttemptOutcome.EMPTY_WITH_DEFECT, sql=validated_sql, row_count=0, defect=defect
            ), None

        # Zero rows with nothing wrong with the query: a real answer, not a failure.
        return record(SQLAttemptOutcome.SUCCESS, sql=validated_sql, row_count=0), rows

    async def generate_and_execute(
        self,
        natural_language_query: str,
        session: AsyncSession,
        schema: str,
        conversation_context: str | None = None,
        attempt_sink: list | None = None,
        deadline: float | None = None,
    ) -> list[dict] | None:
        """Bounded generate/validate/execute recovery loop. Returns rows on the first
        successful attempt — including an empty list for a legitimate zero-row result —
        and raises `SQLGenerationFailed` when every attempt failed. Every attempt goes
        through the same `validate_sql` and `execute_sql` as the first.

        `schema` is bound here, once, from the caller's authenticated request context
        and is never reassigned inside the loop, so no attempt can change which tenant
        is queried."""
        profile = await self._fetch_entity_profile(session, schema)
        attempts: list[SQLAttempt] = []

        for attempt_number in range(1, self.max_attempts + 1):
            if attempt_number > 1 and deadline is not None and time.monotonic() >= deadline:
                logger.warning(
                    "sql_attempt schema=%s attempt=%d/%d outcome=abandoned reason=deadline_exhausted",
                    schema, attempt_number, self.max_attempts,
                )
                break

            attempt, rows = await self._run_attempt(
                attempt_number, natural_language_query, session, schema,
                conversation_context, profile, attempts,
            )
            attempts.append(attempt)
            if attempt_sink is not None:
                attempt_sink.append(attempt.as_trace_dict())

            log = logger.info if attempt.outcome == SQLAttemptOutcome.SUCCESS else logger.warning
            log(
                "sql_attempt schema=%s attempt=%d/%d outcome=%s rows=%s defect=%s error=%s sql=%s",
                schema, attempt.attempt, attempt.max_attempts, attempt.outcome,
                attempt.row_count, attempt.defect, attempt.error, attempt.sql,
            )

            if attempt.outcome not in RETRYABLE_OUTCOMES:
                return rows

        raise SQLGenerationFailed(attempts)
