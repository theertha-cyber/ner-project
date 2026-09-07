"""The single definition of the tenant-schema naming rule.

ADR-001 puts every tenant's content in its own PostgreSQL schema, so this string is
interpolated into raw SQL across the document, annotation, chat, and extraction
services. It was copied into each of them independently; eleven copies of one naming
rule is eleven places a future change to it can be missed. Nothing here imports
FastAPI or SQLAlchemy, so a Celery worker can use it as cheaply as a route module.
"""


def schema_for_tenant(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"
