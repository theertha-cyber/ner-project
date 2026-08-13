import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import Retriever

FORBIDDEN_ARG_KEYS = {"schema", "tenant_id", "tenant", "purpose"}

_JSON_SCHEMA_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}

# Natural-language search entry point used by the entity retrieval tool. Injected via
# ToolContext rather than imported directly so src/shared never imports src.chat_api
# (see design.md Decision 4 fallback).
#
# Called as
#   sql_search(query, session, schema, conversation_context, attempt_sink=…, deadline=…)
# `conversation_context` is the caller's list of prior `{"role", "content"}` messages,
# forwarded from ToolContext; the implementation decides how much of it to use. The two
# keyword arguments are the recovery loop's observability sink and its latency bound; an
# implementation without a bounded retry may accept and ignore them. The callable raises
# on definitive failure — a returned empty list means the query ran and legitimately
# matched nothing, which is not the same thing.
SqlSearch = Callable[..., Awaitable["list[dict] | None"]]


@dataclass(frozen=True)
class ToolContext:
    """Per-request scope handed to every tool call. Constructed by the calling
    application from authenticated request state — never from tool arguments."""

    tenant_id: str
    schema: str
    session: AsyncSession
    retriever: Retriever | None = None
    jwt_token: str | None = None
    max_top_k: int = 20
    sql_search: SqlSearch | None = None
    deadline: float | None = None
    # Prior `{"role", "content"}` messages of the conversation this call belongs to.
    # A tool receives only its own `arguments` — the planner's history never reaches it
    # — so anything a tool must resolve against earlier turns has to arrive here.
    conversation_context: list[dict] | None = None


def _render_result_line(item: Any) -> str:
    if isinstance(item, RetrievalResult):
        return (
            f"- document_id={item.document_id} chunk_index={item.chunk_index} "
            f"score={item.similarity_score:.4f}: {item.chunk_text}"
        )
    return f"- {item}"


@dataclass
class ToolResult:
    tool_name: str
    results: list[Any] = field(default_factory=list)
    latency_ms: float = 0.0
    degraded: bool = False
    error: str | None = None
    candidate_document_ids: set[str] = field(default_factory=set)
    # Opaque per-call diagnostic records (e.g. the SQL recovery loop's per-attempt
    # trace). Internal observability only — never rendered into an observation and
    # never part of any HTTP response.
    diagnostics: list[Any] = field(default_factory=list)
    # `{"returned": int, "matched": int | None, "truncated": bool}` when the capability
    # can report it. Prompt assembly needs this to know whether the rows it admits are
    # the complete answer — without it the prompt asserts a truncated list is exhaustive.
    result_completeness: dict | None = None

    def to_observation(self, limit: int) -> str:
        """Renders this result into a plain-text observation for an LLM conversation.
        Truncates the rendered text to `limit` characters; never mutates `results`."""
        if self.error:
            text = f"Tool '{self.tool_name}' failed: {self.error}"
        elif not self.results:
            text = f"Tool '{self.tool_name}' returned no results."
        else:
            lines = [f"Tool '{self.tool_name}' returned {len(self.results)} result(s):"]
            lines.extend(_render_result_line(item) for item in self.results)
            text = "\n".join(lines)

        if len(text) > limit:
            suffix = "... [truncated]"
            text = text[: max(limit - len(suffix), 0)].rstrip() + suffix
        return text


class RetrievalTool(Protocol):
    name: str
    description: str
    args_schema: dict

    async def call(self, args: dict, context: ToolContext) -> ToolResult: ...


class ArgValidationError(Exception):
    pass


def validate_args(args_schema: dict, args: dict) -> None:
    """Validates `args` against a minimal JSON-Schema-shaped `args_schema` (type,
    properties, required). Raises ArgValidationError on any violation, including
    unknown keys — tools never accept arguments outside their declared schema."""
    if not isinstance(args, dict):
        raise ArgValidationError("arguments must be an object")

    properties = args_schema.get("properties", {})
    required = args_schema.get("required", [])

    unknown = set(args) - set(properties)
    if unknown:
        raise ArgValidationError(f"unknown argument(s): {sorted(unknown)}")

    for key in required:
        if key not in args:
            raise ArgValidationError(f"missing required argument: {key}")

    for key, value in args.items():
        prop_schema = properties.get(key, {})
        expected_type = prop_schema.get("type")
        py_type = _JSON_SCHEMA_TYPES.get(expected_type)
        if py_type is not None and not isinstance(value, py_type):
            raise ArgValidationError(f"argument '{key}' must be of type '{expected_type}'")
        if expected_type == "boolean" and isinstance(value, bool):
            continue
        if expected_type == "integer" and isinstance(value, bool):
            raise ArgValidationError(f"argument '{key}' must be of type 'integer'")


def assert_no_tenancy_params(args_schema: dict, tool_name: str) -> None:
    properties = set(args_schema.get("properties", {}))
    leaked = properties & FORBIDDEN_ARG_KEYS
    if leaked:
        raise ValueError(f"tool '{tool_name}' declares forbidden tenancy argument(s): {sorted(leaked)}")


async def run_tool(
    name: str,
    args_schema: dict,
    args: dict,
    context: ToolContext,
    executor: Callable[[dict, ToolContext], Awaitable[tuple[list[Any], bool]]],
) -> ToolResult:
    """Shared execution wrapper: validates args, times the call, and converts any
    exception raised by `executor` into an error ToolResult rather than propagating."""
    start = time.monotonic()
    try:
        validate_args(args_schema, args)
    except ArgValidationError as e:
        return ToolResult(tool_name=name, results=[], latency_ms=0.0, degraded=False, error=str(e))

    if context.deadline is not None and context.deadline <= start:
        return ToolResult(tool_name=name, results=[], latency_ms=0.0, degraded=False, error="budget exhausted: deadline already passed")

    try:
        results, degraded = await executor(args, context)
        elapsed_ms = (time.monotonic() - start) * 1000
        return ToolResult(tool_name=name, results=results, latency_ms=elapsed_ms, degraded=degraded, error=None)
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ToolResult(tool_name=name, results=[], latency_ms=elapsed_ms, degraded=False, error=str(e))
