import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.extraction_service.services.entity_normalizer import NormalizedEntity


def insert_document_entities(conn: Connection, schema: str, document_id: str, entities: list[NormalizedEntity]) -> None:
    for entity in entities:
        conn.execute(
            text(f"""
                INSERT INTO {schema}.document_entities
                    (id, document_id, entity_type, entity_value, normalized_value, confidence, page_number, char_start, char_end)
                VALUES (:id, :document_id, :entity_type, :entity_value, :normalized_value, :confidence, :page_number, :char_start, :char_end)
            """),
            {
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "entity_type": entity.entity_type,
                "entity_value": entity.entity_value,
                "normalized_value": entity.normalized_value,
                "confidence": entity.confidence,
                "page_number": entity.page_number,
                "char_start": entity.char_start,
                "char_end": entity.char_end,
            },
        )


def delete_document_entities(conn: Connection, schema: str, document_id: str) -> None:
    conn.execute(
        text(f"DELETE FROM {schema}.document_entities WHERE document_id = :document_id"),
        {"document_id": document_id},
    )
