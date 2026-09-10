"""Reopenable content for source-only sync documents (CAP-3, ADR-012).

`source_only` retention stores no bytes, so processing re-acquires them: this
module registers the `azure_blob` source reopener with the OCR worker. The
reopener resolves the connection row for the document's own tenant (the row is
authority — a document never names a tenant to sync as), acquires the bytes
through the provider seam, and returns them. Anything unresolvable returns
None, preserving the worker's existing failure path.

Importing this module has the side effect of registering the reopener. The
Celery worker imports it at task time; tests import it in setup.
"""

from sqlalchemy import text

from src.document_service.blob_sync.sync import SOURCE_TYPE_AZURE_BLOB


async def reopen_azure_blob_content(tenant_id: str, source_id: str,
                                    external_id: str | None) -> bytes | None:
    """Re-acquire one sync document's bytes. Identity in, bytes out, or None."""
    if not external_id:
        return None
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from src.document_service.blob_sync.provider import get_provider
    from src.shared.database import get_engine
    from src.shared.data_sources.store import CONNECTIONS_TABLE
    from src.shared.tenant_schema import schema_for_tenant  # noqa: F401

    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    f"SELECT tenant_id FROM {CONNECTIONS_TABLE} "
                    "WHERE id = :cid AND tenant_id = :tid"
                ),
                {"cid": source_id, "tid": tenant_id},
            )
        ).fetchone()
    if row is None:
        return None
    try:
        return await get_provider(source_id).acquire(external_id)
    except Exception:
        return None


def register_azure_blob_reopener() -> None:
    from src.document_service.services import ocr_worker

    ocr_worker.register_source_reopener(
        SOURCE_TYPE_AZURE_BLOB, reopen_azure_blob_content
    )


register_azure_blob_reopener()
