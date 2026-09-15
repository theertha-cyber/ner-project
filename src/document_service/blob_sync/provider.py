"""Contained Azure Blob provider runtime (CAP-3, ADR-012).

Every Azure SDK call this feature will ever make lives behind `BlobProvider`.
Nothing outside this module names a container client, a credential, or a
provider diagnostic: enumeration yields opaque identities and versions, byte
acquisition yields bytes, and every failure surfaces as a finite reason class.

Live Azure verification is deferred per run provisioning (no approved test
storage account), so the shipped default is `DeferredLiveProvider`, which
refuses every call with `prerequisite_missing` and keeps the capability
inactive. Tests register `FixtureBlobProvider` — the same seam production
uses, backed by in-memory objects instead of SDK calls.
"""

from dataclasses import dataclass, field
from datetime import datetime


# --- Finite provider failure classes ---------------------------------------------------

REASON_LISTING_FAILED = "listing_failed"
REASON_OBJECT_MISSING = "object_missing"
REASON_PREREQUISITE_MISSING = "prerequisite_missing"
REASON_ACQUIRE_FAILED = "acquire_failed"

PROVIDER_REASONS = frozenset({
    REASON_LISTING_FAILED,
    REASON_OBJECT_MISSING,
    REASON_PREREQUISITE_MISSING,
    REASON_ACQUIRE_FAILED,
})


class BlobProviderError(Exception):
    """Base for every provider failure. Carries a finite reason, never a payload."""

    reason = REASON_ACQUIRE_FAILED


class BlobListingFailed(BlobProviderError):
    reason = REASON_LISTING_FAILED


class BlobObjectMissing(BlobProviderError):
    reason = REASON_OBJECT_MISSING


class BlobProviderUnavailable(BlobProviderError):
    reason = REASON_PREREQUISITE_MISSING


# --- Object identity -------------------------------------------------------------------

SUPPORTED_SUFFIXES = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".doc", ".docx"})


@dataclass(frozen=True)
class BlobObject:
    """One enumerable source object, in the source's own terms.

    `identity` is opaque to the platform (a blob name today, never parsed);
    `version` is the source's version token (an etag today, compared, never
    interpreted). Timestamps are supplied only when the source provides them.
    """

    identity: str
    version: str
    filename: str
    size: int = 0
    modified_at: datetime | None = None
    metadata: dict | None = None

    def is_supported(self) -> bool:
        dot = self.filename.rfind(".")
        suffix = self.filename[dot:].lower() if dot != -1 else ""
        return suffix in SUPPORTED_SUFFIXES


class BlobProvider:
    """The seam every sync operation programs against. Subclass, do not branch."""

    name = "base"

    async def enumerate_objects(self, prefix: str | None = None) -> list[BlobObject]:
        raise NotImplementedError

    async def acquire(self, identity: str) -> bytes:
        raise NotImplementedError


class DeferredLiveProvider(BlobProvider):
    """Shipped default until approved Azure resources and activation exist.

    Refuses every call with `prerequisite_missing` so the capability stays
    inactive rather than half-working. The SDK-backed implementation will
    replace this class, not the callers.
    """

    name = "azure_blob_live"

    async def enumerate_objects(self, prefix: str | None = None) -> list[BlobObject]:
        raise BlobProviderUnavailable(
            "live Azure Blob is not configured for this tenant"
        )

    async def acquire(self, identity: str) -> bytes:
        raise BlobProviderUnavailable(
            "live Azure Blob is not configured for this tenant"
        )


class FixtureBlobProvider(BlobProvider):
    """In-memory provider for verification. Same seam, no SDK, no network."""

    name = "fixture"

    def __init__(self, objects: list[BlobObject] | None = None, blobs: dict[str, bytes] | None = None):
        self._objects: dict[str, BlobObject] = {o.identity: o for o in (objects or [])}
        self._blobs: dict[str, bytes] = dict(blobs or {})
        self.enumerations = 0
        self.acquisitions: list[str] = []
        self.fail_listing = False

    def put(self, obj: BlobObject, data: bytes) -> None:
        self._objects[obj.identity] = obj
        self._blobs[obj.identity] = data

    def remove(self, identity: str) -> None:
        self._objects.pop(identity, None)
        self._blobs.pop(identity, None)

    async def enumerate_objects(self, prefix: str | None = None) -> list[BlobObject]:
        self.enumerations += 1
        if self.fail_listing:
            raise BlobListingFailed("fixture listing failure")
        objects = list(self._objects.values())
        if prefix:
            objects = [o for o in objects if o.identity.startswith(prefix)]
        return objects

    async def acquire(self, identity: str) -> bytes:
        self.acquisitions.append(identity)
        try:
            return self._blobs[identity]
        except KeyError:
            raise BlobObjectMissing(identity) from None


_PROVIDERS: dict[str, BlobProvider] = {}
_DEFAULT = DeferredLiveProvider()


def register_provider(key: str, provider: BlobProvider) -> None:
    """Bind a provider instance to a connection id (tests) or `default` (workers)."""
    _PROVIDERS[key] = provider


def reset_providers() -> None:
    _PROVIDERS.clear()


def get_provider(key: str | None = None, fallback=None) -> BlobProvider:
    """Look up a bound provider; when none is registered, call `fallback` if
    supplied instead of returning the always-refusing default. Existing
    callers that omit `fallback` keep today's behavior exactly."""
    if key is not None and key in _PROVIDERS:
        return _PROVIDERS[key]
    if "default" in _PROVIDERS:
        return _PROVIDERS["default"]
    if fallback is not None:
        return fallback()
    return _DEFAULT
