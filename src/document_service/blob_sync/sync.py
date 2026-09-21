"""The one tenant-bound durable Blob sync use case (CAP-3, ADR-012).

Manual, scheduled, retry, and catch-up triggers all execute `run_sync`. The
payload is identity only (tenant, connection, trigger class); everything else
is re-read from the control plane, the ledger, and the provider at execution
time, so any trigger is replayable after a restart.

The use case never resolves secrets and never surfaces configuration values:
it reads the active-connection row for authority and the provider seam for
bytes. The live provider is deferred (it raises `BlobProviderUnavailable`),
so until approved Azure resources exist every run ends `blocked` with
`prerequisite_missing` — inactive by construction, never half-synced.
"""

import logging
import uuid

from sqlalchemy import text

from src.document_service.blob_sync import ledger
from src.document_service.blob_sync.provider import (
    BlobObjectMissing,
    BlobProviderError,
    BlobProviderUnavailable,
    get_provider,
)
from src.document_service.ingestion.contract import (
    ActorKind,
    ContentAccess,
    ContentAcquisition,
    IngestingActor,
    NormalizedDocument,
    SourceReference,
)

logger = logging.getLogger(__name__)

SOURCE_TYPE_AZURE_BLOB = "azure_blob"

# --- Finite trigger classes ------------------------------------------------------------

TRIGGER_MANUAL = "manual"
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_RETRY = "retry"
TRIGGER_CATCHUP = "catchup"

TRIGGERS = frozenset({TRIGGER_MANUAL, TRIGGER_SCHEDULED, TRIGGER_RETRY, TRIGGER_CATCHUP})

# --- Finite run outcomes and reasons ----------------------------------------------------

OUTCOME_SUCCEEDED = "succeeded"
OUTCOME_FAILED = "failed"
OUTCOME_BLOCKED = "blocked"
OUTCOME_LEASE_HELD = "lease_held"

OUTCOMES = frozenset({OUTCOME_SUCCEEDED, OUTCOME_FAILED, OUTCOME_BLOCKED, OUTCOME_LEASE_HELD})

REASON_NONE = "none"
REASON_INACTIVE_CONNECTION = "inactive_connection"
REASON_PREREQUISITE_MISSING = "prerequisite_missing"
REASON_LISTING_FAILED = "listing_failed"
REASON_LEASE_HELD = "lease_held"

REASONS = frozenset({
    REASON_NONE,
    REASON_INACTIVE_CONNECTION,
    REASON_PREREQUISITE_MISSING,
    REASON_LISTING_FAILED,
    REASON_LEASE_HELD,
})

# Retention modes under which a sync may proceed. `platform_blob` would durably
# persist Blob originals through common ingestion, so it blocks the run instead:
# the profile decides what is kept, and the sync refuses to keep what ADR-012
# forbids. `source_only` stores nothing (reopened at processing); `ephemeral`
# uses the working store with terminal release.
SYNC_ALLOWED_RETENTION = frozenset({"source_only", "ephemeral"})

# A source object must be absent from two consecutive successful enumerations
# before it counts as deleted: one absence adjacent to a listing failure keeps
# serving, because a failed listing is not evidence of anything.
MISSING_CONFIRMATIONS = 2

# Hidden-document causes, finite and safe.
CAUSE_SUPERSEDED = "superseded"
CAUSE_SOURCE_MISSING = "source_missing"


class SyncResult:
    def __init__(self, run_id, outcome, reason="none", seen=0, ingested=0,
                 skipped=0, failed=0):
        self.run_id = run_id
        self.outcome = outcome
        self.reason = reason
        self.seen = seen
        self.ingested = ingested
        self.skipped = skipped
        self.failed = failed


def _media_type(filename: str) -> str:
    dot = filename.rfind(".")
    suffix = filename[dot:].lower() if dot != -1 else ""
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix, "application/octet-stream")


def _temp_reference(connection_id: str, identity: str) -> str:
    # Sync-scoped working-store reference. Opaque, unguessable, never persisted
    # outside the run: the ledger links documents, never bytes.
    return f"sync-tmp/{connection_id}/{uuid.uuid4().hex}"


