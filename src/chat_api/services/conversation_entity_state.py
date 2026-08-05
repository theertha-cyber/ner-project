import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat_api.services.entity_resolver import Candidate

logger = logging.getLogger(__name__)

MAX_REASKS = 1


@dataclass
class ConversationState:
    conversation_id: str
    pending_original_message: str | None = None
    pending_mention: str | None = None
    pending_candidates: list[Candidate] = field(default_factory=list)
    pending_reask_count: int = 0
    resolved_document_id: str | None = None
    resolved_entity_value: str | None = None

    @property
    def has_pending_clarification(self) -> bool:
        return self.pending_original_message is not None

    @property
    def has_binding(self) -> bool:
        return self.resolved_document_id is not None


def _candidates_to_json(candidates: list[Candidate]) -> str:
    return json.dumps([
        {
            "document_id": c.document_id, "name": c.name, "organization": c.organization,
            "experience": c.experience, "skills": c.skills, "filename": c.filename,
        }
        for c in candidates
    ])


def _candidates_from_json(raw) -> list[Candidate]:
    if raw is None:
        return []
    data = json.loads(raw) if isinstance(raw, str) else raw
    return [
        Candidate(
            document_id=d["document_id"], name=d["name"], organization=d.get("organization"),
            experience=d.get("experience"), skills=d.get("skills") or [], filename=d.get("filename"),
        )
        for d in data
    ]


async def read_state(session: AsyncSession, schema: str, conversation_id: str) -> ConversationState:
    result = await session.execute(
        text(f"""
            SELECT pending_original_message, pending_mention, pending_candidates, pending_reask_count,
                   resolved_document_id, resolved_entity_value
            FROM {schema}.conversation_entity_state WHERE conversation_id = :cid
        """),
        {"cid": conversation_id},
    )
    row = result.fetchone()
    if row is None:
        return ConversationState(conversation_id=conversation_id)
    return ConversationState(
        conversation_id=conversation_id,
        pending_original_message=row.pending_original_message,
        pending_mention=row.pending_mention,
        pending_candidates=_candidates_from_json(row.pending_candidates),
        pending_reask_count=row.pending_reask_count or 0,
        resolved_document_id=row.resolved_document_id,
        resolved_entity_value=row.resolved_entity_value,
    )


async def _upsert(session: AsyncSession, schema: str, conversation_id: str, **fields) -> None:
    columns = ["conversation_id", *fields.keys(), "updated_at"]
    placeholders = [":conversation_id", *(f":{k}" for k in fields.keys()), "now()"]
    update_clause = ", ".join(f"{k} = :{k}" for k in fields.keys()) + ", updated_at = now()"
    await session.execute(
        text(f"""
            INSERT INTO {schema}.conversation_entity_state ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (conversation_id) DO UPDATE SET {update_clause}
        """),
        {"conversation_id": conversation_id, **fields},
    )


async def store_pending_clarification(
    session: AsyncSession, schema: str, conversation_id: str, original_message: str, mention: str, candidates: list[Candidate],
) -> None:
    """A new clarification always replaces any existing pending state for the
    conversation (single row, ON CONFLICT DO UPDATE)."""
    await _upsert(
        session, schema, conversation_id,
        pending_original_message=original_message,
        pending_mention=mention,
        pending_candidates=_candidates_to_json(candidates),
        pending_reask_count=0,
    )


async def increment_reask(session: AsyncSession, schema: str, conversation_id: str, current_count: int) -> None:
    await session.execute(
        text(f"UPDATE {schema}.conversation_entity_state SET pending_reask_count = :count, updated_at = now() WHERE conversation_id = :cid"),
        {"count": current_count + 1, "cid": conversation_id},
    )


async def clear_pending(session: AsyncSession, schema: str, conversation_id: str) -> None:
    await session.execute(
        text(f"""
            UPDATE {schema}.conversation_entity_state
            SET pending_original_message = NULL, pending_candidates = NULL, pending_reask_count = 0, updated_at = now()
            WHERE conversation_id = :cid
        """),
        {"cid": conversation_id},
    )


async def set_binding(session: AsyncSession, schema: str, conversation_id: str, document_id: str, entity_value: str) -> None:
    await _upsert(
        session, schema, conversation_id,
        resolved_document_id=document_id, resolved_entity_value=entity_value,
    )


async def clear_binding(session: AsyncSession, schema: str, conversation_id: str) -> None:
    await session.execute(
        text(f"""
            UPDATE {schema}.conversation_entity_state
            SET resolved_document_id = NULL, resolved_entity_value = NULL, updated_at = now()
            WHERE conversation_id = :cid
        """),
        {"cid": conversation_id},
    )
