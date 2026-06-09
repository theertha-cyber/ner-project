import io
import boto3
from botocore.exceptions import ClientError
from src.shared.config import settings


class MinioStorageClient:
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=boto3.session.Config(signature_version="s3v4"),
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def upload_file(self, tenant_id: str, document_id: str, extension: str, data: bytes) -> str:
        object_key = f"tenants/{tenant_id}/documents/{document_id}.{extension}"
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=data)
        return object_key

    def get_file(self, object_key: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            return response["Body"].read()
        except ClientError:
            return None

    def delete_file(self, object_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=object_key)
            return True
        except ClientError:
            return False
