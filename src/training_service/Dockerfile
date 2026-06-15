FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir poetry
RUN pip install --no-cache-dir celery redis requests \
    transformers datasets evaluate seqeval \
    boto3 sqlalchemy asyncpg python-jose passlib pydantic-settings \
    "mlflow[postgresql,s3]" && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "src.training_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
