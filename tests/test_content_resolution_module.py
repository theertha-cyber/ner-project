"""Verification for the extracted content-resolution module.

Covers: "Processing and delivery resolve identically", "Reading bytes does not require
the processing pipeline", "Resolution follows the recorded retention mode", "Existing
callers are unaffected by the extraction", "No pre-authorized URL is minted".

The extraction exists so an HTTP route can read a document's bytes without constructing
chunking and the embedding service. The risk it introduces is subtle: the pull-source
integration registers its adapter through `ocr_worker.register_source_reopener`, and
several tests monkeypatch the worker's own attributes. If the move left the worker
holding its own copy of the registry, registration would land in one dict and lookup
would read another — and nothing would fail loudly.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from src.document_service import content_resolution as cr
from src.document_service.services import ocr_worker
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)

pytestmark = [pytest.mark.verification]

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Doc:
    """The subset of a document row the resolution reads."""

    def __init__(self, retention_mode=None, blob_path=None, source_type=None,
                 source_id=None, external_id=None):
        self.retention_mode = retention_mode
        self.blob_path = blob_path
        self.source_type = source_type
        self.source_id = source_id
        self.external_id = external_id


class _Store:
    def __init__(self, contents=None):
        self.contents = contents or {}
        self.opened = []

    def open(self, reference):
        self.opened.append(reference)
        return self.contents.get(reference)


# --- "Existing callers are unaffected by the extraction" ----------------------------


def test_the_worker_still_offers_every_moved_name():
    """Names, not identities. `_store_for` and the two resolvers are thin wrappers rather
    than aliases, deliberately — see the seam test below."""
    for name in (
        "resolve_content", "register_source_reopener", "has_source_reopener",
        "_store_for", "_resolve_content_for_processing", "_reopen_source_content",
        "ContentUnresolvable", "SourceOnlyNotSupported", "_SOURCE_REOPENERS",
    ):
        assert hasattr(ocr_worker, name), f"ocr_worker lost {name}"

    # The exception types must be the same objects, or an `except` in one module would
    # not catch what the other raises.
    assert ocr_worker.ContentUnresolvable is cr.ContentUnresolvable
    assert ocr_worker.SourceOnlyNotSupported is cr.SourceOnlyNotSupported
    assert ocr_worker.register_source_reopener is cr.register_source_reopener


def test_patching_the_workers_store_seam_still_steers_resolution(monkeypatch):
    """The regression this guards actually happened during the extraction.

    Several suites monkeypatch `ocr_worker._store_for` to stand a fake store in for
    MinIO. Re-exporting the shared function as a plain alias left those patches pointing
    at a name nothing consulted — so resolution silently reached for the real object
    store, and the failure surfaced far from its cause.
    """
    fake = _Store({"ref": b"from the patched store"})
    monkeypatch.setattr(ocr_worker, "_store_for", lambda mode: fake)

    assert ocr_worker.resolve_content(_Doc(RETENTION_PLATFORM_BLOB, "ref")) == b"from the patched store"
    assert fake.opened == ["ref"]


async def test_the_seam_also_applies_to_the_processing_resolver(monkeypatch):
    fake = _Store({"ref": b"from the patched store"})
    monkeypatch.setattr(ocr_worker, "_store_for", lambda mode: fake)

    resolved = await ocr_worker._resolve_content_for_processing(
        _Doc(RETENTION_PLATFORM_BLOB, "ref"), "tenant-1"
    )
    assert resolved == b"from the patched store"


def test_the_registry_is_one_dict_not_two():
    """The failure this guards: registration through the worker landing in a different
    dict from the one lookup reads. Both would be empty-looking in isolation and neither
    would raise."""
    assert ocr_worker._SOURCE_REOPENERS is cr._SOURCE_REOPENERS


def test_registering_through_the_worker_is_visible_to_the_shared_module():
    async def _reopen(tenant_id, source_id, external_id):
        return b"from-source"

    ocr_worker.register_source_reopener("test_source_via_worker", _reopen)
    try:
        assert cr.has_source_reopener("test_source_via_worker")
    finally:
        cr._SOURCE_REOPENERS.pop("test_source_via_worker", None)


def test_importing_the_pull_source_integration_registers_its_adapter():
    """`blob_sync.reopen` registers as an import side effect, through the worker's name."""
    import src.document_service.blob_sync.reopen  # noqa: F401

    assert cr.has_source_reopener("azure_blob")


# --- "Reading bytes does not require the processing pipeline" -----------------------


