import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, EndpointConnectionError
from src.shared.config import settings
from src.document_service.services.storage import MinioStorageClient


def _client_error():
    return ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")


def test_ensure_bucket_retries_then_succeeds_on_transient_endpoint_error(monkeypatch):
    monkeypatch.setattr(settings, "retry_initial_delay_seconds", 0.02)
    monkeypatch.setattr(settings, "retry_backoff_multiplier", 2.0)
    monkeypatch.setattr(settings, "retry_max_delay_seconds", 0.05)
    monkeypatch.setattr(settings, "retry_max_total_seconds", 5.0)

    call_count = {"n": 0}

    def head_bucket(Bucket):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise EndpointConnectionError(endpoint_url="http://minio:9000")
        return {}

    mock_boto_client = MagicMock()
    mock_boto_client.head_bucket.side_effect = head_bucket

    with patch("boto3.client", return_value=mock_boto_client):
        client = MinioStorageClient()

    assert call_count["n"] == 3
    assert client.client is mock_boto_client


def test_ensure_bucket_creates_bucket_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "retry_initial_delay_seconds", 0.02)
    monkeypatch.setattr(settings, "retry_max_delay_seconds", 0.05)
    monkeypatch.setattr(settings, "retry_max_total_seconds", 5.0)

    mock_boto_client = MagicMock()
    mock_boto_client.head_bucket.side_effect = _client_error()

    with patch("boto3.client", return_value=mock_boto_client):
        MinioStorageClient()

    mock_boto_client.create_bucket.assert_called_once()


def test_ensure_bucket_raises_after_retry_bound_exhausted(monkeypatch):
    monkeypatch.setattr(settings, "retry_initial_delay_seconds", 0.02)
    monkeypatch.setattr(settings, "retry_max_delay_seconds", 0.05)
    monkeypatch.setattr(settings, "retry_max_total_seconds", 0.2)

    mock_boto_client = MagicMock()
    mock_boto_client.head_bucket.side_effect = _client_error()
    mock_boto_client.create_bucket.side_effect = _client_error()

    with patch("boto3.client", return_value=mock_boto_client):
        with pytest.raises(ClientError):
            MinioStorageClient()
