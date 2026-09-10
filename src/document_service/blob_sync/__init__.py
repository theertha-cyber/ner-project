"""Durable Azure Blob synchronization runtime (CAP-3, ADR-012).

One tenant-bound durable job serves manual, scheduled, retry, and catch-up
triggers. Azure SDK knowledge is contained in `provider.py`; idempotency lives
in the tenant-schema ledger in `ledger.py`; the use case in `sync.py` submits
every eligible object as a `NormalizedDocument` through the common ingestion
pipeline and never retains Blob originals.
"""

from src.document_service.blob_sync.ledger import (
    HIDDEN_TABLE_DDL,
    LEASE_TTL_SECONDS,
    RUNS_TABLE_DDL,
    SOURCES_TABLE_DDL,
    SYNC_TABLES_DDL,
    SYNC_TABLES,
    ensure_sync_tables,
)
from src.document_service.blob_sync.provider import (
    BlobListingFailed,
    BlobObject,
    BlobObjectMissing,
    BlobProvider,
    BlobProviderError,
    BlobProviderUnavailable,
    DeferredLiveProvider,
    FixtureBlobProvider,
    get_provider,
    register_provider,
    reset_providers,
)
from src.document_service.blob_sync.scheduler import (
    CATCHUP_AFTER_CADENCES,
    SYNC_CADENCE_MINUTES,
    ScheduleDecision,
    evaluate_connection,
)
from src.document_service.blob_sync.sync import (
    OUTCOMES,
    TRIGGER_CATCHUP,
    TRIGGER_MANUAL,
    TRIGGER_RETRY,
    TRIGGER_SCHEDULED,
    TRIGGERS,
    SyncResult,
    read_sync_status,
    run_sync,
    trigger_manual_sync,
)

__all__ = [
    "HIDDEN_TABLE_DDL",
    "SYNC_TABLES",
    "SYNC_TABLES_DDL",
    "SOURCES_TABLE_DDL",
    "RUNS_TABLE_DDL",
    "LEASE_TTL_SECONDS",
    "ensure_sync_tables",
    "BlobListingFailed",
    "BlobObject",
    "BlobObjectMissing",
    "BlobProvider",
    "BlobProviderError",
    "BlobProviderUnavailable",
    "DeferredLiveProvider",
    "FixtureBlobProvider",
    "get_provider",
    "register_provider",
    "reset_providers",
    "CATCHUP_AFTER_CADENCES",
    "SYNC_CADENCE_MINUTES",
    "ScheduleDecision",
    "evaluate_connection",
    "OUTCOMES",
    "TRIGGER_CATCHUP",
    "TRIGGER_MANUAL",
    "TRIGGER_RETRY",
    "TRIGGER_SCHEDULED",
    "TRIGGERS",
    "SyncResult",
    "read_sync_status",
    "run_sync",
    "trigger_manual_sync",
]