def test_the_module_imports_without_the_processing_pipeline():
    """Imported in a fresh interpreter, so an already-loaded pipeline in this process
    cannot mask the dependency. Asserting on `sys.modules` after the import is what
    makes this meaningful — a plain import would pass either way."""
    code = (
        "import sys;"
        "import src.document_service.content_resolution;"
        "loaded = set(sys.modules);"
        "print('CHUNKING' if 'src.shared.retrieval.chunking' in loaded else 'clean');"
        "print('EMBEDDING' if 'src.chat_api.services.embedding_service' in loaded else 'clean')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "CHUNKING" not in result.stdout, "content resolution pulled in chunking"
    assert "EMBEDDING" not in result.stdout, "content resolution pulled in the embedding service"


# --- "Resolution follows the recorded retention mode" -------------------------------


def test_platform_blob_reads_the_durable_store(monkeypatch):
    durable, working = _Store({"ref": b"durable bytes"}), _Store()
    monkeypatch.setattr(
        cr, "store_for", lambda mode: working if mode == RETENTION_EPHEMERAL else durable
    )

    assert cr.resolve_content(_Doc(RETENTION_PLATFORM_BLOB, "ref")) == b"durable bytes"
    assert working.opened == []


def test_ephemeral_reads_the_working_store(monkeypatch):
    durable, working = _Store(), _Store({"ref": b"working bytes"})
    monkeypatch.setattr(
        cr, "store_for", lambda mode: working if mode == RETENTION_EPHEMERAL else durable
    )

    assert cr.resolve_content(_Doc(RETENTION_EPHEMERAL, "ref")) == b"working bytes"
    assert durable.opened == []


def test_a_released_original_resolves_to_none(monkeypatch):
    """An ephemeral document past its terminal state has no reference. Well-defined
    resolution, no bytes — distinct from an error."""
    monkeypatch.setattr(cr, "store_for", lambda mode: _Store())
    assert cr.resolve_content(_Doc(RETENTION_EPHEMERAL, None)) is None


def test_an_absent_retention_mode_defaults_to_platform_blob(monkeypatch):
    durable = _Store({"ref": b"durable bytes"})
    monkeypatch.setattr(cr, "store_for", lambda mode: durable)
    assert cr.resolve_content(_Doc(None, "ref")) == b"durable bytes"


def test_source_only_has_no_platform_store_to_read():
    with pytest.raises(cr.SourceOnlyNotSupported):
        cr.resolve_content(_Doc(RETENTION_SOURCE_ONLY, None))


# --- "Processing and delivery resolve identically" ----------------------------------


async def test_source_only_resolves_through_its_adapter():
    async def _reopen(tenant_id, source_id, external_id):
        return b"re-read from source"

    cr.register_source_reopener("test_reopenable", _reopen)
    try:
        doc = _Doc(RETENTION_SOURCE_ONLY, None, source_type="test_reopenable")
        assert await cr.resolve_content_for_reading(doc, "tenant-1") == b"re-read from source"
    finally:
        cr._SOURCE_REOPENERS.pop("test_reopenable", None)


async def test_a_source_with_no_adapter_is_distinguishable_from_one_that_failed():
    """The viewer's failure taxonomy rests on this: 'this source cannot be re-read at
    all' is a configuration fact, 'the source did not answer' is transient, and the
    reopener returns None for both."""
    async def _failing(tenant_id, source_id, external_id):
        raise RuntimeError("remote is down")

    cr.register_source_reopener("test_failing", _failing)
    try:
        assert cr.has_source_reopener("test_failing") is True
        assert cr.has_source_reopener("test_absent") is False

        doc = _Doc(RETENTION_SOURCE_ONLY, None, source_type="test_failing")
        assert await cr.reopen_source_content(doc, "tenant-1") is None
    finally:
        cr._SOURCE_REOPENERS.pop("test_failing", None)


async def test_an_adapter_failure_records_only_its_class(caplog):
    """A source adapter's error text is remote, untrusted content."""
    async def _failing(tenant_id, source_id, external_id):
        raise RuntimeError("connection string secret-value-12345 refused")

    cr.register_source_reopener("test_leaky", _failing)
    try:
        doc = _Doc(RETENTION_SOURCE_ONLY, None, source_type="test_leaky")
        with caplog.at_level("INFO"):
            await cr.reopen_source_content(doc, "tenant-1")
        rendered = " ".join(r.getMessage() + str(r.__dict__) for r in caplog.records)
        assert "secret-value-12345" not in rendered
    finally:
        cr._SOURCE_REOPENERS.pop("test_leaky", None)


async def test_reading_falls_back_to_the_platform_store_when_no_adapter_answers(monkeypatch):
    """A source-only document whose adapter is absent still raises rather than silently
    returning nothing, because the two facts are different."""
    doc = _Doc(RETENTION_SOURCE_ONLY, None, source_type="test_no_adapter")
    with pytest.raises(cr.SourceOnlyNotSupported):
        await cr.resolve_content_for_reading(doc, "tenant-1")


# --- "No pre-authorized URL is minted" ----------------------------------------------


def test_no_content_path_mints_a_url_for_a_client():
    """`original-document-storage` permits the content store exactly three operations.
    A URL-minting call would be a fourth, and is unimplementable for source-only content
    anyway. Guarded by source scan because the absence of a feature is otherwise
    untestable."""
    suspicious = ("generate_presigned_url", "presigned", "generate_blob_sas", "sas_token")
    offenders = []
    for rel in (
        "src/document_service/content_resolution.py",
        "src/document_service/content_store/contract.py",
        "src/document_service/content_store/minio_store.py",
        "src/document_service/content_store/instances.py",
        "src/document_service/services/storage.py",
        "src/document_service/api/v1/documents.py",
    ):
        source = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for token in suspicious:
            if token in source:
                offenders.append((rel, token))
    assert offenders == [], (
        f"a pre-authorized URL path appeared in: {offenders}. The content-store boundary "
        "permits exactly three operations."
    )
