"""Contract-grounded external SQL generation (ADR-016).

Turns a natural-language question into one validated, parameterized SELECT
against the authenticated tenant's published external PostgreSQL contract.
The prompt is fixed, code-owned rules — mirroring the AST validator's grammar
exactly — plus schema context rendered from the published version's index
entries (relation/column names, descriptions, and join keys). Every candidate
statement is checked with the existing validator *locally*, before any
tenant-database contact; retries feed back only the finite rejection reason
and the offending contract identifier, never row values or live metadata.
Only a locally accepted statement reaches the drift-gated executor, and it
runs at most once.

The LLM client here is never wrapped by a prompt/output-capturing tracer:
schema context and generated SQL would otherwise reach LangSmith, which
ADR-013 forbids for external telemetry.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.config import settings
from src.shared.database import get_engine
from src.shared.external_postgres import validator as _validator
from src.shared.external_postgres.azure_database import (
    ExternalDatabaseUnavailable,
    resolve_live_database,
)
from src.shared.external_postgres.capability import resolve_external_capability
from src.shared.external_postgres.connector import (
    ExternalExecutionFailed,
    execute_external_query,
)
from src.shared.external_postgres.drift import DriftBlocked
from src.shared.external_postgres.index import fetch_entries
from src.shared.external_postgres.validator import ValidationRejected, validate_statement
from src.shared.tenant_schema import schema_for_tenant

logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    """Built from `validator._ALLOWED_FUNCTIONS` rather than restated as a second
    list, so the prompt and the validator's grammar cannot drift apart
    (design.md Decision 4)."""
    functions = ", ".join(sorted(_validator._ALLOWED_FUNCTIONS))
    return f"""You generate one read-only SQL query against a tenant's PostgreSQL database.

Rules, all mandatory:
- Exactly one SELECT statement. No other statement type.
- Bare relation names only — never schema-qualified (no `public.table`).
- Only the relations, columns, and joins named in the schema context below.
- Every value — every string, number, date, DATE_TRUNC unit, and each value of
  an IN list as its own placeholder — is a named placeholder `%(pN)s`, with
  its value in `params`. Never write a literal value directly in the SQL.
- Never write LIMIT or OFFSET. The server applies its own row cap.
- No subqueries, WITH/CTEs, UNION/INTERSECT/EXCEPT, or window functions
  (no OVER).
- The only functions you may use are: {functions}.
- For name matching use `ILIKE %(pN)s` with `%` wildcards inside the
  parameter value, not in the SQL text.
- Respond with a single JSON object of the exact shape
  {{"sql": "<statement>", "params": {{"p1": ...}}}} and nothing else.
- If the question cannot be answered within these rules, respond with
  {{"sql": "", "params": {{}}}}.
"""


EXTERNAL_SQL_SYSTEM_PROMPT = _build_system_prompt()

_PLACEHOLDER_RE = re.compile(r"%\(([^)]+)\)s")


@dataclass
class ExternalAnswer:
    """The generator's outcome for one question.

    `reason` is `None` on success; every failure path sets it to one finite
    class and leaves `rows` empty. `relations` names the contract relations
    the accepted statement used, for the citation and evidence channel."""

    rows: list[dict] = field(default_factory=list)
    truncated: bool = False
    relations: list[str] = field(default_factory=list)
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.reason is None


def _metrics():
    """Resolved on use, like the other generators, so this module never pulls
    the observability package's own import graph in at module load time."""
    from src.shared.observability import domain_metrics

    return domain_metrics


def _parse_llm_output(content: str) -> tuple[str, dict] | None:
    """`{"sql": str, "params": dict}` from the raw model output, or `None` for
    anything else — including valid JSON of the wrong shape."""
    try:
        parsed = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    sql, params = parsed.get("sql"), parsed.get("params")
    if not isinstance(sql, str) or not isinstance(params, dict):
        return None
    return sql, params


def _missing_param_name(sql: str, params: dict) -> str | None:
    """The first `%(name)s` placeholder in `sql` with no matching key in
    `params`, or `None` when every placeholder is bound."""
    for match in _PLACEHOLDER_RE.finditer(sql):
        name = match.group(1)
        if name not in params:
            return name
    return None


def _render_feedback(reason: str, reference: str | None) -> str:
    """The retry block for the next attempt's prompt: the finite reason class
    and the offending contract identifier only — never the rejected SQL, a
    row value, or live metadata (design.md Decision 3)."""
    if reference:
        return (
            f"\nYour previous attempt was rejected: {reason} ({reference}). "
            "Do not repeat it. Write a different statement that avoids this issue."
        )
    return (
        f"\nYour previous attempt was rejected: {reason}. "
        "Do not repeat it. Write a different statement that avoids this issue."
    )


