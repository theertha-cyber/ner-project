"""Contract-validated SQL over uploaded tabular files (tabular-file-chat spec).

Reuses ADR-016 unchanged: the fixed rules prompt (`EXTERNAL_SQL_SYSTEM_PROMPT`,
built from the validator's own allow-list), `%(pN)s` placeholders, local
`validate_statement` before execution, and retries that feed back only the
finite reason class and the offending contract identifier. The validation
contract is the tenant's served files' relations with their included columns
and no joins, so a statement over two files is `unapproved_join` (ADR-018).
Only an accepted statement reaches the locked executor, and it runs once.

The LLM client here is never wrapped by a prompt/output-capturing tracer:
schema context, approved value hints and generated SQL would otherwise reach
LangSmith, which ADR-013 forbids.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.chat_api.services import tabular_executor
from src.chat_api.services.external_sql_generator import (
    EXTERNAL_SQL_SYSTEM_PROMPT,
    _missing_param_name,
    _parse_llm_output,
    _render_feedback,
)
from src.chat_api.services.tabular_cache import ParquetCache
from src.shared.config import settings
from src.shared.database import get_engine
from src.shared.external_postgres import validator as _validator
from src.shared.external_postgres.validator import (
    REASON_UNAPPROVED_COLUMN,
    ValidationRejected,
    validate_statement,
)
from src.shared.retrieval.tools.tabular_tools import entry_text_for_file
from src.shared.tabular_files.capability import (
    relation_index,
    resolve_tabular_capability,
    validation_contract,
)

logger = logging.getLogger(__name__)

REASON_NOT_EXECUTABLE = "not_executable"
REASON_GENERATION_EXHAUSTED = "generation_exhausted"

# Fixed, non-sensitive text per finite outcome (tabular-file-chat spec). Never SQL
# text, parameter values, row values or stack traces.
TABULAR_OUTCOME_MESSAGES: dict[str, str] = {
    REASON_NOT_EXECUTABLE: "There are no published uploaded files to answer this from.",
    REASON_GENERATION_EXHAUSTED: (
        "This question could not be turned into a supported query over the uploaded "
        "files. Try rephrasing it, or ask about one file at a time."
    ),
    tabular_executor.REASON_TIMEOUT: (
        "The query over the uploaded file took too long and was stopped. Try a narrower question."
    ),
    tabular_executor.REASON_FAILED: (
        "The query over the uploaded file could not be completed. Try again, or rephrase the question."
    ),
    tabular_executor.REASON_RESOURCE: (
        "The query over the uploaded file needed more memory than is allowed. Try a narrower question."
    ),
}

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PLACEHOLDER_SPAN_RE = re.compile(r"%\([^)]*\)s")


@dataclass
class TabularAnswer:
    rows: list[dict] = field(default_factory=list)
    truncated: bool = False
    relations: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    # Citation material: display name, served version, sheet and relation of each
    # file the statement read. Never row or parameter values.
    files: list[dict] = field(default_factory=list)
    reason: str | None = None


def _columns_used(sql: str, relations: list[str], contract: dict) -> list[str]:
    """Contract columns of the accepted relations that the statement names.
    Every value is a placeholder, so a bare word in the text is never data."""
    words = {w.lower() for w in _WORD_RE.findall(_PLACEHOLDER_SPAN_RE.sub(" ", sql))}
    used: list[str] = []
    for relation in relations:
        for column in contract["relations"][relation]["columns"]:
            if column.lower() in words and column not in used:
                used.append(column)
    return sorted(used)


def _walk(token):
    yield token
    for child in getattr(token, "tokens", None) or []:
        yield from _walk(child)


def check_columns_strict(sql: str, contract: dict, relations: list[str]) -> None:
    """A second column wall on top of the unchanged validator.

    `validate_statement` accepts a bare name it cannot resolve (it prefers a
    database error to a false rejection). For uploaded files that is not good
    enough: an excluded column must be refused before execution, not discovered
    missing by DuckDB. Every bare name in the statement must be a function the
    validator allows, an accepted relation, an alias the statement defines, or
    an included column of an accepted relation; anything else is
    `unapproved_column` naming it."""
    import sqlparse
    from sqlparse import tokens as T
    from sqlparse.sql import Identifier

    statement = sqlparse.parse(sql)[0]
    allowed = {r.lower() for r in relations}
    for relation in relations:
        allowed.update(c.lower() for c in contract["relations"][relation]["columns"])
    allowed.update(
        ident.get_alias().lower() for ident in _walk(statement)
        if isinstance(ident, Identifier) and ident.get_alias()
    )
    functions = {f.lower() for f in _validator._ALLOWED_FUNCTIONS}
    for token in statement.flatten():
        if token.ttype is T.Name:
            name = token.value.lower()
            if name not in allowed and name not in functions:
                raise ValidationRejected(REASON_UNAPPROVED_COLUMN, token.value)


def _schema_context(files: list[dict]) -> str:
    """Per-file context: the entry text plus approved value hints only."""
    blocks = []
    for served in files:
        contract = served["contract"]
        lines = [entry_text_for_file(contract)]
        for column in contract.get("columns", []):
            hints = column.get("value_hints") or []
            if hints:
                lines.append(f"  values of {column['name']}: " + ", ".join(str(h) for h in hints))
        blocks.append("\n".join(lines))
    return (
        "Each table below is one separate uploaded file; a query reads exactly one of them.\n\n"
        + "\n\n".join(blocks)
    )


class TabularSQLGenerator:
    def __init__(self, cache: ParquetCache | None = None):
        self.max_attempts = max(1, settings.tabular_sql_max_attempts)
        self.cache = cache or ParquetCache()
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

    def _build_messages(self, question: str, schema_context: str, conversation_context: str | None,
                        feedback: str | None) -> list[dict]:
        user_parts = [f"Schema context (this tenant's published uploaded files only):\n{schema_context}"]
        if conversation_context:
            user_parts.append(f"Conversation context:\n{conversation_context}")
        user_parts.append(f"Question: {question}")
        if feedback:
            user_parts.append(feedback)
        return [
            {"role": "system", "content": EXTERNAL_SQL_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    async def _generate(self, question: str, schema_context: str, conversation_context: str | None,
                        feedback: str | None) -> str:
        from src.shared.observability import domain_metrics

        messages = self._build_messages(question, schema_context, conversation_context, feedback)
        async with domain_metrics.measure_llm_call("tabular_sql_generation") as call:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0,
                response_format={"type": "json_object"},
            )
            call.usage(response)
        return response.choices[0].message.content

    async def _resolve(self, tenant_id: str) -> dict:
        # Control-plane read (Design D10): its own platform session, never the
        # tenant-resolved one.
        factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with factory() as platform_session:
            return await resolve_tabular_capability(platform_session, tenant_id)

    async def answer(self, question: str, tenant_id: str, conversation_context: str | None = None,
                     deadline: float | None = None) -> TabularAnswer:
        capability = await self._resolve(tenant_id)
        if not capability.get("executable"):
            return TabularAnswer(reason=REASON_NOT_EXECUTABLE)
        files = capability["files"]
        contract = validation_contract(files)
        schema_context = _schema_context(files)

        feedback: str | None = None
        accepted: tuple[str, dict, list[str]] | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                content = await self._generate(question, schema_context, conversation_context, feedback)
            except Exception as exc:
                logger.warning("tabular_sql_generation_attempt",
                               extra={"attempt": attempt, "reason": "generation_error",
                                      "error_class": type(exc).__name__})
                feedback = _render_feedback("generation_error", None)
                continue
            parsed = _parse_llm_output(content)
            if parsed is None:
                logger.info("tabular_sql_generation_attempt", extra={"attempt": attempt, "reason": "malformed_output"})
                feedback = _render_feedback("malformed_output", None)
                continue
            sql, params = parsed
            if not sql:
                return TabularAnswer(reason=REASON_GENERATION_EXHAUSTED)
            missing = _missing_param_name(sql, params)
            if missing is not None:
                logger.info("tabular_sql_generation_attempt", extra={"attempt": attempt, "reason": "missing_param"})
                feedback = _render_feedback("missing_param", missing)
                continue
            try:
                validated = validate_statement(sql, contract)
                check_columns_strict(sql, contract, list(dict.fromkeys(validated["relations"])))
            except ValidationRejected as rejected:
                logger.info("tabular_sql_generation_attempt", extra={"attempt": attempt, "reason": rejected.reason})
                feedback = _render_feedback(rejected.reason, rejected.reference)
                continue
            accepted = (sql, params, list(dict.fromkeys(validated["relations"])))
            break
        if accepted is None:
            return TabularAnswer(reason=REASON_GENERATION_EXHAUSTED)

        sql, params, relations = accepted
        return await self.execute_accepted(tenant_id, files, contract, sql, params, relations)

    async def execute_accepted(self, tenant_id: str, files: list[dict], contract: dict, sql: str,
                               params: dict, relations: list[str]) -> TabularAnswer:
        """Loads only the accepted relations' served Parquet (from the local
        cache, keyed by the served version) and runs the statement once."""
        import asyncio

        index = relation_index(files)
        try:
            tables = {}
            for relation in relations:
                served = index[relation]
                tables[relation] = await asyncio.to_thread(
                    self.cache.get, tenant_id, served["file_id"], served["version"], served["parquet_key"],
                )
            rows, truncated = await tabular_executor.execute(tables, sql, params)
        except tabular_executor.TabularExecutionFailed as failed:
            return TabularAnswer(reason=failed.reason)
        except Exception as exc:
            logger.warning("tabular_execution_failed", extra={"error_class": type(exc).__name__})
            return TabularAnswer(reason=tabular_executor.REASON_FAILED)
        return TabularAnswer(
            rows=rows, truncated=truncated, relations=sorted(relations),
            columns=_columns_used(sql, relations, contract),
            files=[{"display_name": index[r]["display_name"], "version": index[r]["version"],
                    "sheet": index[r]["sheet"], "relation": r} for r in sorted(relations)],
        )
