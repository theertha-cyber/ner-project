"""Server-side external-query capability resolution (CAP-4, ADR-001/011/013).

Answers one question: for this authenticated tenant, is external PostgreSQL
chat executable right now, and under which contract? Authority is the CAP-2
control-plane row (an `active` azure_postgresql connection owned by the
tenant) plus a published canonical contract version for that connection.
Caller-supplied tenant or connection identifiers are never authority.
"""

from __future__ import annotations

import logging

from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL
from src.shared.data_sources.resolver import active_connection
from src.shared.data_sources.store import CONNECTIONS_TABLE
from src.shared.external_postgres.contract import (
    REASON_NOT_ACTIVE_CONNECTION,
    accepted_contract,
)

logger = logging.getLogger(__name__)

NOT_ACTIVE = REASON_NOT_ACTIVE_CONNECTION
NO_PUBLISHED_CONTRACT = "no_published_contract"


async def resolve_external_capability(session, tenant_id: str) -> dict:
    """Resolve the tenant's executable external-query capability.

    Returns ``{"executable": True, "connection_id": ..., "contract": {...}}``
    or ``{"executable": False, "reason": <finite>}``. Never raises for a
    missing connection or contract — absence resolves to non-executable.

    `session` must be a **platform** session (Design D10). Both reads below are
    control-plane — `public.tenant_data_source_connections` and
    `public.external_pg_contracts` — and a `tenant_owned` tenant's resolved
    session points at their own store, which has no `public.*` tables at all.
    Passing one there fails the query and leaves that session's transaction
    aborted, taking every later query on it down with it.
    """
    connection = await active_connection(session, tenant_id, PROVIDER_AZURE_POSTGRESQL)
    if connection is None:
        return {"executable": False, "reason": NOT_ACTIVE}
    connection_id = str(connection.id)
    # Belt-and-braces: the resolver query already constrains active, but the
    # capability must not survive a status constant rename silently.
    if getattr(connection, "status", None) != lc.STATUS_ACTIVE:
        return {"executable": False, "reason": NOT_ACTIVE}
    contract = await accepted_contract(session, tenant_id, connection_id)
    if contract is None:
        logger.info(
            "external_pg_capability_resolved",
            extra={"executable": False, "reason": NO_PUBLISHED_CONTRACT},
        )
        return {"executable": False, "reason": NO_PUBLISHED_CONTRACT,
                "connection_id": connection_id}
    logger.info("external_pg_capability_resolved", extra={"executable": True})
    return {"executable": True, "connection_id": connection_id, "contract": contract}


async def is_external_request_executable(session, tenant_id: str,
                                         connection_id: str) -> bool:
    """Whether one named connection may serve this tenant's external request."""
    capability = await resolve_external_capability(session, tenant_id)
    return bool(capability.get("executable")) and (
        capability.get("connection_id") == connection_id
    )


__all__ = [
    "CONNECTIONS_TABLE",
    "NO_PUBLISHED_CONTRACT",
    "NOT_ACTIVE",
    "is_external_request_executable",
    "resolve_external_capability",
]
