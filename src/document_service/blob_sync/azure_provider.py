"""SDK-backed Azure Blob provider (CAP-3, ADR-012).

Replaces `DeferredLiveProvider` for a connection whose configuration and
resolved connection string are available. Bound to one connection's
container at construction time; every SDK call and credential stays behind
this module, exactly like `DeferredLiveProvider` and `FixtureBlobProvider`
before it — `run_sync` never sees a container client or a connection string.
"""

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient

from src.document_service.blob_sync.provider import (
    BlobListingFailed,
    BlobObject,
    BlobObjectMissing,
    BlobProvider,
    BlobProviderError,
)


class AzureBlobLiveProvider(BlobProvider):
    """One tenant connection's live Azure Blob container, via the SDK."""

    name = "azure_blob_live_sdk"

    def __init__(self, connection_string: str, container: str):
        self._connection_string = connection_string
        self._container = container

    async def enumerate_objects(self, prefix: str | None = None) -> list[BlobObject]:
        try:
            async with BlobServiceClient.from_connection_string(
                self._connection_string
            ) as service:
                container_client = service.get_container_client(self._container)
                objects = []
                async for item in container_client.list_blobs(name_starts_with=prefix):
                    objects.append(
                        BlobObject(
                            identity=item.name,
                            version=(item.etag or "").strip('"'),
                            filename=item.name.rsplit("/", 1)[-1],
                            size=item.size or 0,
                            modified_at=item.last_modified,
                        )
                    )
                return objects
        except AzureError as exc:
            raise BlobListingFailed(type(exc).__name__) from None

    async def acquire(self, identity: str) -> bytes:
        try:
            async with BlobServiceClient.from_connection_string(
                self._connection_string
            ) as service:
                blob_client = service.get_blob_client(self._container, identity)
                downloader = await blob_client.download_blob()
                return await downloader.readall()
        except ResourceNotFoundError:
            raise BlobObjectMissing(identity) from None
        except AzureError as exc:
            raise BlobProviderError(type(exc).__name__) from None
