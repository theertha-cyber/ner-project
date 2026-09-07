"""Reading a tenant's integration profile from control-plane storage.

The profile lives in `public`, never in a tenant schema, so the platform can read a
tenant's adapter selection even when that tenant's own infrastructure is unreachable.
Adapter selection is platform configuration, not tenant content.
"""

from dataclasses import dataclass

from sqlalchemy import text

from src.shared.integration_profile.adapters import (
    DEFAULT_CONTENT_STORE_ADAPTER,
    DEFAULT_INDEX_ADAPTER,
    DEFAULT_RELATIONAL_ADAPTER,
    DEFAULT_SOURCE_ADAPTER,
)
from src.shared.document_retention import RETENTION_PLATFORM_BLOB
from src.shared.integration_profile.status import STATUS_DRAFT

PROFILE_TABLE = "public.tenant_integration_profiles"


@dataclass(frozen=True)
class IntegrationProfile:
    tenant_id: str
    source_adapter: str = DEFAULT_SOURCE_ADAPTER
    content_store_adapter: str = DEFAULT_CONTENT_STORE_ADAPTER
    relational_adapter: str = DEFAULT_RELATIONAL_ADAPTER
    index_adapter: str = DEFAULT_INDEX_ADAPTER
    retention_mode: str = RETENTION_PLATFORM_BLOB
    status: str = STATUS_DRAFT
    configuration: dict | None = None
    secret_references: dict | None = None
    status_reason: str | None = None

    def selections(self) -> dict:
        return {
            "source_adapter": self.source_adapter,
            "content_store_adapter": self.content_store_adapter,
            "relational_adapter": self.relational_adapter,
            "index_adapter": self.index_adapter,
        }


def default_profile(tenant_id: str) -> IntegrationProfile:
    """What a tenant with no recorded profile gets: the platform defaults, retained."""
    return IntegrationProfile(tenant_id=tenant_id)


async def load_profile(session, tenant_id: str) -> IntegrationProfile:
    """Read a tenant's profile, falling back to the platform defaults.

    A missing table or a missing row is not an error. The migration that creates the
    table backfills a default profile per tenant, and a tenant provisioned in between is
    served the same defaults it would have been given — never a failure on the ingestion
    path over a control-plane row that has not been written yet.
    """
    # Asked rather than attempted-and-caught: a failed statement aborts the caller's
    # transaction, and this read shares the ingestion operation's session.
    exists = await session.execute(
        text("SELECT to_regclass(:table) IS NOT NULL"), {"table": PROFILE_TABLE}
    )
    if not exists.scalar():
        return default_profile(tenant_id)

    result = await session.execute(
        text(
            f"""
            SELECT source_adapter, content_store_adapter, relational_adapter,
                   index_adapter, retention_mode, status, configuration,
                   secret_references, status_reason
            FROM {PROFILE_TABLE}
            WHERE tenant_id = :tid
            """
        ),
        {"tid": tenant_id},
    )

    row = result.fetchone()
    if row is None:
        return default_profile(tenant_id)

    return IntegrationProfile(
        tenant_id=tenant_id,
        source_adapter=row.source_adapter,
        content_store_adapter=row.content_store_adapter,
        relational_adapter=row.relational_adapter,
        index_adapter=row.index_adapter,
        retention_mode=row.retention_mode,
        status=row.status,
        configuration=row.configuration,
        secret_references=row.secret_references,
        status_reason=row.status_reason,
    )
