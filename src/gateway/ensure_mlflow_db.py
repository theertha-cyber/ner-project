"""Ensure the ner_mlflow database exists before the MLflow tracking server starts.

Postgres only auto-creates the database named by POSTGRES_DB (ner_dev) on first
container init, and MLflow's backend store does not create its own database -
it expects ner_mlflow to already exist on the same Postgres instance.
"""
import psycopg2
from urllib.parse import urlparse, urlunparse
from src.shared.config import settings

TARGET_DB = "ner_mlflow"


def ensure_mlflow_database():
    parsed = urlparse(settings.database_url_sync)
    maintenance_url = urlunparse(parsed._replace(path="/postgres"))

    conn = psycopg2.connect(maintenance_url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
            if cur.fetchone():
                print(f"Database {TARGET_DB!r} already exists")
                return
            cur.execute(f"CREATE DATABASE {TARGET_DB}")
            print(f"Created database {TARGET_DB!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_mlflow_database()