class ExternalSQLGenerator:
    def __init__(self):
        self.max_attempts = max(1, settings.external_pg_sql_max_attempts)
        self.max_context_chars = settings.external_pg_schema_context_max_chars
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

    def _build_messages(
        self, question: str, schema_context: str,
        conversation_context: str | None, feedback: str | None,
    ) -> list[dict]:
        user_parts = [f"Schema context (this tenant's published contract only):\n{schema_context}"]
        if conversation_context:
            user_parts.append(f"Conversation context:\n{conversation_context}")
        user_parts.append(f"Question: {question}")
        if feedback:
            user_parts.append(feedback)
        return [
            {"role": "system", "content": EXTERNAL_SQL_SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    async def _generate(
        self, question: str, schema_context: str,
        conversation_context: str | None, feedback: str | None,
    ) -> str:
        messages = self._build_messages(question, schema_context, conversation_context, feedback)
        async with _metrics().measure_llm_call("external_sql_generation") as call:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0,
                response_format={"type": "json_object"},
            )
            call.usage(response)
        return response.choices[0].message.content

    async def answer(
        self, question: str, session, tenant_id: str,
        conversation_context: str | None = None, deadline: float | None = None,
    ) -> ExternalAnswer:
        """Answers one external chat question end to end (design.md Decision 3).
        `deadline` is accepted for interface symmetry with the retrieval tools'
        recovery loop; generation attempts are bounded by count, not by time."""
        # Control-plane reads (Design D10) go on their own platform session:
        # `session` here is the tenant-resolved one, which for a `tenant_owned`
        # tenant is their own store with no `public.*` tables at all. The
        # `fetch_entries` call below is the opposite case and correctly keeps
        # `session` — the schema index lives in the tenant's own schema.
        platform_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with platform_factory() as platform_session:
            capability = await resolve_external_capability(platform_session, tenant_id)
        if not capability.get("executable"):
            return ExternalAnswer(reason=capability.get("reason") or "not_active_connection")

        connection_id = capability["connection_id"]
        contract = capability["contract"]
        schema = schema_for_tenant(tenant_id)

        entries = await fetch_entries(session, schema, connection_id, contract["version"])
        schema_context = "\n\n".join(e["entry"] for e in entries)
        if len(schema_context) > self.max_context_chars:
            return ExternalAnswer(reason="schema_context_too_large")

        feedback: str | None = None
        accepted_sql: str | None = None
        accepted_params: dict = {}
        accepted_relations: list[str] = []

        for attempt in range(1, self.max_attempts + 1):
            try:
                content = await self._generate(question, schema_context, conversation_context, feedback)
            except Exception as exc:
                logger.warning(
                    "external_sql_generation_attempt",
                    extra={"attempt": attempt, "reason": "generation_error",
                           "error_class": type(exc).__name__},
                )
                feedback = _render_feedback("generation_error", None)
                continue

            parsed = _parse_llm_output(content)
            if parsed is None:
                logger.info(
                    "external_sql_generation_attempt",
                    extra={"attempt": attempt, "reason": "malformed_output"},
                )
                feedback = _render_feedback("malformed_output", None)
                continue

            sql, params = parsed
            if not sql:
                return ExternalAnswer(reason="unanswerable")

            missing = _missing_param_name(sql, params)
            if missing is not None:
                logger.info(
                    "external_sql_generation_attempt",
                    extra={"attempt": attempt, "reason": "missing_param"},
                )
                feedback = _render_feedback("missing_param", missing)
                continue

            try:
                validated = validate_statement(sql, contract["canonical"])
            except ValidationRejected as rejected:
                logger.info(
                    "external_sql_generation_attempt",
                    extra={"attempt": attempt, "reason": rejected.reason},
                )
                feedback = _render_feedback(rejected.reason, rejected.reference)
                continue

            accepted_sql, accepted_params = sql, params
            accepted_relations = validated["relations"]
            break
        else:
            return ExternalAnswer(reason="generation_exhausted")

        try:
            # Same control-plane read as the capability resolution above — the
            # connection row it resolves lives in `public`, not the tenant store.
            async with platform_factory() as platform_session:
                database = await resolve_live_database(platform_session, tenant_id)
        except ExternalDatabaseUnavailable:
            return ExternalAnswer(reason="not_active_connection")

        try:
            result = await execute_external_query(database, contract, accepted_sql, accepted_params)
        except DriftBlocked as blocked:
            return ExternalAnswer(reason=blocked.outcome)
        except (ValidationRejected, ExternalExecutionFailed):
            return ExternalAnswer(reason="execution_failed")

        return ExternalAnswer(
            rows=result["rows"], truncated=result["truncated"],
            relations=sorted(set(accepted_relations)),
        )
