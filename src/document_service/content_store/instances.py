"""The two configured content-store instances.

Durable and working are the same adapter with different lifetime policy — that is the
whole difference, which is why they are two instances rather than two boundaries.
Both are constructed lazily and cached, because constructing one reaches the object
store to ensure its bucket.
"""

from src.document_service.content_store.contract import ContentStore
from src.document_service.content_store.minio_store import MinioContentStore
from src.shared.config import settings

_durable: ContentStore | None = None
_working: ContentStore | None = None


def get_durable_store() -> ContentStore:
    """Where an original is kept for the life of the document, under `platform_blob`."""
    global _durable
    if _durable is None:
        _durable = MinioContentStore(bucket=settings.minio_bucket)
    return _durable


def get_working_store() -> ContentStore:
    """Where an `ephemeral` document's bytes live only until processing terminates.

    A separate bucket, not a prefix, so the expiry rule applies to working copies and
    nothing else. The expiry is the tenant's privacy guarantee, so it is enforced by the
    object store rather than by this application reaching a terminal state.
    """
    global _working
    if _working is None:
        _working = MinioContentStore(
            bucket=settings.minio_working_bucket,
            expiry_days=settings.working_copy_expiry_days,
        )
    return _working


def reset_stores() -> None:
    """Drop the cached instances. For tests that reconfigure the buckets."""
    global _durable, _working
    _durable = None
    _working = None
