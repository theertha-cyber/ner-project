import re
import logging
import time
from dataclasses import dataclass, field
from openai import AsyncOpenAI, AsyncAzureOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.shared.entity_views import (
    CHILD_VALUE_COLUMNS,
    SUBJECT_TABLE_NAME,
    EntityDefinitionSpec,
    QuerySurface,
    resolve_query_surface,
)

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

# Marks a defect as the filename-filter kind, so the retry feedback can explain the right
# thing. Every defect class shares the one `SQLAttempt.defect` field and is told apart by its
# prefix.
_FILENAME_DEFECT_PREFIX = "filename:"
# `wrong_relation:<literal>|<relation or column>` — the value exists in this tenant's data, but
# it is projected into a relation or column the statement did not query. Both the relation and
# the value are real and the query still cannot match, which is the defect class the funded
# retry budget exists for and the one fragmented labelling produces most.
_WRONG_RELATION_DEFECT_PREFIX = "wrong_relation:"
# `scope:<relations that accept a scope>` — a document scope was supplied and the statement
# named nothing it could be applied to. Left unexecuted: `apply_document_scope` returns the
# statement untouched when it recognises no reference, and the graph's secondary row filter only
# drops rows that carry a `document_id` column — an aggregate carries none. Executing it would
# answer a document-scoped question tenant-wide, silently, with a plausible number.
_SCOPE_DEFECT_PREFIX = "scope:"


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

    def __init__(self, attempts: list[SQLAttempt], reason: str | None = None):
        self.attempts = attempts
        self.reason = reason
        if reason is not None:
            # A failure decided before any attempt was made — the coverage probe. Reported
            # as a failure rather than as an empty answer, because the reason the surface
            # returns nothing has nothing to do with the question.
            super().__init__(f"SQL generation failed: {reason}")
            return
        last = attempts[-1] if attempts else None
        detail = f"{last.outcome}: {last.error or last.defect or ''}".strip(": ") if last else "no attempts"
        super().__init__(f"SQL generation failed after {len(attempts)} attempt(s) ({detail})")


@dataclass
class RelationGrounding:
    """One relation, or one `subject` entity column, as the generator is told about it.

    Identifiers alone are not enough to map a natural-language concept onto a relation, and
    the catalog already holds the material that is: `entity_definitions.description` and
    `.examples` are tenant-authored, and `value_kind` / `value_unit` say what a typed column
    actually holds. `samples` are real values drawn from the tenant's own data — the highest
    leverage input to first-attempt success, and the one thing the relational move does not
    change."""

    identifier: str  # `e_skill`, or `subject.email` for a pivoted column
    name: str
    is_column: bool = False
    sql_type: str | None = None
    description: str | None = None
    examples: list | None = None
    value_kind: str | None = None
    value_unit: str | None = None
    samples: list[str] = field(default_factory=list)


@dataclass
class SurfaceGrounding:
    """The tenant's relations and columns with their semantics and value samples.

    Keyed by relation rather than by `entity_type`: a base-model tenant's samples arrive
    labelled `PER`, and a prompt listing `PER` beside a relation named `subject.name` teaches
    the wrong association. Empty when the surface could not be resolved, which renders as no
    grounding block at all rather than as a misleading one."""

    relations: list[RelationGrounding] = field(default_factory=list)


# Strips SQLAlchemy's echo of the executed statement and its bound parameters, which
# `DBAPIError.__str__` appends. Without this the retry prompt — and the log line —
# would carry tenant values back out for no diagnostic benefit.
_DRIVER_ECHO_RE = re.compile(r"\[(?:SQL|parameters):.*", re.DOTALL)

# Only positive equality proves anything about which relation a value lives in. A
# substring match may legitimately span relations, and a negation says nothing at all.
_NORMALIZED_VALUE_EQ_RE = re.compile(
    r"(?:\w+\.)?normalized_value\s*=\s*'([^']*)'", re.IGNORECASE
)


def _sanitize_error(exc: BaseException) -> str:
    """Renders an exception into a single bounded line safe to put in a prompt."""
    message = _DRIVER_ECHO_RE.sub("", str(exc)).split("\n", 1)[0].strip()
    text_out = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
    if len(text_out) > MAX_ERROR_FEEDBACK_CHARS:
        text_out = text_out[: MAX_ERROR_FEEDBACK_CHARS - 1].rstrip() + "…"
    return text_out


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


# --- Table reference resolution -------------------------------------------------
#
# Every table reference in a statement is resolved by one routine, so the whitelist
# check has exactly one feed. The previous implementation scanned for the first
# identifier after each FROM/JOIN and, separately, the first identifier after each
# subquery's FROM. A comma-separated table list has only one FROM, so
# `FROM documents d, public.widget_api_keys k` resolved to `documents` alone and the
# second table was never examined — `public` holds `tenants`, `tenant_users`,
# `widget_api_keys`, `entity_definitions`, and `audit_events`.

