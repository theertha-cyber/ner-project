"""The application-owned boundary for a document's bytes.

Three operations and nothing else. Deliberately absent from every signature and every
type here: bucket, container, endpoint, region, credential, and the rule by which a
key is built. A caller holds a `StorageReference` and may do exactly two things with
it — open it and delete it. Deriving a file extension, a media type, a tenant, or a
document id from one is prohibited; the reference is opaque outside the store that
produced it.
"""

from typing import Protocol, runtime_checkable

# Opaque to every caller. Named `storage_reference` in the application contract; the
# existing `blob_path` column is only the physical place it is persisted, until the
# named `document-metadata-column-reconciliation` change renames that column.
StorageReference = str


@runtime_checkable
class ContentStore(Protocol):
    def put(
        self,
        tenant_id: str,
        document_id: str,
        data: bytes,
        filename: str | None = None,
    ) -> StorageReference | None:
        """Store bytes and return the reference by which they can be reopened.

        `filename` is a naming hint the store may use or ignore; it is not part of the
        reference's meaning and no caller may read it back out of the returned value.
        Returning None is a valid outcome: a store that retains nothing has nothing to
        hand back, and the document then carries no reference.
        """
        ...

    def open(self, reference: StorageReference) -> bytes | None:
        """Return the bytes at a previously returned reference, or None if they are gone."""
        ...

    def delete(self, reference: StorageReference) -> None:
        """Remove the bytes at a reference. Safe to call again with the same reference."""
        ...
