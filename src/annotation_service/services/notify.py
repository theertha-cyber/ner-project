"""Writing persistent notifications.

The Tenant Admin does not re-review annotations an Annotator Admin approved — they are
*told* the work is done and proceed to training. That message has to survive a page
reload, so it is a row in `public.notifications`, not a toast.

`public`, not the tenant schema: the gateway reads this table to render the bell, and
`audit_events` (the other cross-cutting log) already lives in `public`. Every row still
carries `tenant_id` and every read is tenant-scoped.

Addressed to a *role* (`recipient_role='tenant_admin'`) rather than a user, because
"the Tenant Admin" is a position — whichever tenant admin opens the portal should see
it. `recipient_user_id` is available for the cases that are genuinely one person's.
"""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def notify(
    session: AsyncSession,
    *,
    tenant_id: str,
    kind: str,
    title: str,
    body: str | None = None,
    recipient_role: str | None = "tenant_admin",
    recipient_user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> str:
    """Insert one notification. Caller owns the surrounding transaction/commit."""
    notification_id = str(uuid.uuid4())
    await session.execute(
        text(
            """
            INSERT INTO public.notifications
                (id, tenant_id, recipient_role, recipient_user_id, kind, title, body,
                 resource_type, resource_id)
            VALUES
                (:id, :tenant_id, :recipient_role, :recipient_user_id, :kind, :title, :body,
                 :resource_type, :resource_id)
            """
        ),
        {
            "id": notification_id,
            "tenant_id": tenant_id,
            "recipient_role": recipient_role,
            "recipient_user_id": recipient_user_id,
            "kind": kind,
            "title": title,
            "body": body,
            "resource_type": resource_type,
            "resource_id": resource_id,
        },
    )
    return notification_id
