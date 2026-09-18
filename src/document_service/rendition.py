"""Converting an original into a PDF the viewer can render.

The viewer has exactly one rendering path — pdf.js — so anything a browser cannot render
natively is converted here rather than handled by a second renderer in the client. That
is the whole reason conversion is server-side: a per-format matrix in the browser would
need a `.doc` story the browser does not have.

A rendition is derived and nothing more. The original's bytes, its recorded media type,
its checksum and its storage reference are untouched by conversion, and the original
remains obtainable.

Nothing is persisted. The `document-pdf-rendition` capability permits reuse for a
retained document but does not require it, and caching a converted PDF of an `ephemeral`
or `source_only` document would durably recreate exactly what that tenant's retention
policy deleted or declined to store. Converting per request costs latency; a cache that
has to be correct about retention costs a privacy incident when it is not. If the latency
proves to matter, the cache belongs behind an explicit retention gate, not here.

Two adapters, chosen by what the platform already carries:

- PyMuPDF renders TIFF and CSV. It is already a dependency, runs in-process, and needs no
  image change.
- LibreOffice converts `.doc` and `.docx`. Nothing pure-Python reproduces Word layout
  faithfully, and a low-fidelity text extraction dressed up as "the original document"
  would defeat the point of showing the original. When the binary is absent the
  conversion reports failure rather than degrading silently.
"""

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

PDF_MEDIA_TYPE = "application/pdf"

# Bounded so a pathological input cannot hold a request open indefinitely. Chosen to be
# comfortably above a normal document and well below any gateway timeout.
CONVERSION_TIMEOUT_SECONDS = 20

# Conversion parses untrusted input, historically a rich source of memory-safety bugs, so
# the input is bounded too. Below the 50MB ingestion ceiling: a document that large is not
# one anyone wants rendered in a side panel.
MAX_CONVERTIBLE_BYTES = 25 * 1024 * 1024

_WORD_TYPES = frozenset({
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
})


class ConversionFailed(Exception):
    """The original could not be turned into a PDF.

    Never swallowed into an empty or partial PDF: a blank page presented as the document
    is worse than an error, because the reader cannot tell that anything went wrong.
    """


class ConversionTimedOut(ConversionFailed):
    """The conversion exceeded its bound and was abandoned."""


class ConversionTooLarge(ConversionFailed):
    """The original is larger than this path will attempt."""


def _tiff_to_pdf(data: bytes) -> bytes:
    """One PDF page per TIFF frame, preserving page structure so a page reference into
    the original still means something in the rendition."""
    import fitz

    with fitz.open(stream=data, filetype="tiff") as source:
        return source.convert_to_pdf()


def _csv_to_pdf(data: bytes) -> bytes:
    """A readable, paginated rendering of tabular text.

    Not a spreadsheet rendering — a CSV has no layout of its own, so the honest thing is
    legible monospaced rows rather than an invented table style.
    """
    import csv
    import io

    import fitz

    text = data.decode("utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    lines = [" | ".join(cell.strip() for cell in row) for row in rows]

    document = fitz.open()
    page = document.new_page()
    writer = fitz.TextWriter(page.rect)
    font = fitz.Font("cour")
    y = 40.0
    for line in lines:
        if y > page.rect.height - 40:
            writer.write_text(page)
            page = document.new_page()
            writer = fitz.TextWriter(page.rect)
            y = 40.0
        # Truncated rather than wrapped: a spilled column is easier to read than a row
        # broken across lines when the reader is checking one cited value.
        writer.append((40, y), line[:110], font=font, fontsize=9)
        y += 12
    writer.write_text(page)
    rendered = document.tobytes()
    document.close()
    return rendered


def _word_to_pdf(data: bytes, suffix: str) -> bytes:
    """LibreOffice, out of process, in a scratch directory it cannot escape."""
    with tempfile.TemporaryDirectory() as workdir:
        source = Path(workdir) / f"input{suffix}"
        source.write_bytes(data)
        try:
            subprocess.run(
                [
                    "soffice", "--headless", "--norestore",
                    "--convert-to", "pdf", "--outdir", workdir, str(source),
                ],
                check=True,
                capture_output=True,
                timeout=CONVERSION_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            # The toolchain lives only in the converting service's image. Elsewhere this
            # is a deployment fact, reported rather than masked.
            raise ConversionFailed("converter_unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise ConversionTimedOut("conversion_timeout") from exc
        except subprocess.CalledProcessError as exc:
            # The converter's stderr quotes the document back; only the class is kept.
            raise ConversionFailed("converter_error") from exc

        produced = source.with_suffix(".pdf")
        if not produced.exists():
            raise ConversionFailed("converter_produced_nothing")
        return produced.read_bytes()


def to_pdf(data: bytes, media_type: str) -> bytes:
    """Convert an original into a PDF, or raise a `ConversionFailed`.

    Never returns the input unchanged: a caller that received the original bytes back
    under a PDF media type would hand pdf.js something it cannot parse, and the reader
    would see a blank panel with no explanation.
    """
    if len(data) > MAX_CONVERTIBLE_BYTES:
        raise ConversionTooLarge("input_too_large")

    if media_type not in _CONVERTERS:
        raise ConversionFailed("unsupported_for_conversion")

    try:
        return _CONVERTERS[media_type](data)
    except ConversionFailed:
        # Already one of ours — the Word adapter distinguishes timeout from failure, and
        # that distinction must survive.
        raise
    except Exception as exc:
        # Every adapter raises its own library's errors: PyMuPDF has `FzErrorFormat`, the
        # CSV path can raise anything a malformed decode produces. They are translated
        # here rather than at each call site so no adapter can leak a type the route does
        # not know to catch — which would surface as a 500 instead of a viewer message.
        # The message is not kept: a parser error quotes the document back.
        logger.info(
            "document_conversion_failed",
            extra={"error_class": type(exc).__name__},
        )
        raise ConversionFailed("converter_error") from exc


_CONVERTERS = {
    "image/tiff": _tiff_to_pdf,
    "text/csv": _csv_to_pdf,
    "application/msword": lambda data: _word_to_pdf(data, ".doc"),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        lambda data: _word_to_pdf(data, ".docx"),
}
