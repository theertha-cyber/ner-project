"""Drift-gated read-only external query execution (CAP-4, ADR-013).

Order per execution: drift check → AST validation → parameterized execution
through the tenant-scoped credential with a server row cap and a ten-second
statement timeout. Results are response-only rows; nothing is written to
platform storage.

``AzureExternalDatabase`` is the production seam implementation (asyncpg with
``SET TRANSACTION READ ONLY`` + ``statement_timeout``); it is registered only
where a resolvable secret reference and activation evidence exist. Tests use
``FixtureExternalDatabase``. Without a registered live implementation the path
fails closed with ``not_active_connection`` — live Azure verification stays
deferred per run provisioning.
"""

from __future__ import annotations

import logging
import re

from src.shared.external_postgres import drift as drift_gate
from src.shared.external_postgres.drift import DriftBlocked, ExternalDatabase
from src.shared.external_postgres.validator import (
    ValidationRejected,
    validate_statement,
)

logger = logging.getLogger(__name__)

ROW_CAP = 100
STATEMENT_TIMEOUT_MS = 10_000

EXECUTION_OUTCOMES = frozenset(
    {"success", "drift_blocked", "validation_rejected", "execution_failed"}
)

_LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)", re.IGNORECASE)


def clamp_limit(statement: str, row_cap: int = ROW_CAP) -> str:
    """Enforce the server row cap: keep a smaller LIMIT, else append one."""
    match = _LIMIT_RE.search(statement)
    if match and int(match.group(1)) <= row_cap:
        return statement
    if match:
        return _LIMIT_RE.sub(f"LIMIT {row_cap}", statement, count=1)
    return f"{statement.rstrip().rstrip(';')} LIMIT {row_cap}"


def _record(outcome: str, reason: str) -> None:
    try:
        from src.shared.observability.domain_metrics import record_external_pg_query
    except Exception:
        return
    try:
        record_external_pg_query(outcome=outcome, reason=reason)
    except Exception:
        logger.debug("metric_record_failed", extra={"family": "external_pg"})


async def execute_external_query(database: ExternalDatabase, contract: dict,
                                 statement: str, params: dict | None = None) -> dict:
    """Run one drift-gated, validated, parameterized external SELECT.

    Returns ``{"rows": [...], "row_count": n, "truncated": bool}``. Raises
    :class:`DriftBlocked` or :class:`ValidationRejected`, or
    :class:`ExternalExecutionFailed` when the database itself fails.
    ``params`` values are bound, never interpolated; the executed text carries
    placeholders only.
    """
    params = dict(params or {})
    try:
        await drift_gate.check(database, contract)
    except DriftBlocked as blocked:
        _record("drift_blocked", blocked.outcome)
        raise
    try:
        validate_statement(statement, contract["canonical"])
    except ValidationRejected as rejected:
        _record("validation_rejected", rejected.reason)
        # Finite reason class only — never the statement, literals, or rows.
        logger.warning(
            "external_pg_statement_rejected",
            extra={"reason": rejected.reason,
                   "reference": rejected.reference},
        )
        raise
    bounded = clamp_limit(statement)
    try:
        rows = await database.execute(bounded, params,
                                      STATEMENT_TIMEOUT_MS, ROW_CAP)
    except Exception as exc:
        _record("execution_failed", type(exc).__name__)
        logger.warning(
            "external_pg_execution_failed",
            extra={"error_class": type(exc).__name__},
        )
        raise ExternalExecutionFailed(type(exc).__name__) from None
    _record("success", "none")
    logger.info(
        "external_pg_query_executed",
        extra={"row_count": len(rows)},
    )
    return {"rows": rows, "row_count": len(rows), "truncated": len(rows) >= ROW_CAP}


class ExternalExecutionFailed(Exception):
    """The external database failed; carries the error class only."""

    def __init__(self, error_class: str):
        super().__init__(error_class)
        self.error_class = error_class
