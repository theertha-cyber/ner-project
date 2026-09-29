"""Platform MinIO layout for uploaded tabular files (ADR-019).

Every key is built here, and only from server-issued identifiers: the tenant id
from the authenticated context, a server-generated file UUID and an integer
version. Nothing a request body, file name or model output carries ever reaches
a key. Follows `src/document_service/services/storage.py` for the client setup.
"""

from __future__ import annotations

import re
import uuid

import boto3
from botocore.exceptions import ClientError

from src.shared.config import settings

_TENANT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SOURCE_EXTENSIONS = ("csv", "xlsx")


def _check_ids(tenant_id: str, file_id: str, version: int | None = None) -> None:
    if not isinstance(tenant_id, str) or not _TENANT_RE.match(tenant_id):
        raise ValueError("unsafe tenant id")
    uuid.UUID(str(file_id))
    if version is not None and (not isinstance(version, int) or isinstance(version, bool) or version < 1):
        raise ValueError("unsafe version")


def file_prefix(tenant_id: str, file_id: str) -> str:
    _check_ids(tenant_id, file_id)
    return f"tenants/{tenant_id}/tabular/{file_id}/"


def version_prefix(tenant_id: str, file_id: str, version: int) -> str:
    _check_ids(tenant_id, file_id, version)
    return f"tenants/{tenant_id}/tabular/{file_id}/v{version}/"


def original_key(tenant_id: str, file_id: str, version: int, extension: str) -> str:
    if extension not in SOURCE_EXTENSIONS:
        raise ValueError("unsupported extension")
    return f"{version_prefix(tenant_id, file_id, version)}original.{extension}"


def parquet_key(tenant_id: str, file_id: str, version: int) -> str:
    return f"{version_prefix(tenant_id, file_id, version)}data.parquet"


class TabularObjectStore:
    """Thin boto3 wrapper; every method takes an already-built key from the
    helpers above, never a caller-composed string."""

    def __init__(self, client=None, bucket: str | None = None):
        self.client = client or boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=boto3.session.Config(signature_version="s3v4"),
        )
        self.bucket = bucket or settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put_file(self, key: str, local_path: str) -> None:
        with open(local_path, "rb") as fh:
            self.client.upload_fileobj(fh, self.bucket, key)

    def download_to(self, key: str, local_path: str) -> None:
        with open(local_path, "wb") as fh:
            self.client.download_fileobj(self.bucket, key, fh)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        token = None
        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            page = self.client.list_objects_v2(**kwargs)
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
            if not page.get("IsTruncated"):
                return keys
            token = page.get("NextContinuationToken")

    def delete_prefix(self, prefix: str) -> int:
        """Removes every object under one server-built prefix; returns the count."""
        if not prefix.startswith("tenants/") or "/tabular/" not in prefix or not prefix.endswith("/"):
            raise ValueError("refusing to delete outside a tabular prefix")
        keys = self.list_keys(prefix)
        for start in range(0, len(keys), 1000):
            batch = keys[start:start + 1000]
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
        return len(keys)
