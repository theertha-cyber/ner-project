import uuid
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.extraction_service.services.entity_normalizer import NormalizedEntity
from src.shared.config import settings


def insert_document_entities(conn: Connection, schema: str, document_id: str, entities: list[NormalizedEntity]) -> None:
    """Writes reconstructed entities, with the provenance that says where each value
    came from.

    `source_entity_value` / `source_entity_type` are written only when post-processing
    actually changed the value or the type — a NULL therefore *means* "unchanged"
    rather than "unknown", and the table does not double in size for the majority of
    rows nothing touches."""
    for entity in entities:
        conn.execute(
            text(f"""
                INSERT INTO {schema}.document_entities
                    (id, document_id, entity_type, entity_value, normalized_value, confidence, page_number, char_start, char_end,
                     value_kind, value_number, value_number_high, value_unit, value_date, value_date_high,
                     source_entity_value, source_entity_type, postprocess_status, postprocess_model,
                     postprocess_prompt_version, postprocess_at, extraction_schema_version, occurrence_count)
                VALUES (:id, :document_id, :entity_type, :entity_value, :normalized_value, :confidence, :page_number, :char_start, :char_end,
                        :value_kind, :value_number, :value_number_high, :value_unit, :value_date, :value_date_high,
                        :source_entity_value, :source_entity_type, :postprocess_status, :postprocess_model,
                        :postprocess_prompt_version, :postprocess_at, :extraction_schema_version, :occurrence_count)
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
                "value_kind": entity.value_kind,
                "value_number": entity.value_number,
                "value_number_high": entity.value_number_high,
                "value_unit": entity.value_unit,
                "value_date": entity.value_date,
                "value_date_high": entity.value_date_high,
                "source_entity_value": entity.source_entity_value,
                "source_entity_type": entity.source_entity_type,
                "postprocess_status": entity.postprocess_status,
                "postprocess_model": entity.postprocess_model,
                "postprocess_prompt_version": entity.postprocess_prompt_version,
                "postprocess_at": entity.postprocess_at,
                "extraction_schema_version": settings.extraction_schema_version,
                "occurrence_count": entity.occurrence_count,
            },
        )


def delete_document_entities(conn: Connection, schema: str, document_id: str) -> None:
    conn.execute(
        text(f"DELETE FROM {schema}.document_entities WHERE document_id = :document_id"),
        {"document_id": document_id},
    )
