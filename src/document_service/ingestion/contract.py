"""The normalized document every source adapter submits.

Nothing here names HTTP, multipart, an object-storage client, a provider API, or a
credential. That is the point: an adapter translates whatever its source speaks into
these types, and the ingestion operation never learns which adapter called it.

Retention is conspicuously not a field. An adapter declares how its content can be
acquired; the tenant's integration profile decides what is kept. Letting a source assert
its own retention would put the tenant's privacy guarantee in the hands of the component
least able to honour it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Mapping

# Re-exported so an adapter reads one contract module. Defined in
# `src.shared.document_retention`, which the processing worker also imports.
from src.shared.document_retention import (  # noqa: F401
    RETENTION_EPHEMERAL,
    RETENTION_MODES,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)

# --- The reserved platform-upload source ----------------------------------------------

SOURCE_TYPE_PLATFORM_UPLOAD = "platform_upload"

# Identical for every tenant, stable for the life of a tenant, and never issued to a
# configured document source. A generated per-tenant identifier would need a table, a
# backfill, and a lookup on every upload to express a fact that is constant.
PLATFORM_UPLOAD_SOURCE_ID = "platform-upload"
RESERVED_SOURCE_IDS = frozenset({PLATFORM_UPLOAD_SOURCE_ID})

ORIGIN_PUSH = "push"
ORIGIN_PULL = "pull"


class ContentAcquisition(str, Enum):
    """Whether the source can be asked for the same bytes again."""

    # The bytes exist only for the duration of the submitting call. A browser upload is
    # this: once the HTTP request ends there is no one left to ask.
    SINGLE_USE = "single_use"
    # The adapter can be asked again after the submitting call has ended.
    REOPENABLE = "reopenable"


class ActorKind(str, Enum):
    HUMAN = "human"
    SOURCE_SYSTEM = "source_system"


@dataclass(frozen=True)
class IngestingActor:
    kind: ActorKind
    # The platform user id for a human; None for a source system.
    user_id: str | None = None


@dataclass(frozen=True)
class SourceReference:
    """Where this document came from, in the source's own terms.

    Timestamps are never synthesised. A source that supplies no modified time leaves it
    None, and it is stored as NULL rather than backfilled with the ingestion time — a
    fabricated timestamp is indistinguishable from a real one to every later reader.
    """

    source_type: str
    source_id: str
    external_id: str | None = None
    source_version: str | None = None
    source_created_at: datetime | None = None
    source_modified_at: datetime | None = None
    # Opaque to the platform. Never consulted for tenant identity or retention.
    metadata: Mapping[str, Any] | None = None
    origin: str = ORIGIN_PUSH


@dataclass(frozen=True)
class ContentAccess:
    """How the ingestion operation obtains the bytes it is to store and checksum."""

    read: Callable[[], bytes]

    @classmethod
    def from_bytes(cls, data: bytes) -> "ContentAccess":
        return cls(read=lambda: data)


@dataclass(frozen=True)
class NormalizedDocument:
    # Taken from authenticated context by the adapter's caller. A tenant identifier
    # appearing in `source.metadata` has no effect on where this document is written.
    tenant_id: str
    filename: str
    content: ContentAccess
    purpose: str
    actor: IngestingActor
    source: SourceReference
    acquisition: ContentAcquisition
    # What the source claims the bytes are. Advisory: the platform still computes its own
    # checksum, and media-type resolution falls back to the filename and then a sniff.
    declared_media_type: str | None = None
    declared_size: int | None = None


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    checksum: str
    file_size: int
    retention_mode: str
    storage_reference: str | None
    duplicate_of: str | None
    content_store_kind: str | None = field(default=None)


def assert_source_id_available(source_id: str) -> None:
    """Refuse a configured source that tries to claim a reserved identifier.

    Called by whatever registers a document source. No pull source exists yet, so today
    the only caller is integration-profile validation — but the reservation has to be
    enforceable from the moment the literal is written, or the first real source will
    find it already in use in some tenant's data.
    """
    from src.document_service.ingestion.errors import ReservedSourceId

    if source_id in RESERVED_SOURCE_IDS:
        raise ReservedSourceId(source_id)