async def _active_blob_connection(session, tenant_id: str, connection_id: str):
    """Authority check: the row must exist, belong to this tenant, be azure_blob,
    and be active. Anything else resolves to None — never an exception the
    caller could mistake for permission."""
    from src.shared.data_sources import lifecycle as lc
    from src.shared.data_sources.providers import PROVIDER_AZURE_BLOB
    from src.shared.data_sources.store import CONNECTIONS_TABLE

    row = (
        await session.execute(
            text(
                "SELECT id, provider, status, configuration, secret_references "
                f"FROM {CONNECTIONS_TABLE} WHERE id = :cid AND tenant_id = :tid"
            ),
            {"cid": connection_id, "tid": tenant_id},
        )
    ).fetchone()
    if row is None or row[1] != PROVIDER_AZURE_BLOB or row[2] != lc.STATUS_ACTIVE:
        return None
    return row


def build_live_provider(tenant_id: str, configuration: dict, secret_references: dict):
    """Build a real SDK-backed provider from a connection's own config and
    resolved secret. Raises `BlobProviderUnavailable` for anything that keeps
    the connection from being usable — never half-configured. Shared by the
    sync path and the OCR reopener (`blob_sync.reopen`) so both build the same
    provider the same way, instead of each hitting the always-refusing default."""
    from src.document_service.blob_sync.azure_provider import AzureBlobLiveProvider
    from src.shared.data_sources.providers import (
        PROVIDER_AZURE_BLOB,
        PROVIDER_SECRET_KIND,
    )
    from src.shared.integration_profile.secrets import (
        SecretResolutionError,
        resolve_for_tenant,
    )

    if not isinstance(configuration, dict) or not isinstance(secret_references, dict):
        raise BlobProviderUnavailable("connection configuration unavailable")

    container = configuration.get("container")
    if not container:
        raise BlobProviderUnavailable("container is not configured")

    adapter_kind = PROVIDER_SECRET_KIND[PROVIDER_AZURE_BLOB]
    namespace = type(
        "_BlobConnectionSecrets",
        (),
        {"tenant_id": tenant_id, "secret_references": {adapter_kind: dict(secret_references)}},
    )()
    try:
        context = resolve_for_tenant(namespace, adapter_kind)
    except SecretResolutionError:
        raise BlobProviderUnavailable("secret reference unresolvable") from None
    connection_string = context.get("connection_string_ref")
    if not connection_string:
        raise BlobProviderUnavailable("connection string secret unresolvable")

    return AzureBlobLiveProvider(connection_string, container)


async def _profile_retention(session, tenant_id: str) -> str | None:
    from src.shared.integration_profile.store import load_profile

    try:
        profile = await load_profile(session, tenant_id)
    except Exception:
        return None
    return getattr(profile, "retention_mode", None)


