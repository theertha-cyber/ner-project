import os
import tempfile
import boto3
from botocore.config import Config as BotoConfig
from src.shared.config import settings


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
    )


def download_model_artifacts(tenant_id: str, version_number: int) -> str:
    artifact_path = f"tenants/{tenant_id}/models/v{version_number}/"
    s3 = _get_s3_client()
    bucket = settings.minio_bucket

    local_dir = tempfile.mkdtemp(prefix=f"model_{tenant_id}_v{version_number}_")

    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=artifact_path)
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                relative_path = os.path.relpath(key, artifact_path)
                local_path = os.path.join(local_dir, relative_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                s3.download_file(bucket, key, local_path)
    except Exception:
        import shutil
        shutil.rmtree(local_dir, ignore_errors=True)
        raise

    return local_dir


def estimate_model_memory(local_dir: str) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(local_dir):
        for f in filenames:
            filepath = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(filepath)
            except OSError:
                pass
    return total
