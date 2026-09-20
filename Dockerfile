FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without dev --no-interaction

# PDF text extraction is OCR-only (pdf2image rasterises, pytesseract reads). Installed
# outside Poetry so the lock file does not have to be regenerated for a leaf dependency.
RUN pip install --no-cache-dir "pdf2image==1.17.0" "pytesseract==0.3.13" "pillow>=10,<12"

FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime binaries the OCR path shells out to: tesseract (with the English language pack)
# for recognition, poppler's pdftoppm (via pdf2image) for page rasterisation.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

COPY tenant_schema_ddl.py .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Document service ---------------------------------------------------------------
#
# Its own target, because it is the only service that converts a document into a viewable
# PDF and LibreOffice is several hundred megabytes. Adding it to the shared `runtime`
# stage above would inflate the model-serving, training, annotation and extraction images
# by that much for a capability none of them use.
#
# Only the Writer and Calc filters are installed: the viewer converts .doc/.docx and
# reads .csv, and the rest of the suite (Impress, Draw, Base) has nothing to contribute.
FROM runtime AS runtime-documents

RUN apt-get update && apt-get install -y --no-install-recommends         libreoffice-writer-nogui libreoffice-calc-nogui     && rm -rf /var/lib/apt/lists/*

# LibreOffice writes a profile on first run and will not start headless without a home it
# can own. Without this the first conversion of every container fails, and the second
# succeeds -- a failure that looks like flakiness rather than a missing directory.
ENV HOME=/tmp

CMD ["uvicorn", "src.document_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