async def run_sync(session_factory, tenant_id: str, connection_id: str,
                   trigger: str, *, provider=None,
                   make_ingestion_service=None, temp_store=None,
                   platform_session_factory=None) -> SyncResult:
    """Execute one durable synchronization. See module docstring for the contract.

    `session_factory` is the tenant's data plane (ledger and document rows), which for a
    `tenant_owned` tenant is its own Azure store. The connection row and integration
    profile are control-plane tables that exist only on the platform database, so they are
    read through `platform_session_factory` (defaults to `session_factory`, which is the
    same database for a `platform`-mode tenant)."""
    from src.shared.tenant_schema import schema_for_tenant

    if trigger not in TRIGGERS:
        raise ValueError(f"unknown sync trigger: {trigger}")
    schema = schema_for_tenant(tenant_id)
    run_id = str(uuid.uuid4())
    platform_session_factory = platform_session_factory or session_factory

    async with session_factory() as session:
        await ledger.ensure_sync_tables(session, schema)
        await ledger.record_run_start(
            session, schema, run_id=run_id, tenant_id=tenant_id,
            connection_id=connection_id, trigger=trigger,
        )
        await session.commit()

    async def _finish(outcome, reason="none", seen=0, ingested=0, skipped=0, failed=0):
        async with session_factory() as session:
            await ledger.record_run_finish(
                session, schema, run_id=run_id, outcome=outcome, reason=reason,
                seen=seen, ingested=ingested, skipped=skipped, failed=failed,
            )
            await session.commit()
        _record_metric(trigger, outcome)
        return SyncResult(run_id, outcome, reason, seen, ingested, skipped, failed)

    async with platform_session_factory() as session:
        connection = await _active_blob_connection(session, tenant_id, connection_id)
    if connection is None:
        return await _finish(OUTCOME_BLOCKED, REASON_INACTIVE_CONNECTION)

    if provider is None:
        try:
            provider = get_provider(
                connection_id,
                fallback=lambda: build_live_provider(
                    tenant_id, connection[3], connection[4]
                ),
            )
        except BlobProviderUnavailable:
            return await _finish(OUTCOME_BLOCKED, REASON_PREREQUISITE_MISSING)

    async with platform_session_factory() as session:
        retention = await _profile_retention(session, tenant_id)
    if retention not in SYNC_ALLOWED_RETENTION:
        logger.info(
            "blob_sync_blocked",
            extra={"trigger": trigger, "reason": REASON_PREREQUISITE_MISSING},
        )
        return await _finish(OUTCOME_BLOCKED, REASON_PREREQUISITE_MISSING)

    async with session_factory() as session:
        held = await ledger.acquire_lease(session, schema, connection_id, run_id)
        await session.commit()
    if not held:
        return await _finish(OUTCOME_LEASE_HELD, REASON_LEASE_HELD)

    try:
        try:
            objects = await provider.enumerate_objects(_prefix(connection))
        except BlobProviderUnavailable:
            return await _finish(OUTCOME_BLOCKED, REASON_PREREQUISITE_MISSING)
        except BlobProviderError:
            logger.info(
                "blob_sync_listing_failed", extra={"trigger": trigger}
            )
            return await _finish(OUTCOME_FAILED, REASON_LISTING_FAILED)

        seen = len(objects)
        ingested = skipped = failed = 0
        enumerated = {o.identity for o in objects}
        for obj in objects:
            if not obj.is_supported():
                skipped += 1
                continue
            try:
                created = await _reconcile_object(
                    session_factory, schema, tenant_id, connection_id,
                    obj, provider, make_ingestion_service, temp_store,
                )
            except Exception:
                logger.info("blob_sync_object_failed", extra={"trigger": trigger})
                failed += 1
                continue
            if created:
                ingested += 1
            else:
                skipped += 1

        await _reconcile_absences(session_factory, schema, connection_id, enumerated)
        return await _finish(OUTCOME_SUCCEEDED, REASON_NONE, seen, ingested, skipped, failed)
    finally:
        async with session_factory() as session:
            await ledger.release_lease(session, schema, connection_id, run_id)
            await session.commit()


def _prefix(connection) -> str | None:
    configuration = connection[3] if len(connection) > 3 else None
    if isinstance(configuration, dict):
        prefix = configuration.get("prefix")
        return prefix or None
    return None


async def _reconcile_object(session_factory, schema, tenant_id, connection_id,
                            obj, provider, make_ingestion_service,
                            temp_store) -> bool:
    """Sync one object. Returns True when a new document was ingested."""
    async with session_factory() as session:
        known = await ledger.get_source(session, schema, connection_id, obj.identity)
    if known is not None and known[0] == obj.version and not known[3]:
        return False
    previous_document = known[1] if known is not None else None

    try:
        data = await provider.acquire(obj.identity)
    except BlobObjectMissing:
        return False

    reference = _temp_reference(connection_id, obj.identity)
    staged_reference: str | None = None
    if temp_store is not None:
        # The store mints the reference; the hint above is only a name. A
        # store that retains nothing returns None and the bytes stay in
        # memory for the submitting call.
        staged_reference = temp_store.put(
            tenant_id, reference, data, filename=obj.filename
        )

    def _read() -> bytes:
        if staged_reference is not None:
            reopened = temp_store.open(staged_reference)
            if reopened is not None:
                return reopened
        return data

    try:
        service = make_ingestion_service() if make_ingestion_service else None
        if service is None:
            from src.document_service.ingestion.service import DocumentIngestionService

            service = DocumentIngestionService()
        document = NormalizedDocument(
            tenant_id=tenant_id,
            filename=obj.filename,
            content=ContentAccess(read=_read),
            purpose="query",
            actor=IngestingActor(kind=ActorKind.SOURCE_SYSTEM),
            source=SourceReference(
                source_type=SOURCE_TYPE_AZURE_BLOB,
                source_id=connection_id,
                external_id=obj.identity,
                source_version=obj.version,
                source_modified_at=obj.modified_at,
                origin="pull",
            ),
            acquisition=ContentAcquisition.REOPENABLE,
            declared_media_type=_media_type(obj.filename),
            declared_size=obj.size,
        )
        async with session_factory() as session:
            result = await service.ingest(session, document)

        # Replacement finalization is one transaction: purge the prior
        # document's derived outputs, hide it from retrieval, and relink the
        # ledger to the new document. Retrieval never serves a mix of old and
        # new derived data.
        async with session_factory() as session:
            if previous_document:
                await _purge_document_outputs(session, schema, previous_document)
                await ledger.hide_document(
                    session, schema, document_id=previous_document,
                    connection_id=connection_id, cause=CAUSE_SUPERSEDED,
                )
            await ledger.upsert_source_seen(
                session, schema, connection_id=connection_id,
                identity=obj.identity, version=obj.version,
                document_id=result.document_id,
            )
            await session.commit()
        return True
    finally:
        if staged_reference is not None:
            try:
                temp_store.delete(staged_reference)
            except Exception:
                pass