_SQL_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<comment>--[^\n]*|/\*.*?\*/)
    | (?P<string>'(?:[^']|'')*')
    | (?P<quoted>"(?:[^"]|"")*")
    | (?P<word>[A-Za-z_][A-Za-z_0-9$]*)
    | (?P<num>\d+(?:\.\d+)?)
    | (?P<punct>.)
    """,
    re.VERBOSE | re.DOTALL,
)

_BARE_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9$]*")

# Words that end a FROM table list. `ON`/`USING` end a join item; the join keywords
# themselves end the preceding item and are picked up again by the main walk.
_TABLE_LIST_TERMINATORS = frozenset({
    "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "FETCH", "WINDOW",
    "UNION", "INTERSECT", "EXCEPT", "RETURNING", "ON", "USING", "JOIN", "INNER",
    "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL", "FOR", "TABLESAMPLE", "WITH",
})

# Prefixes that may precede a table reference without being one.
_TABLE_REF_PREFIXES = frozenset({"LATERAL", "ONLY"})


@dataclass(frozen=True)
class TableReference:
    """One table reference exactly as the statement wrote it. `name` keeps any schema
    qualifier rather than stripping it — a qualifier is grounds for rejection, never
    something to normalise away. `start`/`end` are its span in the original statement,
    so a reference can be rewritten in place without re-rendering the whole query."""

    name: str
    is_callable: bool = False
    start: int = -1
    end: int = -1
    has_alias: bool = False
    # The alias the statement bound the reference to, when it wrote one. Kept because a
    # qualified column reference names the alias, not the table, so column validation cannot
    # attribute `s.filename` to `subject` without it.
    alias: str | None = None


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int


def _tokenize_sql(sql: str) -> list[_Token]:
    """Splits a statement into tokens, dropping whitespace and comments and replacing
    every string literal with a placeholder so a keyword inside a literal cannot be
    read as structure. Each token keeps its span in the original statement."""
    tokens: list[_Token] = []
    for match in _SQL_TOKEN_RE.finditer(sql):
        kind = match.lastgroup
        if kind in ("ws", "comment"):
            continue
        tokens.append(_Token("''" if kind == "string" else match.group(), match.start(), match.end()))
    return tokens


def _skip_parenthesised(tokens: list[_Token], index: int) -> int:
    """`index` points at `(`. Returns the index just past its matching `)`."""
    depth = 0
    while index < len(tokens):
        if tokens[index].text == "(":
            depth += 1
        elif tokens[index].text == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def _is_identifier_token(token: str) -> bool:
    return bool(_BARE_IDENTIFIER_RE.fullmatch(token)) or token.startswith('"')


def _parse_table_list(
    tokens: list[_Token], index: int, single: bool
) -> tuple[int, list[TableReference]]:
    """Reads the table list starting at `index`, which is the token after FROM or
    JOIN. Every comma-separated entry is returned. A parenthesised source (a derived
    table or a parenthesised join) is left for the main walk to descend into, which is
    what makes subqueries resolve through the same routine rather than a second scan."""
    refs: list[TableReference] = []
    count = len(tokens)

    while index < count:
        while index < count and tokens[index].text.upper() in _TABLE_REF_PREFIXES:
            index += 1
        if index >= count:
            break

        token = tokens[index].text
        if token == "(" or token in (",", ")", ";") or token.upper() in _TABLE_LIST_TERMINATORS:
            break
        if not _is_identifier_token(token):
            break

        name_parts = [token]
        name_start, name_end = tokens[index].start, tokens[index].end
        index += 1
        while index + 1 < count and tokens[index].text == "." and _is_identifier_token(tokens[index + 1].text):
            name_parts.append(tokens[index + 1].text)
            name_end = tokens[index + 1].end
            index += 2

        callable_source = index < count and tokens[index].text == "("
        if callable_source:
            index = _skip_parenthesised(tokens, index)

        # An alias, written with or without AS, and any column alias list after it.
        alias: str | None = None
        if index < count and tokens[index].text.upper() == "AS":
            index += 1
            if index < count and _is_identifier_token(tokens[index].text):
                alias = tokens[index].text
                index += 1
        elif (
            index < count
            and _is_identifier_token(tokens[index].text)
            and tokens[index].text.upper() not in _TABLE_LIST_TERMINATORS
        ):
            alias = tokens[index].text
            index += 1
        if index < count and tokens[index].text == "(":
            index = _skip_parenthesised(tokens, index)

        refs.append(TableReference(
            ".".join(name_parts), is_callable=callable_source,
            start=name_start, end=name_end, has_alias=alias is not None, alias=alias,
        ))

        if single or index >= count or tokens[index].text != ",":
            break
        index += 1

    return index, refs


def iter_table_references(sql: str) -> list[TableReference]:
    """Every table reference in `sql`, including each entry of a comma-separated FROM
    list and every reference inside a subquery or derived table.

    A FROM is only a table list when it belongs to a SELECT at the same parenthesis
    depth, which is what keeps `EXTRACT(YEAR FROM value_date)` and
    `SUBSTRING(x FROM 1 FOR 3)` from being read as sources."""
    tokens = _tokenize_sql(sql)
    references: list[TableReference] = []
    select_depths: list[int] = []
    depth = 0
    index = 0

    while index < len(tokens):
        token = tokens[index].text
        upper = token.upper()

        if token == "(":
            depth += 1
            index += 1
            continue
        if token == ")":
            depth -= 1
            while select_depths and select_depths[-1] > depth:
                select_depths.pop()
            index += 1
            continue
        if upper == "SELECT":
            select_depths.append(depth)
            index += 1
            continue
        if upper in ("FROM", "JOIN") and select_depths and select_depths[-1] == depth:
            next_index, refs = _parse_table_list(tokens, index + 1, single=(upper == "JOIN"))
            references.extend(refs)
            index = max(next_index, index + 1)
            continue
        index += 1

    return references


def accepted_relations(surface: QuerySurface | None) -> set[str]:
    """Every relation a statement may name: the static tables plus this tenant's surface.

    `surface` is the querying tenant's generated relational surface, resolved from
    `entity_definitions` by the same `resolve_query_surface` that feeds the execution role's
    grants and the generation prompt. It is per-tenant, so it is passed in rather than read
    from a module constant: one tenant's `e_skill` says nothing about another's."""
    return set(WHITELISTED_TABLES) | set(surface.table_names if surface is not None else set())


def accepted_columns(surface: QuerySurface | None) -> dict[str, set[str]]:
    """`relation -> the columns it declares`, from one source per relation.

    The static tables keep their declared sets; `subject` and each on-surface child table take
    theirs from the resolver, which derives them from the same functions the reconciler and the
    projection use. Nothing here restates a generated column name."""
    columns = {table: set(cols) for table, cols in WHITELISTED_TABLES.items()}
    if surface is not None:
        columns.update(surface.columns_by_relation())
    return columns


def _validate_table_references(sql: str, surface: QuerySurface | None = None) -> None:
    """Rejects any reference that is not a bare identifier naming an accepted relation.
    A schema-qualified name is rejected outright rather than normalised by dropping its
    qualifier — `public.documents` is not `documents`."""
    allowed = accepted_relations(surface)
    for reference in iter_table_references(sql):
        name = reference.name
        if reference.is_callable:
            raise SQLValidationError(
                f"Table reference '{name}' is not in the whitelist: "
                "function-call sources are not allowed"
            )
        if "." in name:
            raise SQLValidationError(
                f"Table reference '{name}' is not in the whitelist: "
                "schema-qualified table names are not allowed"
            )
        if not _BARE_IDENTIFIER_RE.fullmatch(name) or name.lower() not in allowed:
            raise SQLValidationError(f"Table '{name}' is not in the whitelist")


def _qualified_column_references(sql: str) -> list[tuple[str, str]]:
    """Every `<qualifier>.<column>` the statement writes, as `(qualifier, column)`.

    Reads the same token stream as the table walk, so a keyword or a dotted name inside a
    string literal cannot be mistaken for a column reference. A quoted identifier, a
    three-part name, and a `qualifier.name(` function call are skipped: each is a reference
    this routine cannot attribute, and an unattributable reference is accepted, not guessed
    at."""
    tokens = _tokenize_sql(sql)
    references: list[tuple[str, str]] = []

    for index, token in enumerate(tokens):
        if token.text != "." or index == 0 or index + 1 >= len(tokens):
            continue
        qualifier, column = tokens[index - 1].text, tokens[index + 1].text
        if not _is_identifier_token(qualifier) or not _is_identifier_token(column):
            continue
        if qualifier.startswith('"') or column.startswith('"'):
            continue
        if index >= 2 and tokens[index - 2].text == ".":
            continue
        if index + 2 < len(tokens) and tokens[index + 2].text in (".", "("):
            continue
        references.append((qualifier, column))

    return references


def _validate_column_references(sql: str, surface: QuerySurface | None = None) -> None:
    """Rejects a qualified column reference the relation it names does not declare.

    Permissive on ambiguity by design (design.md Decision 6): an unqualified column, a
    qualifier bound to no accepted relation, and a qualifier that resolves to two different
    relations are all accepted. The tokenizer is a reference parser, not a full SQL parser,
    and a gap in it must degrade into a database error — retryable, and already handled —
    rather than into rejecting a correct query. A select alias (`COUNT(*) AS n`) is
    unqualified and so is never examined here."""
    declared = accepted_columns(surface)

    claimed: dict[str, set[str]] = {}
    for reference in iter_table_references(sql):
        if reference.is_callable or "." in reference.name:
            continue
        name = reference.name.lower()
        if name not in declared:
            continue
        claimed.setdefault((reference.alias or name).lower(), set()).add(name)

    # A qualifier bound to more than one relation — the same alias reused in a subquery for a
    # different table — is ambiguous, and ambiguity is accepted rather than resolved.
    bound = {qualifier: next(iter(names)) for qualifier, names in claimed.items() if len(names) == 1}

    for qualifier, column in _qualified_column_references(sql):
        relation = bound.get(qualifier.lower())
        if relation is None:
            continue
        if column.lower() not in declared[relation]:
            raise SQLValidationError(
                f"Column '{qualifier}.{column}' is not declared by '{relation}'"
            )


# The column that ties each static table to a document. A resolved document scope is applied by
# constraining these, so the scope holds whatever shape the generated statement takes —
# including aggregates, which project no document_id to filter on afterwards.
_STATIC_DOCUMENT_SCOPE_COLUMNS = {
    "document_entities": "document_id",
    "document_chunks": "document_id",
    "document_text_spans": "document_id",
    "extraction_runs": "document_id",
    "documents": "id",
}


def document_scope_columns(surface: QuerySurface | None = None) -> dict[str, str]:
    """`relation -> the column a document scope constrains`, static tables plus the surface.

    Mechanical for the generated relations: `subject.document_id` is its primary key and
    `_CHILD_TABLE_COLUMNS` declares `document_id VARCHAR NOT NULL` on every child table, so the
    map is derived from the resolved relation set rather than restated. A relation missing from
    this map is a relation a scope cannot narrow, which is why an unscopeable scoped statement
    is a defect rather than a tenant-wide answer."""
    columns = dict(_STATIC_DOCUMENT_SCOPE_COLUMNS)
    for relation in (surface.table_names if surface is not None else set()):
        columns[relation] = "document_id"
    return columns

DOCUMENT_SCOPE_PARAM = "scope_document_ids"

# The trailing row limit, with any OFFSET that follows it. Anchored at the end because
# `validate_sql` guarantees the statement ends there.
_TRAILING_LIMIT_RE = re.compile(
    r"\bLIMIT\s+(\d+)(\s+OFFSET\s+\d+)?\s*;?\s*$", re.IGNORECASE
)


def _statement_limit(sql: str) -> int | None:
    match = _TRAILING_LIMIT_RE.search(sql)
    return int(match.group(1)) if match else None


def _with_limit(sql: str, limit: int) -> str:
    """The same statement asking for `limit` rows. Used to fetch one row beyond the
    real limit, which is how truncation is detected without a second query."""
    match = _TRAILING_LIMIT_RE.search(sql)
    if not match:
        return sql
    offset = match.group(2) or ""
    return sql[: match.start()] + f"LIMIT {limit}{offset}"


def _without_limit(sql: str) -> str:
    match = _TRAILING_LIMIT_RE.search(sql)
    if not match:
        return sql.rstrip().rstrip(";")
    return sql[: match.start()].rstrip()


def apply_document_scope(
    sql: str,
    scope_columns: dict[str, str] | None = None,
    param_name: str = DOCUMENT_SCOPE_PARAM,
) -> tuple[str, int]:
    """Constrains every scoped table reference in an already-validated statement to a
    bound set of document identifiers. Returns the rewritten statement and how many
    references were rewritten, so the caller can tell a scoped statement from one the
    scope could not touch.

    Each reference is replaced in place by an inline view over the same table:

        FROM document_entities e   ->   FROM (SELECT * FROM document_entities
                                              WHERE document_id = ANY(:ids)) e

    The scope therefore survives aggregation, grouping, and `LIMIT` — unlike the
    previous mechanism, which appended `(restrict results to document_id = '…')` to the
    natural-language question and relied on the generating model to honour it, backed by
    a post-execution row filter that ran *after* `LIMIT 100` and so turned a
    limit-truncated result into an empty one.

    Spans are computed against the original text and applied last-first, so the
    rewritten fragments are never themselves rescanned."""
    columns = _STATIC_DOCUMENT_SCOPE_COLUMNS if scope_columns is None else scope_columns
    references = [
        r for r in iter_table_references(sql)
        if not r.is_callable and r.start >= 0 and r.name.lower() in columns
    ]
    if not references:
        return sql, 0

    for reference in sorted(references, key=lambda r: r.start, reverse=True):
        table = reference.name.lower()
        column = columns[table]
        inline = f"(SELECT * FROM {table} WHERE {column} = ANY(:{param_name}))"
        # A derived table needs a name. When the statement already supplies an alias,
        # adding one here would be a syntax error; when it doesn't, the table's own
        # name keeps every qualified column reference in the statement resolving.
        if not reference.has_alias:
            inline = f"{inline} AS {table}"
        sql = sql[: reference.start] + inline + sql[reference.end:]

    return sql, len(references)


# `SET ROLE` / `SET SESSION AUTHORIZATION` would let a statement choose the identity it
# runs under, which is the one thing the execution role in `execute_sql` must decide.
_ROLE_SWITCH_RE = re.compile(
    r"\bSET\s+(?:LOCAL\s+|SESSION\s+)?ROLE\b|\bSET\s+(?:LOCAL\s+)?SESSION\s+AUTHORIZATION\b",
    re.IGNORECASE,
)


def _fix_document_name_reference(sql: str) -> str:
    """Deterministically repairs a `document_name` reference the LLM forgot to alias.
    A statement over `document_entities` needs a `documents` join to resolve a filename, and
    the model sometimes selects the bare, nonexistent `document_name` column instead — which
    only surfaces as a Postgres UndefinedColumnError at execution time, and the guardrail then
    swallows that into a generic "no sources" reply.

    Kept, and kept gated on `document_entities`, rather than deleted: that table is still
    whitelisted and reachable, so the repair still has a live path. It cannot fire on
    relational SQL, and it has nothing to repair there — `subject.filename` is denormalized
    and resolves on its own (design.md Decision 8)."""
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


def surface_targets(
    surface: QuerySurface | None,
) -> list[tuple[EntityDefinitionSpec, str]]:
    """`(definition, the relation or column its values are projected into)`, in prompt order.

    One walk over the resolved surface, so the grounding block and the wrong-relation probe
    describe the same set. A `multi` definition owns its child table; a `single` definition
    owns a `subject` column and is named `subject.<column>`."""
    if surface is None:
        return []
    targets: list[tuple[EntityDefinitionSpec, str]] = [
        (definition, identifier)
        for identifier, definition in sorted(surface.child_tables.items())
    ]
    targets.extend(
        (column.definition, f"{SUBJECT_TABLE_NAME}.{column.name}")
        for column in surface.subject_columns
    )
    return targets


def relation_by_entity_type(surface: QuerySurface | None) -> dict[str, str]:
    """`stored entity_type literal -> the relation or column that holds its values`.

    Routed through `build_routing_index`, the same index the projection writes by, rather than
    through name equality: on a base-model tenant `entity_type` holds `PER`/`ORG` and only
    `base_label_mapping` connects those to a definition (ADR-008). Name equality would make
    every base-model tenant resolve to nothing."""
    from src.extraction_service.services.relational_projection import build_routing_index

    targets = surface_targets(surface)
    if not targets:
        return {}
    identifiers = {definition.sql_identifier: target for definition, target in targets}
    return {
        literal: identifiers[definition.sql_identifier]
        for literal, definition in build_routing_index(
            [definition for definition, _target in targets]
        ).items()
        if definition.sql_identifier in identifiers
    }


def _render_attempt_feedback(
    attempts: list[SQLAttempt], surface: QuerySurface | None = None
) -> str:
    """Renders prior attempts into the corrective block appended to a retry prompt.
    At temperature 0 a retry without the previous SQL in front of it regenerates the
    same query and burns the budget, so the SQL is always included.

    Every branch speaks in relations and columns. None mentions `entity_type`: the model is
    never told to query the EAV store, so feedback pointing it there would teach a query model
    the prompt does not describe and the validator would reject."""
    if not attempts:
        return ""

    blocks = []
    for a in attempts:
        lines = [f"Attempt {a.attempt} SQL:", (a.sql or "(no SQL was produced)")[:MAX_SQL_LENGTH]]
        if a.outcome == SQLAttemptOutcome.EMPTY_WITH_DEFECT:
            defect = a.defect or ""
            if defect.startswith(_SCOPE_DEFECT_PREFIX):
                relations = defect[len(_SCOPE_DEFECT_PREFIX):]
                lines.append(
                    "This query was not executed. The question is restricted to specific "
                    "documents, and this query references no relation that restriction can be "
                    "applied to, so running it would have answered a different, tenant-wide "
                    f"question. Query one of these relations instead: {relations}."
                )
                blocks.append("\n".join(lines))
                continue

            lines.append(f"Execution result: {a.row_count or 0} rows returned.")
            if defect.startswith(_FILENAME_DEFECT_PREFIX):
                literal = defect[len(_FILENAME_DEFECT_PREFIX):]
                lines.append(
                    f"This query required a filename to match '{literal}', but no document in "
                    "this tenant has that in its filename, so it could not have matched "
                    "anything. Filenames are not the subject's name — if you meant to "
                    "constrain to a named subject, match the relation or column that holds "
                    "names instead, and select `filename` rather than filtering on it."
                )
            elif defect.startswith(_WRONG_RELATION_DEFECT_PREFIX):
                payload = defect[len(_WRONG_RELATION_DEFECT_PREFIX):]
                literal, _, holder = payload.partition("|")
                lines.append(
                    f"The value '{literal}' does exist in this tenant's data, but it is held "
                    f"by `{holder}`, not by the relation this query filtered on — so the "
                    f"combination could not have matched anything. Re-issue the query against "
                    f"`{holder}`."
                )
            else:
                lines.append(
                    "This query could not have matched anything as written; reconsider which "
                    "relation holds the value it filtered on."
                )
        elif a.outcome == SQLAttemptOutcome.VALIDATION_ERROR:
            lines.append(f"Rejected by the SQL validation layer: {a.error}")
            if surface is not None:
                lines.append(
                    "The relations you may query are: "
                    f"{', '.join(sorted(surface.table_names))}. "
                    + "; ".join(
                        f"`{relation}` declares ({', '.join(sorted(columns))})"
                        for relation, columns in sorted(surface.columns_by_relation().items())
                    )
                    + "."
                )
        elif a.outcome == SQLAttemptOutcome.EXECUTION_ERROR:
            lines.append(f"Database error: {a.error}")
        else:
            lines.append(f"Could not produce a usable query: {a.error}")
        blocks.append("\n".join(lines))

    return (
        "\n\n## Previous attempts (all failed — do not repeat them)\n\n"
        + "\n\n".join(blocks)
        + "\n\nThe previous attempt did not produce a useful result. Reconsider the relations, "
        "columns, values, operators, joins, filters, and other assumptions, and generate a "
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

    def _render_surface(self, grounding: SurfaceGrounding | None) -> str:
        """Renders the tenant's relations and columns, each with what it means and a bounded
        sample of the values that actually occur in it.

        Identifiers, semantics, and samples in one block because the model's hardest job on
        this data is deciding which relation a question is about and how its values are
        spelled — and every part of that answer is here rather than guessed at. A relation with
        no samples is still listed: absence of a sample is not absence of the relation."""
        if not grounding or not grounding.relations:
            return ""

        lines = [
            "",
            "## This tenant's entity surface",
            "",
            "These are the relations and columns holding this tenant's extracted facts. Each is "
            "listed with what it means and, where available, real values drawn from this "
            "tenant's own data. Questions rarely name a relation verbatim, so map the wording "
            "onto whichever relation or column fits best — one that is not listed here does not "
            "exist. The samples are partial: a value's absence from them does not mean it is "
            "absent from the data, but they do show how values in that relation are written.",
            "",
        ]
        for relation in grounding.relations:
            header = f"- `{relation.identifier}`"
            if relation.is_column:
                header += f" ({relation.sql_type}, one value per subject)"
            else:
                header += " (many rows per subject; values in `value` / `normalized_value`)"
            header += f" — {relation.name}"
            if relation.description:
                header += f": {relation.description}"
            lines.append(header)
            if relation.value_kind:
                unit = f" in {relation.value_unit}" if relation.value_unit else ""
                lines.append(f"  - holds a parsed {relation.value_kind} value{unit}")
            if relation.examples:
                rendered = ", ".join(str(e) for e in relation.examples[:5])
                lines.append(f"  - examples given by the tenant: {rendered}")
            for value in relation.samples:
                lines.append(f"  - value in the data: {value}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _render_relation_list(surface: QuerySurface | None) -> str:
        """The relations a statement may name, as a bare list, for the hard-constraints block."""
        if surface is None:
            return SUBJECT_TABLE_NAME
        return ", ".join(sorted(surface.table_names)) or SUBJECT_TABLE_NAME

    async def generate_sql(
        self,
        natural_language_query: str,
        conversation_context: str | None = None,
        grounding: SurfaceGrounding | None = None,
        surface: QuerySurface | None = None,
        previous_attempts: list[SQLAttempt] | None = None,
    ) -> str:
        # The static tables, minus the EAV entity store. `document_entities` stays whitelisted
        # and granted — the grounding and defect probes read it — but it is not shown here:
        # the query model is the relational surface, and a table listed in the prompt is a
        # table the model will eventually query.
        tables_desc = "\n".join(
            f"- {tbl} ({', '.join(sorted(cols))})"
            for tbl, cols in WHITELISTED_TABLES.items()
            if tbl != "document_entities"
        )
        subject_columns_desc = "\n".join(
            f"- subject.{column.name} ({column.sql_type}) — {column.definition.name}"
            for column in (surface.subject_columns if surface else [])
        ) or "- (this tenant has no single-valued fact columns beyond the identity columns)"
        child_tables_desc = "\n".join(
            f"- {identifier} ({', '.join(CHILD_VALUE_COLUMNS)}) — {definition.name}"
            for identifier, definition in sorted((surface.child_tables if surface else {}).items())
        ) or "- (this tenant has no multi-valued entity tables)"
        context = f"\nConversation context:\n{conversation_context}" if conversation_context else ""
        surface_desc = self._render_surface(grounding)
        relation_list = self._render_relation_list(surface)
        feedback = _render_attempt_feedback(previous_attempts or [], surface)

        prompt = f"""You are a SQL query generator for a multi-tenant NER platform.
