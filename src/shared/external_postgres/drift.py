"""Live fingerprint drift gate (CAP-4, ADR-013, NFR-RELY-002).

Before every external query the connector introspects live contract-relevant
metadata through the :class:`ExternalDatabase` seam and recomputes the
canonical fingerprint from the accepted contract's join graph. Outcomes:

- clean — fingerprints match; execution may proceed.
- drift_mismatch — live metadata differs; blocked until a replacement
  contract is accepted.
- metadata_unavailable — introspection failed; blocked with a distinct reason
  (operators can tell downtime from schema change).
- fingerprint_failure — fingerprint computation failed; blocked.

Every non-clean outcome raises :class:`DriftBlocked` before SQL parsing or
execution. Only finite outcome/reason classes and correlation metadata are
logged; never metadata values beyond relation/column *names*.
"""

from __future__ import annotations

import logging

from src.shared.external_postgres.contract import fingerprint_of_metadata

logger = logging.getLogger(__name__)

OUTCOME_CLEAN = "clean"
OUTCOME_DRIFT_MISMATCH = "drift_mismatch"
OUTCOME_METADATA_UNAVAILABLE = "metadata_unavailable"
OUTCOME_FINGERPRINT_FAILURE = "fingerprint_failure"

DRIFT_OUTCOMES = frozenset(
    {
        OUTCOME_CLEAN,
        OUTCOME_DRIFT_MISMATCH,
        OUTCOME_METADATA_UNAVAILABLE,
        OUTCOME_FINGERPRINT_FAILURE,
    }
)


class ExternalDatabase:
    """Seam for live external metadata + execution.

    Production implements introspection/execution against Azure Database for
    PostgreSQL; tests and local fixtures register fakes. Live Azure
    verification is deferred per run provisioning.
    """

    async def introspect(self, relations: list[str]) -> dict[str, list[str]]:
        """Return {relation: [columns]} for the named relations."""
        raise NotImplementedError

    async def execute(self, statement: str, params: dict, timeout_ms: int,
                      row_cap: int) -> list[dict]:
        """Execute one parameterized SELECT; returns response-only rows."""
        raise NotImplementedError


class FixtureExternalDatabase(ExternalDatabase):
    """In-memory fake: declared metadata plus scripted rows, no network."""

    def __init__(self, metadata: dict[str, list[str]] | None = None,
                 rows: list[dict] | None = None, available: bool = True):
        self._metadata = {k: list(v) for k, v in (metadata or {}).items()}
        self._rows = list(rows or [])
        self.available = available
        self.executions: list[dict] = []

    async def introspect(self, relations: list[str]) -> dict[str, list[str]]:
        if not self.available:
            raise ConnectionError("fixture-unavailable")
        return {name: list(self._metadata.get(name, [])) for name in relations}

    async def execute(self, statement: str, params: dict, timeout_ms: int,
                      row_cap: int) -> list[dict]:
        self.executions.append({"params": dict(params), "row_cap": row_cap})
        return [dict(r) for r in self._rows[:row_cap]]


class DriftBlocked(Exception):
    """Execution blocked by the drift gate; finite outcome only."""

    def __init__(self, outcome: str):
        super().__init__(outcome)
        self.outcome = outcome


async def check(database: ExternalDatabase, contract: dict) -> str:
    """Compare live metadata against the accepted fingerprint.

    Returns "clean" or raises DriftBlocked. Never raises the underlying
    introspection error to callers.
    """
    canonical = contract["canonical"]
    relations = list(canonical.get("relations", {}).keys())
    joins = canonical.get("joins", [])
    try:
        live = await database.introspect(relations)
    except Exception as exc:
        logger.warning(
            "external_pg_drift_check",
            extra={"outcome": OUTCOME_METADATA_UNAVAILABLE,
                   "error_class": type(exc).__name__},
        )
        raise DriftBlocked(OUTCOME_METADATA_UNAVAILABLE) from None
    try:
        live_fingerprint = fingerprint_of_metadata(live, joins)
    except Exception:
        logger.warning(
            "external_pg_drift_check",
            extra={"outcome": OUTCOME_FINGERPRINT_FAILURE},
        )
        raise DriftBlocked(OUTCOME_FINGERPRINT_FAILURE) from None
    if live_fingerprint != contract["fingerprint"]:
        logger.warning(
            "external_pg_drift_check",
            extra={"outcome": OUTCOME_DRIFT_MISMATCH},
        )
        raise DriftBlocked(OUTCOME_DRIFT_MISMATCH)
    logger.info("external_pg_drift_check", extra={"outcome": OUTCOME_CLEAN})
    return OUTCOME_CLEAN
