"""Verification for media-type resolution — part of verification.md rows 72-81.

The extractor used to be chosen by splitting the MinIO object key. It is now chosen from
the document's resolved media type, in a fixed order: declared type, then filename
extension, then a content sniff. The order is the whole safety property — dropping the
filename fallback would reroute every `application/octet-stream` upload, which is common
in practice.
"""

import os

import pytest

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.services.ocr_worker import (
    IMAGE_MEDIA_TYPES,
    MEDIA_TYPE_PDF,
    resolve_media_type,
)

PDF_BYTES = b"%PDF-1.4 fixture"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture"
JPEG_BYTES = b"\xff\xd8\xff\xe0fixture"
TIFF_BYTES = b"II*\x00fixture"


# --- Step 1: a specific declared type wins ---------------------------------------------


def test_declared_media_type_selects_the_extractor():
    # The reference ends in `.bin`; it is not consulted, and must not be.
    assert resolve_media_type("image/png", "object.bin", PDF_BYTES) == "image/png"


def test_declared_type_survives_a_charset_parameter():
    assert resolve_media_type("application/pdf; charset=binary", None, None) == MEDIA_TYPE_PDF


@pytest.mark.parametrize(
    "declared,expected",
    [("image/jpg", "image/jpeg"), ("image/pjpeg", "image/jpeg"), ("image/tif", "image/tiff")],
)
def test_common_client_aliases_resolve(declared, expected):
    assert resolve_media_type(declared, None, None) == expected


# --- Step 2: the filename extension is the fallback ------------------------------------


@pytest.mark.parametrize("generic", ["application/octet-stream", "", None, "*/*"])
def test_generic_declared_type_falls_back_to_the_filename(generic):
    """This is today's behaviour, preserved exactly."""
    assert resolve_media_type(generic, "report.pdf", None) == MEDIA_TYPE_PDF
    assert resolve_media_type(generic, "scan.PNG", None) == "image/png"


def test_an_unknown_declared_type_falls_back_rather_than_failing():
    assert resolve_media_type("text/plain", "report.pdf", None) == MEDIA_TYPE_PDF


# --- Step 3: content sniff is the last resort ------------------------------------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (PDF_BYTES, MEDIA_TYPE_PDF),
        (PNG_BYTES, "image/png"),
        (JPEG_BYTES, "image/jpeg"),
        (TIFF_BYTES, "image/tiff"),
    ],
)
def test_content_sniff_resolves_when_nothing_is_declared_or_named(data, expected):
    assert resolve_media_type(None, "object", data) == expected


def test_unresolvable_media_type_is_none_not_a_guess():
    assert resolve_media_type(None, "object", b"not a known magic number") is None


# --- The order itself -------------------------------------------------------------------


def test_resolution_order_is_declared_then_filename_then_content():
    # All three disagree: the declared type must win.
    assert resolve_media_type("image/png", "report.pdf", PDF_BYTES) == "image/png"
    # Declared is generic: the filename wins over the content.
    assert resolve_media_type("application/octet-stream", "scan.png", PDF_BYTES) == "image/png"
    # Neither declared nor named: the content decides.
    assert resolve_media_type(None, "object", PNG_BYTES) == "image/png"


def test_the_image_media_types_are_the_ones_the_image_extractor_handles():
    assert IMAGE_MEDIA_TYPES == frozenset({"image/jpeg", "image/png", "image/tiff"})


# --- The reference is never parsed -------------------------------------------------------


def test_resolution_never_receives_or_consults_a_storage_reference():
    import inspect

    from src.document_service.services import ocr_worker

    signature = inspect.signature(resolve_media_type)
    assert list(signature.parameters) == ["declared", "filename", "data"]

    body = inspect.getsource(ocr_worker.process_document)
    # The old implementation was `blob_path.split(".")`.
    assert "blob_path.split" not in body
    assert ".split(\".\")" not in body