Generate a SELECT SQL query answering the natural language question below.

## The data model

Documents are uploaded files; entities are the structured facts extracted from them. Those facts
are stored relationally, one relation per kind of fact, and `document_id` ties them together.

**`subject` is one row per extracted document — one subject.** A subject is whoever or whatever
the document is about: a candidate, a contract, an invoice. Its key is `document_id`, its
`filename` column carries the file's name, and every single-valued fact about that subject is a
typed column on the same row:

{subject_columns_desc}

**Each `e_…` table holds the many-valued facts**, with as many rows per document as the subject
has values, joined back to `subject` on `document_id`. Every one of them carries the same
columns: `value` is the text as it appeared, `normalized_value` is lowercased and canonicalised
for matching (so 'aws' matches both "AWS" and "Amazon Web Services"), `value_number` /
`value_date` hold the parsed value where one could be parsed, and `confidence` and `page_number`
describe the extraction:

{child_tables_desc}

So a question about a single-valued fact is answered from a `subject` column, and a question
about a many-valued one is answered from that fact's own table — joined to `subject` when the
answer needs the filename or a single-valued fact as well. Reason about *subjects*, not about
isolated rows: a set of rows each matching one condition is not the same as one subject
satisfying all of them.

**Your result set is the entire evidence for the final answer.** These rows are handed to another
model that must answer the user's question using nothing else — it cannot see your SQL. A
condition written in `WHERE` filters the rows and is then thrown away, so a result of bare
identifiers proves nothing: asked "who knows Python", that model receives a list of documents
with no mention of Python anywhere and can only reply that it doesn't know. So **select the facts
that justify each row**, not merely the identity of what matched.

