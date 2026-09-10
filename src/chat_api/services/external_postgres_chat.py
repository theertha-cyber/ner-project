"""External PostgreSQL chat capability (CAP-4, ADR-013).

A separate selection from the platform SQL path: the caller resolves the
tenant's executable external capability server-side, then executes one
drift-gated, AST-validated, parameterized SELECT. The LLM never receives the
credential or a direct connection — it proposes a statement and parameters,
and this module validates and executes them.

Rejected statements record only a finite rejection reason class and
correlation metadata, never SQL text (chat-api delta spec). Result rows are
response-only and never written to platform storage.
"""

from __future__ import annotations

import logging

from src.shared.external_postgres.capability import resolve_external_capability
from src.shared.external_postgres.connector import execute_external_query
from src.shared.external_postgres.drift import DriftBlocked, ExternalDatabase
from src.shared.external_postgres.validator import ValidationRejected

logger = logging.getLogger(__name__)

SOURCE_NAME = "external_postgresql"


async def external_chat_answer(session, tenant_id: str, statement: str,
                               params: dict | None,
                               database: ExternalDatabase) -> dict:
    """Answer one external chat turn: resolve, then drift-gated execution.

    Returns ``{"source": "external_postgresql", "rows": [...],
    "row_count": n, "truncated": bool, "connection_id": ...}``. Raises
    :class:`ExternalNotExecutable` (finite reason), :class:`DriftBlocked`,
    :class:`ValidationRejected`, or :class:`ExternalExecutionFailed`.
    """
    capability = await resolve_external_capability(session, tenant_id)
    if not capability.get("executable"):
        raise ExternalNotExecutable(capability.get("reason", "not_active_connection"))
    # The resolved connection id is authority: a caller-supplied connection
    # identifier is never accepted here.
    result = await execute_external_query(
        database, capability["contract"], statement, params
    )
    logger.info(
        "external_pg_chat_answered",
        extra={"row_count": result["row_count"]},
    )
    return {"source": SOURCE_NAME, "connection_id": capability["connection_id"], **result}


class ExternalNotExecutable(Exception):
    """No executable external capability for this tenant; finite reason only."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
