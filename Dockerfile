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

# Runtime binaries the OCR path shells out to: tesseract for recognition, poppler's
# pdftoppm (via pdf2image) for page rasterisation.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local

COPY tenant_schema_ddl.py .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