With that in mind, what the question returns decides the query's shape:

- **Facts** ("her email", "every company named", "which languages does X know") — select the
  columns or the child-table rows holding them, joined to `subject` for identification.
- **Subjects filtered by what they have** ("who knows Python", "who knows both X and Y") — join
  the matching child rows and project their values, so each row carries the evidence for its own
  inclusion. Use `EXISTS` for any *additional* condition you only need to test rather than show.
- **Subjects filtered by what they lack** ("who doesn't know Java") — the justification is an
  absence and cannot be shown, so `NOT EXISTS` over that fact's table is right; select the
  subject's identity columns.
- **Counts and rankings** ("how many know Python", "who lists the most languages", "most common
  language") — aggregate over the rows directly. `EXISTS` only reports whether something is
  there, so nothing countable survives it and a ranking built on it has nothing real to sort by.

## Reasoning guidelines

Translate the meaning of the question, not its surface words. A few things follow from the model
above:

- **Every condition in the question is a real constraint.** They compose with AND; dropping one,
  or substituting one for another, silently answers a different question than the one asked.
- **English quantifiers are set operations over subjects.** "Both X and Y" means one subject
  satisfies each condition (typically an `EXISTS` per condition); "X or Y" means either suffices;
  "not X" / "without X" means the subject has no such row at all (`NOT EXISTS`) — never a
  positive filter on the negated value, which returns precisely the opposite set.
- **Distinguish what identifies the subject from what you are reading off it.** A child row holds
  one fact and only its own value: the row carrying an email address contains the email, never
  the subject's name. So a person's name can never be a filter on the child row you are
  selecting — it belongs to `subject`, and it constrains the child rows only through the shared
  `document_id`. Words for a category of subject ("candidates", "engineers", "people") are not
  values at all — they say who is being asked about, and belong in no filter. Only concrete
  values named in the question are matched directly.
- **`subject.filename` is never the subject's name.** Filenames are whatever the uploader
  happened to call the file — "Resume 4.pdf", "CV_final_v2.pdf", a bare hash — and a person named
  in the question is almost never in one. `filename ILIKE '%<their name>%'` therefore returns
  nothing while looking perfectly reasonable. To constrain to a named subject, match the relation
  or column that holds names, listed above. `filename` is for identifying a result to the reader:
  select it, never filter on it.
- **When aggregating, group by exactly the thing being ranked and nothing else.** Grouping by
  `document_id` ranks subjects; grouping by `normalized_value` ranks the values themselves —
  similar wording, opposite questions. Every extra column in the GROUP BY changes what one row
  means, so a superlative about people ("who lists the most languages") splits into one row per
  person *per language* if the value is grouped too, and no longer answers the question. A
  singular superlative wants a single row.
- **Match values at the right precision.** Short canonical values (skills, languages, tools,
  emails) compare cleanly with `=` against a lowercased literal on `normalized_value`. Narrative
  values (degrees, addresses, job titles) are almost never stored as the bare term — a degree is
  extracted as "B.Tech in Computer Science and Engineering", an address as a whole postal line —
  so `=` finds nothing and a substring match (`ILIKE '%…%'`) is what actually retrieves them.
- **Prefer the typed columns for anything quantitative.** `value_number` / `value_date`, and the
  typed `subject` columns above, hold parsed numeric and date values (with `CURRENT_DATE`
  available for "today"); comparing or ordering the raw text instead gives wrong results. They
  are NULL wherever a value could not be parsed, so a subject with several such rows is best
  summarised with an aggregate (`MAX(value_number)`) rather than read from an arbitrary row.

Prefer the simplest query that faithfully expresses the question. Whenever the result is a list of
facts or subjects, every row needs two separate things, and a row is useless without either:

1. **The matched fact itself** — the `value` of the row, or the `subject` column, that satisfied
   the question, projected as a named column. This is the evidence, and it is the whole reason
   the row is in the result. A result identifying four people with no trace of what they matched
   on cannot answer "who knows Python".
2. **Who the row is about** — alongside the evidence, never instead of it: `document_id`, and
   `subject.filename` where the reader needs to see which file it came from. Where the tenant has
   a relation or column holding subjects' names, select it too — an answer should be able to say
   "Reshma U", not "Resume-1a2b.pdf", and it can only do so if you retrieved the name.

**Every result row MUST project `document_id`.** It is what ties a row back to its source
document, and a row without it cannot be cited or scoped.

(An aggregate grouped by `document_id` satisfies both: the grouping key and the aggregate are the
whole answer, and extra columns would only distort the grouping.)

## Hard constraints

Only use the relations and columns listed in this prompt. The entity relations you may query are:
{relation_list}.
Always include a LIMIT clause. Unless the question itself asks for a specific number of results
("the top 3", "who has the most"), leave room for every answer — use `LIMIT {DEFAULT_LIMIT}` rather
than a small number that would silently truncate the result.
Never use DDL, INSERT, UPDATE, DELETE, DROP, ALTER, or GRANT.
Never use UNION, or JOINs on relations that are not listed here.
{surface_desc}
Other tables available (document metadata, not entity facts):
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

    def validate_sql(self, sql: str, surface: QuerySurface | None = None) -> str:
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

        if _ROLE_SWITCH_RE.search(sql):
            raise SQLValidationError("Disallowed SQL keyword: SET ROLE")

        # One routine resolves every reference — top-level, comma-joined, JOINed, and
        # inside subqueries — so there is no second scan to fall out of step with it.
        _validate_table_references(sql, surface)
        # Columns second, so a reference to an unknown relation is reported as the table
        # problem it is rather than as a column the (rejected) table fails to declare.
        _validate_column_references(sql, surface)

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

        return sql

    @staticmethod
    def _execution_role() -> str | None:
        """The role generated SQL runs under, or None to keep the connection role.

        Read from server configuration only. Nothing in the question, the conversation,
        the generated statement, or a tool argument reaches this — the same rule
        `schema` follows."""
        if not settings.sql_execution_role_enabled:
            return None
        role = settings.sql_execution_role_name
        if not _BARE_IDENTIFIER_RE.fullmatch(role or ""):
            raise SQLValidationError("Configured SQL execution role is not a bare identifier")
        return role

    async def execute_sql(
        self, sql: str, session: AsyncSession, schema: str, params: dict | None = None,
        completeness_sink: dict | None = None,
    ) -> list[dict]:
        """Executes an already-validated statement and returns its rows.

        When `completeness_sink` is given it is filled with `returned`, `matched`, and
        `truncated`. Truncation is detected by asking for one row beyond the limit —
        cheap, and it costs nothing on the overwhelming majority of queries that are
        not truncated. The exact matched total is computed only when the extra row came
        back, inside the same read-only transaction and its timeout, and reported as
        unknown (`None`) if that count fails. The rows handed to the caller and the row
        limit itself are unchanged by any of this."""
        import asyncio
        role = self._execution_role()
        limit = _statement_limit(sql)
        probe_sql = _with_limit(sql, limit + 1) if (completeness_sink is not None and limit) else sql

        try:
            async with asyncio.timeout(10):
                result = await session.execute(
                    text(f"SET search_path TO {schema}")
                )
                await session.execute(text("BEGIN READ ONLY"))
                # SET LOCAL scopes the role to this transaction, so the privilege
                # boundary and the read-only boundary end together and neither can
                # leak back onto the pooled connection.
                if role is not None:
                    await session.execute(text(f"SET LOCAL ROLE {role}"))
                result = await session.execute(text(probe_sql), params or {})
                raw_rows = result.fetchall()
                columns = result.keys()

                truncated = bool(limit) and len(raw_rows) > limit
                if truncated:
                    raw_rows = raw_rows[:limit]

                matched: int | None = len(raw_rows)
                if truncated:
                    matched = await self._count_matching_rows(session, sql, params)

                await session.execute(text("COMMIT"))

                rows = [dict(zip(columns, row)) for row in raw_rows]
                if completeness_sink is not None:
                    completeness_sink.update({
                        "returned": len(rows),
                        "matched": matched,
                        "truncated": truncated,
                    })
                return rows
        except asyncio.TimeoutError:
            await session.execute(text("ROLLBACK"))
            logger.warning("SQL query timed out after 10s")
            raise SQLValidationError("Query execution timed out")

    @staticmethod
    async def _count_matching_rows(
        session: AsyncSession, sql: str, params: dict | None,
    ) -> int | None:
        """The total the statement would have matched without its row limit, or None if
        the count could not be taken. Only ever called on a statement already known to
        be truncated, so this is not a per-query cost."""
        try:
            result = await session.execute(
                text(f"SELECT COUNT(*) FROM ({_without_limit(sql)}) AS _completeness"),
                params or {},
            )
            row = result.first()
            return int(row[0]) if row is not None else None
        except Exception as e:
            logger.warning("Matched-row count failed, reporting unknown: %s", _sanitize_error(e))
            return None

    async def _fetch_entity_value_samples(self, session: AsyncSession, schema: str) -> dict[str, list[str]]:
        """Bounded, representative values per stored `entity_type`, still read from the EAV
        store. Ranked by frequency so the *dominant* spelling surfaces — which is the one worth
        matching against on a dataset with fragmented vocabulary. The ROW_NUMBER() window is
        applied over the grouped counts, so the outer LIMIT can never distort the ranking.

        One query rather than a `SELECT DISTINCT` per generated relation: N queries instead of
        one, and a per-relation read reports nothing for a tenant whose surface is unpopulated,
        which is precisely the case the coverage probe has to be able to distinguish. The
        results are re-keyed onto relations by `_fetch_surface_grounding`; the caps are applied
        there, per relation, because several stored labels can route to one relation."""
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

    # One query, two facts: does the relational surface hold rows for this question's extent,
    # and does the EAV store. Asked together so the two answers describe the same instant and
    # the same scope, and so the probe costs one round trip per question.
    _COVERAGE_PROBE_SQL = (
        "SELECT {projected} AS projected, "
        "EXISTS (SELECT 1 FROM document_entities{scope}) AS extracted"
    )

    # Whether the tenant's schema physically holds `subject` yet. A tenant whose documents all
    # predate the projection has no generated tables at all, not empty ones — the reconciler
    # runs at extraction-run start, so a tenant that has not extracted since is untouched. The
    # existence check is what lets that case reach the coverage message instead of dying as an
    # `UndefinedTable` inside the probe and being written off as "we don't know".
    _SUBJECT_EXISTS_SQL = (
        "SELECT 1 FROM pg_tables WHERE schemaname = :schema AND tablename = :relation"
    )

    async def _coverage_reason(
        self,
        session: AsyncSession,
        schema: str,
        surface: QuerySurface,
        document_ids: list[str] | None,
    ) -> str | None:
        """Why the relational surface cannot answer at all, or None when it can.

        The projection is written only by the extraction worker, so relational data exists only
        for documents extracted since it shipped. A relational query over an empty `subject`
        returns zero rows, and the zero-rows policy — correctly, for its own assumptions —
        calls that a legitimate empty answer. Under a relational-only query model that becomes
        a confident wrong answer for an entire class of tenants, so it is turned into a visible
        "source unavailable" instead.

        Scoped to the question's extent, not to the tenant: a scoped question about a document
        that predates the projection is the same failure at document granularity.

        An absent `subject` counts as an unpopulated one: it is the same condition seen earlier,
        and it has the same remedy. A tenant that has not run extraction since the projection
        shipped has no generated tables at all, because the reconciler runs at run start.

        Best-effort in the same sense as the other probes: an unresolved surface or a failed
        probe returns None. Not knowing is not evidence, and a probe must never turn a working
        question into a failure."""
        if SUBJECT_TABLE_NAME not in surface.table_names:
            return None

        scope, params = "", {}
        if document_ids:
            scope = f" WHERE document_id = ANY(:{DOCUMENT_SCOPE_PARAM})"
            params = {DOCUMENT_SCOPE_PARAM: list(document_ids)}

        try:
            await session.execute(text(f"SET search_path TO {schema}"))
            exists = await session.execute(
                text(self._SUBJECT_EXISTS_SQL),
                {"schema": schema, "relation": SUBJECT_TABLE_NAME},
            )
            projected = (
                f"EXISTS (SELECT 1 FROM {SUBJECT_TABLE_NAME}{scope})"
                if exists.first() is not None
                else "false"
            )
            result = await session.execute(
                text(self._COVERAGE_PROBE_SQL.format(projected=projected, scope=scope)),
                params,
            )
            row = result.first()
        except Exception as e:
            logger.warning("Coverage probe failed schema=%s: %s", schema, _sanitize_error(e))
            return None

        if row is None or bool(row[0]) or not bool(row[1]):
            return None

        extent = "the requested document(s)" if document_ids else "this tenant"
        return (
            f"the relational entity surface holds no rows for {extent} while extracted "
            "entities exist, so structured retrieval cannot answer from it; re-extract under "
            "a promoted model version to populate it"
        )

    async def _fetch_query_surface(self, session: AsyncSession, schema: str) -> QuerySurface:
        """The querying tenant's relational surface, from the shared resolver.

        Resolved from `schema` rather than from a `tenant_id` threaded through the tool
        boundary (design.md Decision 2): `schema` is the value ADR-001 makes authoritative, and
        it is already bound once from authenticated request context.

        Best-effort: a failure here must not turn a working question into a 500. The
        consequence of an empty surface is only that a generated statement naming a generated
        relation is rejected — the same outcome as before those tables existed."""
        try:
            resolved = await resolve_query_surface(session, [schema])
        except Exception as e:
            logger.warning("query surface resolution failed schema=%s: %s", schema, _sanitize_error(e))
            return QuerySurface(table_names=set())
        return resolved.get(schema) or QuerySurface(table_names=set())

    async def _fetch_surface_grounding(
        self, session: AsyncSession, schema: str, surface: QuerySurface
    ) -> SurfaceGrounding:
        """The tenant's relations and columns, their semantics, and their real values.

        Fetched once per invocation and reused by every attempt, so a retry differs from its
        predecessor only by the feedback block.

        The samples come from `document_entities` keyed by `entity_type` and are re-keyed onto
        the relation or column that entity type projects into, through the same routing index
        the projection itself uses. That indirection is the ADR-008 requirement in practice: a
        base-model tenant's values arrive labelled `PER`, and only `base_label_mapping` says
        which relation holds them. An entity type no active definition claims contributes no
        samples — it projects nowhere, so there is no relation to list it under."""
        relations: list[RelationGrounding] = []
        by_identifier: dict[str, RelationGrounding] = {}
        for definition, target in surface_targets(surface):
            is_column = "." in target
            relation = RelationGrounding(
                identifier=target,
                name=definition.name,
                is_column=is_column,
                sql_type=next(
                    (
                        column.sql_type
                        for column in surface.subject_columns
                        if f"{SUBJECT_TABLE_NAME}.{column.name}" == target
                    ),
                    None,
                ),
                description=definition.description,
                examples=definition.examples,
                value_kind=definition.value_kind,
                value_unit=definition.value_unit,
            )
            relations.append(relation)
            by_identifier[target] = relation

        if not relations:
            return SurfaceGrounding()

        holders = relation_by_entity_type(surface)

        samples = await self._fetch_entity_value_samples(session, schema)
        candidates: dict[str, list[str]] = {}
        for entity_type, values in sorted(samples.items()):
            target = holders.get((entity_type or "").strip().upper())
            if target is None:
                # An entity type no active definition claims projects nowhere, so there is no
                # relation to list its values under. The EAV store tolerates undefined types
                # deliberately; the query surface does not describe them.
                continue
            # Several stored labels can route to one relation — a base-model tenant's `PER`
            # and its own `PERSON` both do — so the caps are applied after the merge, not by
            # the query, and in prompt order so the budget is spent deterministically.
            candidates.setdefault(target, []).extend(values)

        total = 0
        for relation in relations:
            for value in candidates.get(relation.identifier, []):
                if total >= self.sample_max_values:
                    break
                if len(relation.samples) >= self.sample_values_per_type:
                    break
                relation.samples.append(value)
                total += 1

        return SurfaceGrounding(relations=relations)

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

    async def _wrong_relation_defect(
        self, sql: str, session: AsyncSession, schema: str, surface: QuerySurface | None,
    ) -> str | None:
        """Returns `wrong_relation:<literal>|<relation or column>` when a value the statement
        matched against `normalized_value` exists in this tenant's data, but is projected into
        a relation or column the statement did not query. Otherwise None.

        Both the value and the relation are real and the query still cannot match, because the
        extractor filed that value elsewhere — the most common way a well-formed query comes
        back empty on this data, and the class the funded retry budget exists for.

        `document_entities` is the oracle rather than the relations themselves: it is indexed,
        it answers "where does this value actually live" in one query instead of one per
        relation, and it can see values in relations that are off-surface or unpopulated. It is
        read here, never described to the generator.

        Never fires on an unresolved surface or a failed probe — "we don't know" is not
        evidence of a defect, exactly as it is not evidence of absence."""
        holders = relation_by_entity_type(surface)
        if not holders:
            return None

        values = [v for v in _NORMALIZED_VALUE_EQ_RE.findall(sql) if v]
        if not values:
            return None

        queried = {
            reference.name.lower()
            for reference in iter_table_references(sql)
            if not reference.is_callable
        }

        try:
            await session.execute(text(f"SET search_path TO {schema}"))
            for value in values:
                result = await session.execute(
                    text(
                        "SELECT DISTINCT entity_type FROM document_entities "
                        "WHERE normalized_value = :value"
                    ),
                    {"value": value},
                )
                targets = [
                    holders[row[0].strip().upper()]
                    for row in result.fetchall()
                    if row[0] and row[0].strip().upper() in holders
                ]
                if not targets:
                    # The value occurs nowhere, or only under an entity type that projects
                    # nowhere. Genuinely absent is a real answer and must not consume a retry.
                    continue
                if any(self._statement_reads(sql, target, queried) for target in targets):
                    continue
                return f"{_WRONG_RELATION_DEFECT_PREFIX}{value}|{targets[0]}"
        except Exception as e:
            logger.warning("Wrong-relation defect check failed: %s", _sanitize_error(e))
            return None
        return None

    @staticmethod
    def _statement_reads(sql: str, target: str, queried: set[str]) -> bool:
        """Whether the statement actually read the relation or column `target` names.

        A `subject` column needs both halves: a statement that joins `subject` for the filename
        has not read `subject.email`, and reporting no defect on that basis would hide the
        very mismatch this probe exists to find."""
        relation, _, column = target.partition(".")
        if relation.lower() not in queried:
            return False
        if not column:
            return True
        return bool(re.search(rf"\b{re.escape(column)}\b", sql, re.IGNORECASE))

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
        grounding: SurfaceGrounding,
        previous_attempts: list[SQLAttempt],
        document_ids: list[str] | None = None,
        completeness_sink: dict | None = None,
        surface: QuerySurface | None = None,
    ) -> tuple[SQLAttempt, list[dict] | None]:
        """One generate -> validate -> execute -> classify pass. `schema` is passed in
        already bound from authenticated request context and is only ever forwarded;
        nothing here derives it from generated SQL or from the question. `document_ids`
        is likewise caller-supplied: it comes from entity resolution, never from the
        generated statement."""
        def record(outcome: str, **kw) -> SQLAttempt:
            return SQLAttempt(
                attempt=attempt_number, max_attempts=self.max_attempts, outcome=outcome, **kw
            )

        try:
            sql = await self.generate_sql(
                natural_language_query, conversation_context, grounding, surface, previous_attempts,
            )
        except Exception as e:
            return record(SQLAttemptOutcome.GENERATION_ERROR, error=_sanitize_error(e)), None

        if not sql or not sql.strip():
            return record(
                SQLAttemptOutcome.GENERATION_ERROR,
                sql=sql,
                error="the generator returned no usable query text",
            ), None

        try:
            validated_sql = self.validate_sql(sql, surface)
        except SQLValidationError as e:
            return record(SQLAttemptOutcome.VALIDATION_ERROR, sql=sql, error=_sanitize_error(e)), None

        # The scope is applied after validation, so the whitelist decided on the
        # statement the model wrote, and the rewrite can only ever narrow it.
        scoped_sql, params = validated_sql, {}
        if document_ids:
            scoped_sql, rewritten = apply_document_scope(
                validated_sql, document_scope_columns(surface)
            )
            if not rewritten:
                # Classified before execution: the statement is not wrong, it is out of scope,
                # and running it would answer a different question than the one asked.
                scopeable = ", ".join(sorted(document_scope_columns(surface)))
                return record(
                    SQLAttemptOutcome.EMPTY_WITH_DEFECT,
                    sql=validated_sql,
                    row_count=0,
                    defect=f"{_SCOPE_DEFECT_PREFIX}{scopeable}",
                ), None
            params = {DOCUMENT_SCOPE_PARAM: list(document_ids)}

        try:
            rows = await self.execute_sql(scoped_sql, session, schema, params, completeness_sink)
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

        defect = await self._filename_defect(validated_sql, session, schema)
        if defect is None:
            defect = await self._wrong_relation_defect(validated_sql, session, schema, surface)
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
        document_ids: list[str] | None = None,
        completeness_sink: dict | None = None,
    ) -> list[dict] | None:
        """Bounded generate/validate/execute recovery loop. Returns rows on the first
        successful attempt — including an empty list for a legitimate zero-row result —
        and raises `SQLGenerationFailed` when every attempt failed. Every attempt goes
        through the same `validate_sql` and `execute_sql` as the first.

        `schema` is bound here, once, from the caller's authenticated request context
        and is never reassigned inside the loop, so no attempt can change which tenant
        is queried. `document_ids`, when given, is applied to every attempt as a bound
        predicate on the validated statement."""
        # Resolved once per question, from the same resolver that grants the execution role its
        # SELECTs, so the described set, the validated set, and the granted set cannot drift.
        surface = await self._fetch_query_surface(session, schema)
        # Asked before any attempt: a surface with no rows for this question's extent answers
        # every statement with zero rows, and reporting that as "nothing found" would be a
        # confident wrong answer rather than an empty one.
        coverage = await self._coverage_reason(session, schema, surface, document_ids)
        if coverage is not None:
            logger.warning("sql_coverage schema=%s outcome=unavailable reason=%s", schema, coverage)
            raise SQLGenerationFailed([], reason=coverage)
        grounding = await self._fetch_surface_grounding(session, schema, surface)
        attempts: list[SQLAttempt] = []

        for attempt_number in range(1, self.max_attempts + 1):
            if attempt_number > 1 and deadline is not None and time.monotonic() >= deadline:
                logger.warning(
                    "sql_attempt schema=%s attempt=%d/%d outcome=abandoned reason=deadline_exhausted",
                    schema, attempt_number, self.max_attempts,
                )
                break

            # A fresh sink per attempt: a later attempt's completeness must never be
            # reported alongside an earlier attempt's rows.
            attempt_completeness: dict = {}
            attempt, rows = await self._run_attempt(
                attempt_number, natural_language_query, session, schema,
                conversation_context, grounding, attempts, document_ids, attempt_completeness,
                surface,
            )
            if completeness_sink is not None and attempt.outcome == SQLAttemptOutcome.SUCCESS:
                completeness_sink.clear()
                completeness_sink.update(attempt_completeness)
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
