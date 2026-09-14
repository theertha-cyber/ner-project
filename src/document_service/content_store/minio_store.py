"""The platform's default content store, over the existing MinIO client."""

from src.document_service.content_store.contract import StorageReference
from src.document_service.services.storage import MinioStorageClient


def _extension(filename: str) -> str:
    """The key's trailing extension. Local to the adapter rather than imported from the
    OCR worker, so that the worker can depend on this package without a cycle."""
    dot = filename.rfind(".")
    return "" if dot == -1 else filename[dot + 1:].lower()


class MinioContentStore:
    """Key construction lives here and nowhere else.

    The key shape is the one uploads have always used, so objects written before this
    boundary existed still resolve through it. That it happens to end in a file
    extension is an artefact of the historical layout, not information any caller may
    read back: the extractor is chosen from the document's resolved media type.
    """

    kind = "platform_minio"

    def __init__(self, bucket: str | None = None, expiry_days: int | None = None):
        self._client = MinioStorageClient(bucket=bucket)
        if expiry_days is not None:
            self._client.set_expiry_days(expiry_days)

    def put(
        self,
        tenant_id: str,
        document_id: str,
        data: bytes,
        filename: str | None = None,
    ) -> StorageReference | None:
        return self._client.upload_file(
            tenant_id, document_id, _extension(filename or ""), data
        )

    def open(self, reference: StorageReference) -> bytes | None:
        if not reference:
            return None
        return self._client.get_file(reference)

    def delete(self, reference: StorageReference) -> None:
        # Idempotent by construction: S3 DELETE on an absent key succeeds, and the
        # client swallows the error class that would arise if it did not.
        if not reference:
            return
        self._client.delete_file(reference)
