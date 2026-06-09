from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import generate_uuid
from src.shared.auth import hash_password, validate_password
from src.shared.exceptions import ValidationError, NotFoundError, ConflictError, QuotaExceededError


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, tenant_id: str, payload: dict) -> dict:
        email = payload["email"]
        password = payload["password"]
        role = payload.get("role", "business_user")

        password_error = validate_password(password)
        if password_error:
            raise ValidationError(password_error)

        quota = await self.db.execute(
            text("SELECT max_users FROM public.tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        quota_row = quota.fetchone()
        if not quota_row:
            raise NotFoundError("Tenant", tenant_id)

        current_count = await self.db.scalar(
            text("SELECT COUNT(*) FROM public.tenant_users WHERE tenant_id = :tid AND status = 'active'"),
            {"tid": tenant_id},
        )
        if current_count >= quota_row.max_users:
            raise QuotaExceededError("Users", quota_row.max_users)

        existing = await self.db.execute(
            text("SELECT id FROM public.tenant_users WHERE email = :email AND tenant_id = :tid"),
            {"email": email, "tid": tenant_id},
        )
        if existing.fetchone():
            raise ConflictError("User", "email", email)

        user_id = generate_uuid()
        password_hash = hash_password(password)
        await self.db.execute(
            text("""
                INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                VALUES (:id, :tid, :email, :pwd_hash, :role, 'active')
            """),
            {
                "id": user_id,
                "tid": tenant_id,
                "email": email,
                "pwd_hash": password_hash,
                "role": role,
            },
        )
        await self.db.commit()

        return {"user": {"id": user_id, "email": email, "role": role, "status": "active"}}

    async def list_users(self, tenant_id: str, role: str | None = None) -> dict:
        conditions = ["tenant_id = :tid"]
        params = {"tid": tenant_id}
        if role:
            conditions.append("role = :role")
            params["role"] = role

        where = " AND ".join(conditions)
        result = await self.db.execute(
            text(f"SELECT id, email, role, status, created_at FROM public.tenant_users WHERE {where} ORDER BY created_at DESC"),
            params,
        )
        rows = result.fetchall()
        users = [
            {"id": r.id, "email": r.email, "role": r.role, "status": r.status, "created_at": str(r.created_at)}
            for r in rows
        ]
        return {"users": users}

    async def get_user(self, tenant_id: str, user_id: str) -> dict:
        result = await self.db.execute(
            text("SELECT id, email, role, status, created_at FROM public.tenant_users WHERE id = :uid AND tenant_id = :tid"),
            {"uid": user_id, "tid": tenant_id},
        )
        row = result.fetchone()
        if not row:
            raise NotFoundError("User", user_id)
        return {"user": {"id": row.id, "email": row.email, "role": row.role, "status": row.status, "created_at": str(row.created_at)}}

    async def update_user(self, tenant_id: str, user_id: str, payload: dict) -> dict:
        existing = await self.get_user(tenant_id, user_id)
        current = existing["user"]

        allowed_fields = {"role", "status"}
        updates = {k: v for k, v in payload.items() if k in allowed_fields}

        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = user_id
            await self.db.execute(
                text(f"UPDATE public.tenant_users SET {set_clause} WHERE id = :id"),
                updates,
            )
            await self.db.commit()

        return await self.get_user(tenant_id, user_id)

    async def deactivate_user(self, tenant_id: str, user_id: str) -> dict:
        existing = await self.get_user(tenant_id, user_id)
        if existing["user"]["status"] != "active":
            return existing

        await self.db.execute(
            text("UPDATE public.tenant_users SET status = 'inactive' WHERE id = :uid AND tenant_id = :tid"),
            {"uid": user_id, "tid": tenant_id},
        )
        await self.db.commit()
        return await self.get_user(tenant_id, user_id)
