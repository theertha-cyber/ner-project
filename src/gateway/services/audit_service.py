from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import generate_uuid, AuditEventKind


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        actor: str,
        role: str,
        action: str,
        target: str,
        kind: AuditEventKind,
        tenant_id: str | None = None,
    ) -> dict:
        event_id = generate_uuid()
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text("""
                INSERT INTO public.audit_events (id, actor, role, action, target, kind, tenant_id, created_at)
                VALUES (:id, :actor, :role, :action, :target, :kind, :tenant_id, :created_at)
            """),
            {
                "id": event_id,
                "actor": actor,
                "role": role,
                "action": action,
                "target": target,
                "kind": kind.value,
                "tenant_id": tenant_id,
                "created_at": now,
            },
        )
        await self.db.commit()
        return {
            "id": event_id,
            "actor": actor,
            "role": role,
            "action": action,
            "target": target,
            "kind": kind.value,
            "tenant_id": tenant_id,
            "created_at": str(now),
        }

    async def list_events(self, page: int = 1, per_page: int = 50) -> dict:
        offset = (page - 1) * per_page

        count_result = await self.db.execute(
            text("SELECT COUNT(*) FROM public.audit_events"),
        )
        total = count_result.scalar()

        result = await self.db.execute(
            text("""
                SELECT id, actor, role, action, target, kind, tenant_id, created_at
                FROM public.audit_events
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": per_page, "offset": offset},
        )
        rows = result.fetchall()

        events = [
            {
                "id": r.id,
                "actor": r.actor,
                "role": r.role,
                "action": r.action,
                "target": r.target,
                "kind": r.kind,
                "tenant_id": r.tenant_id,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]

        return {"events": events, "total": total, "page": page, "per_page": per_page}
