from sqlalchemy import text
from src.document_service.content_store.instances import get_durable_store
from src.extraction_service.services.relational_projection import (
    build_relational_delete_statements,
)
from src.shared.entity_views import (
    list_existing_generated_tables,
    load_definition_specs,
)


async def has_table(session, schema: str, table_name: str) -> bool:
    table_check = await session.execute(
        text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table_name
            LIMIT 1
        """),
        {"schema": schema, "table_name": table_name},
    )
    return bool(table_check.fetchone())


async def hard_delete_documents(session, schema, tenant_id, document_ids):
    if not document_ids:
        return

    from src.document_service.api.v1.documents import has_column
    use_blob_path = await has_column(session, schema, "documents", "blob_path")
    blob_col = "blob_path" if use_blob_path else "storage_uri"

    # Load definitions and existing generated tables once per call to avoid repeating database roundtrips
    try:
        specs = await load_definition_specs(session, tenant_id)
        existing = await list_existing_generated_tables(session, schema)
    except Exception:
        specs = []
        existing = []

    for doc_id in document_ids:
        # Fetch blob path/URI
        result = await session.execute(
            text(f"SELECT {blob_col} FROM {schema}.documents WHERE id = :id"),
            {"id": doc_id},
        )
        row = result.fetchone()
        blob_path = getattr(row, blob_col, None) if row else None
        if blob_path:
            try:
                store = get_durable_store()
                store.delete(blob_path)
            except Exception:
                pass  # tolerate failures deleting blob

        # Delete derived tables
        for table in ["document_chunks", "document_text_spans", "extracted_entities", "document_entities"]:
            if await has_table(session, schema, table):
                try:
                    await session.execute(
                        text(f"DELETE FROM {schema}.{table} WHERE document_id = :id"),
                        {"id": doc_id},
                    )
                except Exception:
                    pass

        # Build relational delete statements with narrowing
        if specs and existing:
            try:
                for statement, params in build_relational_delete_statements(
                    schema, doc_id, specs, existing
                ):
                    await session.execute(text(statement), params)
            except Exception:
                pass  # tolerate missing or errored relational tables

        # Delete the document row
        await session.execute(
            text(f"DELETE FROM {schema}.documents WHERE id = :id"),
            {"id": doc_id},
        )
