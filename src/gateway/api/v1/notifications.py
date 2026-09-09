"""Persistent notifications — the bell in the portal topbar.

Rows are written by services when something crosses a line the user needs to know about
(an annotator approves an annotation task; an annotator approves a 50+ automated batch).
This router only reads them and marks them read.

Scoping: a caller sees a notification when it is for their tenant AND it is addressed
either to their role or to them specifically. A `business_user` therefore never sees the
annotation/training notifications, which are all `recipient_role='tenant_admin'`.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.gateway.dependencies import get_db, require_tenant_role, get_request_tenant_id

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class Notification(BaseModel):
    id: str
    kind: str
    title: str
    body: str | None
    resource_type: str | None
    resource_id: str | None
    read_at: str | None
    created_at: str


class NotificationList(BaseModel):
    items: list[Notification]
    unread: int


def _user_id(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.get("", response_model=NotificationList)
async def list_notifications(
    request: Request,
    unread_only: bool = False,
    limit: int = 50,
    role: str = Depends(require_tenant_role),
    tenant_id: str = Depends(get_request_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> NotificationList:
    limit = max(1, min(limit, 200))
    audience = "(recipient_role = :role OR recipient_user_id = :uid)"
    where = f"tenant_id = :tenant_id AND {audience}"
    if unread_only:
        where += " AND read_at IS NULL"

    params = {"tenant_id": tenant_id, "role": role, "uid": _user_id(request), "limit": limit}
    rows = (
        await db.execute(
            text(
                f"SELECT id, kind, title, body, resource_type, resource_id, read_at, created_at "
                f"FROM public.notifications WHERE {where} "
                f"ORDER BY created_at DESC LIMIT :limit"
            ),
            params,
        )
    ).fetchall()

    unread = (
        await db.execute(
            text(
                f"SELECT COUNT(*) FROM public.notifications "
                f"WHERE tenant_id = :tenant_id AND {audience} AND read_at IS NULL"
            ),
            {"tenant_id": tenant_id, "role": role, "uid": _user_id(request)},
        )
    ).scalar() or 0

    return NotificationList(
        items=[
            Notification(
                id=r[0],
                kind=r[1],
                title=r[2],
                body=r[3],
                resource_type=r[4],
                resource_id=r[5],
                read_at=r[6].isoformat() if r[6] else None,
                created_at=r[7].isoformat(),
            )
            for r in rows
        ],
        unread=int(unread),
    )


class MarkReadResult(BaseModel):
    updated: int


@router.post("/{notification_id}/read", response_model=MarkReadResult)
async def mark_read(
    notification_id: str,
    request: Request,
    role: str = Depends(require_tenant_role),
    tenant_id: str = Depends(get_request_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResult:
    result = await db.execute(
        text(
            "UPDATE public.notifications SET read_at = NOW() "
            "WHERE id = :id AND tenant_id = :tenant_id "
            "AND (recipient_role = :role OR recipient_user_id = :uid) AND read_at IS NULL"
        ),
        {"id": notification_id, "tenant_id": tenant_id, "role": role, "uid": _user_id(request)},
    )
    await db.commit()
    if result.rowcount == 0:
        # Either it does not exist, is not ours, or was already read — all "nothing to do".
        raise HTTPException(status_code=404, detail="Notification not found or already read")
    return MarkReadResult(updated=result.rowcount)


@router.post("/read-all", response_model=MarkReadResult)
async def mark_all_read(
    request: Request,
    role: str = Depends(require_tenant_role),
    tenant_id: str = Depends(get_request_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResult:
    result = await db.execute(
        text(
            "UPDATE public.notifications SET read_at = NOW() "
            "WHERE tenant_id = :tenant_id AND (recipient_role = :role OR recipient_user_id = :uid) "
            "AND read_at IS NULL"
        ),
        {"tenant_id": tenant_id, "role": role, "uid": _user_id(request)},
    )
    await db.commit()
    return MarkReadResult(updated=result.rowcount)
