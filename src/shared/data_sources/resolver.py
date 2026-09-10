"""Server-side tenant capability resolution for approved Azure connections (CAP-2).

The resolver answers one question: for this authenticated tenant, which approved
Azure capabilities are executable right now? Authority is the control-plane row —
an `active` connection owned by the tenant — never portal input, chat input, or a
queued payload. Anything else recorded (drafts, unsupported selections, other
tenants' connections) resolves to nothing.

The Azure-only executable exception (delta `tenant-integration-profile` spec):
a recorded non-default adapter selection is executable only when it names an
approved Azure adapter *and* the owning tenant holds an active connection of the
matching provider. Platform defaults remain executable as before; every other
recorded selection stays recorded-but-unsupported.
"""

from sqlalchemy import text

from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import (
    PROVIDER_AZURE_BLOB,
    PROVIDER_AZURE_POSTGRESQL,
    PROVIDERS,
)
from src.shared.data_sources.store import CONNECTIONS_TABLE
from src.shared.integration_profile.adapters import EXECUTABLE_ADAPTERS

# Recorded profile selections that an active approved Azure connection makes
# executable, per (slot, recorded value) -> provider. Closed: anything absent
# here is not an Azure exception, whatever it records.
AZURE_EXECUTABLE_SELECTIONS = {
    ("source_adapter", "azure_blob"): PROVIDER_AZURE_BLOB,
    ("content_store_adapter", "tenant_azure_blob"): PROVIDER_AZURE_BLOB,
    ("relational_adapter", "tenant_postgresql"): PROVIDER_AZURE_POSTGRESQL,
    ("index_adapter", "tenant_pgvector"): PROVIDER_AZURE_POSTGRESQL,
}


async def active_connection(session, tenant_id: str, provider: str):
    """The tenant's active connection of one approved provider, or None.

    Unknown providers resolve to None rather than raising: resolution is a
    lookup, and validation belongs to the write path.
    """
    if provider not in PROVIDERS:
        return None
    result = await session.execute(
        text(
            f"SELECT * FROM {CONNECTIONS_TABLE} "
            f"WHERE tenant_id = :tid AND provider = :provider "
            f"AND status = '{lc.STATUS_ACTIVE}'"
        ),
        {"tid": tenant_id, "provider": provider},
    )
    return result.fetchone()


async def executable_providers(session, tenant_id: str) -> list[str]:
    """Approved providers the tenant may execute right now, sorted."""
    found = []
    for provider in sorted(PROVIDERS):
        if await active_connection(session, tenant_id, provider) is not None:
            found.append(provider)
    return found


async def is_selection_executable(
    session, tenant_id: str, slot: str, value: str | None
) -> bool:
    """Whether one recorded profile selection may serve a request.

    Platform defaults are executable as before. A recorded Azure selection is
    executable only with a matching active tenant-owned connection. Everything
    else — including another tenant's active connection — is not.
    """
    if value is None or EXECUTABLE_ADAPTERS.get(slot) == value:
        return True
    provider = AZURE_EXECUTABLE_SELECTIONS.get((slot, value))
    if provider is None:
        return False
    return await active_connection(session, tenant_id, provider) is not None
