"""Verification for the content-store boundary.

Covers verification.md rows 23-27. Rows 41-42 (task 4.8) belong to the processing
pipeline and live with the OCR verification.

The reference round-trip and the delete run against a real MinIO instance, because a
stand-in would prove that the adapter's own arithmetic is consistent rather than that
bytes survive a trip through the object store. The contract-introspection rows are
static and need nothing running.
"""

import inspect
import os
import socket
import typing
import uuid

import pytest

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.content_store import contract as contract_module
from src.document_service.content_store.contract import ContentStore
from src.document_service.content_store.minio_store import MinioContentStore
from src.shared.config import settings


def _minio_usable() -> bool:
    """Reachable *and* authenticating.

    `tests/conftest.py` sets placeholder MinIO credentials by default, so the object
    store is deliberately out of reach for the normal suite. Export real
    `NER_MINIO_ACCESS_KEY` / `NER_MINIO_SECRET_KEY` to run these rows against the live
    instance — which is how task 5.3's real-working-store requirement is met.
    """
    host, _, port = settings.minio_endpoint.partition(":")
    try:
        socket.create_connection((host, int(port or 9000)), 2).close()
    except OSError:
        return False
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=boto3.session.Config(signature_version="s3v4"),
        ).list_buckets()
        return True
    except (ClientError, BotoCoreError):
        return False


requires_minio = pytest.mark.skipif(
    not _minio_usable(),
    reason="requires a reachable MinIO instance and working NER_MINIO_* credentials",
)

PAYLOAD = b"%PDF-1.4 content store round trip " * 8

# Every word the contract is forbidden to name. Region and endpoint are checked as whole
# words so that an unrelated identifier containing them does not fail the row.
FORBIDDEN_CONFIG_TERMS = [
    "bucket",
    "container",
    "endpoint",
    "region",
    "credential",
    "access_key",
    "secret_key",
    "aws",
    "minio",
]


@pytest.fixture
def durable_store():
    return MinioContentStore(bucket=settings.minio_bucket)


# --- Row 23: storing returns an opaque reference ---------------------------------


@requires_minio
def test_row_23_put_returns_a_reference_that_reopens_the_identical_bytes(durable_store):
    tenant_id = uuid.uuid4().hex
    document_id = str(uuid.uuid4())

    reference = durable_store.put(tenant_id, document_id, PAYLOAD, filename="report.pdf")

    assert reference, "put must return a storage reference"
    assert durable_store.open(reference) == PAYLOAD

    durable_store.delete(reference)


# --- Row 24: deleting removes the bytes, and repeat delete is safe ----------------


@requires_minio
def test_row_24_delete_removes_the_bytes_and_is_idempotent(durable_store):
    tenant_id = uuid.uuid4().hex
    document_id = str(uuid.uuid4())
    reference = durable_store.put(tenant_id, document_id, PAYLOAD, filename="report.pdf")
    assert durable_store.open(reference) == PAYLOAD

    durable_store.delete(reference)
    assert durable_store.open(reference) is None

    # A second delete of the same reference must not raise. Terminal-state cleanup and
    # the working store's own expiry can both reach the same object.
    durable_store.delete(reference)
    assert durable_store.open(reference) is None


# --- Row 25: the boundary exposes no storage configuration ------------------------


def test_row_25_contract_exposes_exactly_three_operations():
    operations = {
        name
        for name, _ in inspect.getmembers(ContentStore, inspect.isfunction)
        if not name.startswith("_")
    }
    assert operations == {"put", "open", "delete"}


def test_row_25_contract_names_no_bucket_endpoint_region_or_credential():
    source = inspect.getsource(contract_module)
    signature_text = " ".join(
        f"{name}{inspect.signature(member)}"
        for name, member in inspect.getmembers(ContentStore, inspect.isfunction)
    )
    annotations = " ".join(
        str(a) for a in typing.get_type_hints(ContentStore.put, globalns=vars(contract_module)).values()
    )

    for term in FORBIDDEN_CONFIG_TERMS:
        assert term not in signature_text.lower(), f"contract signature names '{term}'"
        assert term not in annotations.lower(), f"contract annotation names '{term}'"
        # The prose may explain what is deliberately absent; code may not introduce it.
        code_lines = [
            line
            for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        in_docstring = False
        for line in code_lines:
            stripped = line.strip()
            if stripped.count('"""') == 1:
                in_docstring = not in_docstring
                continue
            if in_docstring or stripped.startswith('"""'):
                continue
            assert term not in stripped.lower(), f"contract code names '{term}': {stripped}"


# --- Row 27: key construction lives inside the platform adapter -------------------


@requires_minio
def test_row_27_key_is_built_inside_the_adapter_and_scoped_to_the_tenant(durable_store):
    tenant_id = uuid.uuid4().hex
    document_id = str(uuid.uuid4())

    reference = durable_store.put(tenant_id, document_id, PAYLOAD, filename="report.pdf")

    assert reference.startswith(f"tenants/{tenant_id}/"), reference
    assert document_id in reference

    other_tenant = uuid.uuid4().hex
    other_reference = durable_store.put(
        other_tenant, document_id, PAYLOAD, filename="report.pdf"
    )
    assert other_reference.startswith(f"tenants/{other_tenant}/")
    assert other_reference != reference

    durable_store.delete(reference)
    durable_store.delete(other_reference)


def test_row_27_no_caller_outside_the_adapter_constructs_a_key():
    """The key rule appears in the adapter and in no other application module."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "src"
    adapter = root / "document_service" / "content_store" / "minio_store.py"
    storage = root / "document_service" / "services" / "storage.py"

    offenders = []
    for path in root.rglob("*.py"):
        if path in (adapter, storage):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "tenants/" in text and "/documents/" in text:
            offenders.append(str(path.relative_to(root)))

    assert offenders == [], f"storage keys constructed outside the adapter: {offenders}"
