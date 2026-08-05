FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --without dev --no-interaction

FROM python:3.11-slim AS runtime

WORKDIR /app

COPY --from=builder /usr/local /usr/local

COPY tenant_schema_ddl.py .
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "src.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
