"""Image OCR path for document ingestion (jpeg/png/tiff and scanned PDFs).

Skipped when the tesseract binary is unavailable on the host; the Docker
runtime image installs it (see Dockerfile).
"""
import io

import pytest

from src.document_service.services.ocr_worker import (
    extract_text_image,
    extract_text_pdf_as_image,
    is_allowed_file,
)

Image = pytest.importorskip("PIL.Image")
ImageDraw = pytest.importorskip("PIL.ImageDraw")
pytesseract = pytest.importorskip("pytesseract")

try:
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
except Exception:  # pragma: no cover - depends on host
    HAS_TESSERACT = False

needs_tesseract = pytest.mark.skipif(
    not HAS_TESSERACT, reason="tesseract binary not installed on this host"
)


def _text_image():
    img = Image.new("RGB", (700, 160), "white")
    ImageDraw.Draw(img).text((20, 60), "INVOICE 12345 ACME CORP", fill="black")
    return img


def _encode(img, fmt, **kwargs):
    buf = io.BytesIO()
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


@needs_tesseract
class TestImageOcr:
    def test_jpeg_yields_text_span(self):
        spans = extract_text_image(_encode(_text_image(), "JPEG"))
        assert len(spans) == 1
        assert "INVOICE" in spans[0]["text"]
        assert spans[0]["char_end"] == len(spans[0]["text"])
        assert spans[0]["page_number"] == 0

    def test_palette_png_is_converted_before_ocr(self):
        spans = extract_text_image(_encode(_text_image().convert("P"), "PNG"))
        assert "INVOICE" in spans[0]["text"]

    def test_multiframe_tiff_yields_one_span_per_frame(self):
        img = _text_image()
        data = _encode(img, "TIFF", save_all=True, append_images=[img])
        spans = extract_text_image(data)
        assert [s["page_number"] for s in spans] == [0, 1]
        assert spans[1]["char_start"] == spans[0]["char_end"] + 1

    def test_scanned_pdf_falls_back_to_rasterised_ocr(self):
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_image(fitz.Rect(0, 0, 500, 120), stream=_encode(_text_image(), "JPEG"))
        pdf_bytes = doc.tobytes()
        doc.close()

        spans = extract_text_pdf_as_image(pdf_bytes)
        assert len(spans) == 1
        assert "INVOICE" in spans[0]["text"]


class TestAllowedExtensions:
    @pytest.mark.parametrize("name", ["scan.jpg", "scan.JPEG", "page.png", "fax.tiff"])
    def test_image_uploads_are_accepted(self, name):
        assert is_allowed_file(name)