async def _purge_document_outputs(session, schema: str, document_id: str) -> None:
    await session.execute(
        text(f"DELETE FROM {schema}.document_chunks WHERE document_id = :id"),
        {"id": document_id},
    )
    await session.execute(
        text(f"DELETE FROM {schema}.document_text_spans WHERE document_id = :id"),
        {"id": document_id},
    )


async def _reconcile_absences(session_factory, schema, connection_id,
                              enumerated: set[str]) -> None:
    """Count absences; confirm and hide only at two consecutive sightings."""
    async with session_factory() as session:
        known_identities = await ledger.ledger_identities(session, schema, connection_id)
    for identity in known_identities:
        if identity in enumerated:
            continue
        async with session_factory() as session:
            sightings = await ledger.record_absence(session, schema, connection_id, identity)
            if sightings >= MISSING_CONFIRMATIONS:
                known = await ledger.get_source(session, schema, connection_id, identity)
                await ledger.confirm_missing(session, schema, connection_id, identity)
                if known is not None and known[1]:
                    await ledger.hide_document(
                        session, schema, document_id=known[1],
                        connection_id=connection_id, cause=CAUSE_SOURCE_MISSING,
                    )
            await session.commit()


# --- Manual trigger and safe status ------------------------------------------------------


def trigger_manual_sync(tenant_id: str, connection_id: str) -> dict:
    """Describe the durable task a manual sync enqueues.

    Returns an enqueue descriptor (task name plus identity-only args), not a
    live handle: the caller enqueues it through the broker, which keeps this
    module free of broker configuration. Authorization (tenant admin) is the
    caller's duty; execution re-checks the active connection anyway.
    """
    return {
        "task": "blob_sync_run",
        "args": [tenant_id, connection_id, TRIGGER_MANUAL],
    }


async def read_sync_status(session_factory, schema: str, connection_id: str) -> dict:
    """Latest run as safe classes, identifiers, and correlation timestamps only."""
    async with session_factory() as session:
        # A status read must never fail on a tenant that never synced: the
        # tables may not exist yet, and "never run" is the truthful answer.
        await ledger.ensure_sync_tables(session, schema)
        await session.commit()
        row = (
            await session.execute(
                text(
                    f"SELECT id, trigger, outcome, reason, objects_seen, "
                    f"objects_ingested, objects_skipped, started_at, completed_at "
                    f"FROM {schema}.azure_blob_sync_runs "
                    "WHERE connection_id = :cid ORDER BY started_at DESC LIMIT 1"
                ),
                {"cid": connection_id},
            )
        ).fetchone()
    if row is None:
        return {"connection_id": connection_id, "outcome": "never_run",
                "completed_at": None}
    return {
        "run_id": row[0],
        "connection_id": connection_id,
        "trigger": row[1],
        "outcome": row[2],
        "reason": row[3],
        "objects_seen": row[4],
        "objects_ingested": row[5],
        "objects_skipped": row[6],
        "started_at": row[7].isoformat() if row[7] is not None else None,
        "completed_at": row[8].isoformat() if row[8] is not None else None,
    }


def _record_metric(trigger: str, outcome: str) -> None:
    try:
        from src.shared.observability.domain_metrics import record_blob_sync

        record_blob_sync(trigger=trigger, outcome=outcome)
    except Exception:
        pass
