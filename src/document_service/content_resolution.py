"""Obtaining a document's bytes from its recorded retention mode.

One implementation, used by everything that reads a document's content — the processing
worker and, since the cited-document viewer, the HTTP route that serves it to a reader.
The `original-document-storage` capability requires the retention mode be recorded once
and never re-derived; having two resolvers would be two places to re-derive it.

Its own module, rather than living in the OCR worker where it started, because a request
path should not have to construct chunking and the embedding service to read a file. The
worker re-exports every name below, so `blob_sync.reopen`, which registers through
`ocr_worker.register_source_reopener`, and the tests that monkeypatch the worker's own
attributes, both keep working unchanged.

This module deliberately imports nothing from the processing pipeline. The content store
is imported at call time for the same cycle-avoidance reason it always was.
"""

import logging

from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)

logger = logging.getLogger(__name__)


class ContentUnresolvable(Exception):
    """The document's bytes cannot be obtained under its recorded retention mode."""


class SourceOnlyNotSupported(ContentUnresolvable):
    """A `source_only` document whose source type has no registered adapter.

    Distinct from "the bytes are gone" and from "the source is temporarily unreachable":
    all three leave a caller with no bytes, and only one of them is worth retrying. The
    viewer's failure taxonomy depends on being able to tell them apart.
    """


# --- Source reopeners -------------------------------------------------------------------
#
# `source_only` retention stores no bytes, so they are re-acquired through a registered
# per-source-type adapter. The registry (not imports) connects a reader to source
# runtimes: `blob_sync.reopen` registers the Azure Blob adapter as an import side effect,
# and with none registered a caller is told the source is not reopenable rather than
# being handed a confusing absence.
#
# Because registration happens on import, every process that serves content must import
# the registering module. The Celery worker does so at task time; the document-service
# API does so at startup.

_SOURCE_REOPENERS: dict = {}


def register_source_reopener(source_type: str, reopen) -> None:
    _SOURCE_REOPENERS[source_type] = reopen


def has_source_reopener(source_type: str | None) -> bool:
    """Whether this source type can be asked for bytes at all.

    Exists because a reopener reports every failure as `None` — a missing adapter and a
    failed download are indistinguishable from its return value alone. Callers that must
    separate a configuration fact from a transient one check this first.
    """
    return source_type in _SOURCE_REOPENERS


async def reopen_source_content(document, tenant_id: str):
    """Ask the registered adapter for this document's bytes, or None.

    Returns None both when no adapter is registered and when the adapter fails; use
    `has_source_reopener` to tell those apart. The exception is swallowed deliberately:
    a source adapter's error text is remote, untrusted content, so only its class is
    recorded.
    """
    from src.document_service.services.ocr_worker import classify_processing_error

    source_type = getattr(document, "source_type", None)
    reopen = _SOURCE_REOPENERS.get(source_type)
    if reopen is None:
        return None
    try:
        return await reopen(
            tenant_id,
            getattr(document, "source_id", None),
            getattr(document, "external_id", None),
        )
    except Exception as exc:
        logger.info(
            "source_reopen_failed",
            extra={"error_class": classify_processing_error(exc)},
        )
        return None


# --- Store selection and resolution ------------------------------------------------------


def store_for(retention_mode: str):
    # Imported at call time so this module and the content store can depend on each
    # other's packages without an import cycle at module load.
    from src.document_service.content_store import get_durable_store, get_working_store

    if retention_mode == RETENTION_EPHEMERAL:
        return get_working_store()
    return get_durable_store()


def resolve_content(document, store_resolver=None) -> bytes | None:
    """Obtain the bytes implied by the document's recorded retention mode.

    `store_resolver` exists so a caller can supply its own store selection — in practice
    `ocr_worker._store_for`, which tests monkeypatch to stand a fake store in for MinIO.
    Injecting it keeps one implementation of the resolution rule while leaving that
    seam where the existing suites expect to find it.

    The recorded value decides — never a re-derivation, and never the shape of the
    reference. Returns None when the resolution is well defined but the bytes are gone.
    Raises `SourceOnlyNotSupported` for a `source_only` document, whose bytes live
    outside every platform store; use `resolve_content_for_reading` to include the
    reopen path.
    """
    retention_mode = getattr(document, "retention_mode", None) or RETENTION_PLATFORM_BLOB
    if retention_mode == RETENTION_SOURCE_ONLY:
        raise SourceOnlyNotSupported(
            "source_only retention requires a reopenable source adapter"
        )
    reference = getattr(document, "blob_path", None)
    if not reference:
        return None
    resolver = store_resolver or store_for
    return resolver(retention_mode).open(reference)


async def resolve_content_for_reading(document, tenant_id: str, store_resolver=None):
    """Resolve bytes, re-acquiring source-only content through its adapter.

    The one resolution every reader shares: the processing worker calls it to extract
    text, and the content route calls it to serve a document to a reader. Anything
    unresolvable raises `ContentUnresolvable`, exactly as `resolve_content` does when no
    adapter can supply the bytes.
    """
    retention_mode = getattr(document, "retention_mode", None) or RETENTION_PLATFORM_BLOB
    if retention_mode == RETENTION_SOURCE_ONLY:
        reopened = await reopen_source_content(document, tenant_id)
        if reopened is not None:
            return reopened
    return resolve_content(document, store_resolver=store_resolver)
