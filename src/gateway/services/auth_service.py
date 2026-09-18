import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.auth import verify_password, create_access_token, create_refresh_token, decode_token
from src.shared.exceptions import AuthError, NotFoundError


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str) -> dict:
        # Email is unique per tenant, not globally (`uq_email_per_tenant`), so the same address
        # can be a legitimate account in more than one tenant with two different passwords.
        # Every matching row is fetched, ordered active-tenant-and-user first, and the password
        # decides which one the caller meant — never `fetchone()`'s arbitrary pick of whichever
        # row Postgres returns first, which could resolve a login to an unrelated deactivated
        # tenant even though the account the person actually typed the password for is active.
        result = await self.db.execute(
            text("""
                SELECT u.id, u.password_hash, u.role, u.status, u.tenant_id,
                       t.slug, t.status as tenant_status
                FROM public.tenant_users u
                JOIN public.tenants t ON t.id = u.tenant_id
                WHERE u.email = :email
                ORDER BY (u.status = 'active' AND t.status = 'active') DESC
            """),
            {"email": email},
        )
        rows = result.fetchall()

        row = next((r for r in rows if verify_password(password, r.password_hash)), None)
        if row is None:
            raise AuthError("Invalid email or password")

        if row.status != "active":
            raise AuthError("User account is inactive")

        if row.tenant_status == "inactive":
            raise AuthError("Tenant is deactivated")

        tenant_id = str(row.tenant_id)
        user_id = str(row.id)
        access_token = create_access_token(tenant_id, user_id, row.role, email)
        refresh_token = create_refresh_token(tenant_id, user_id, row.role, email)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "role": row.role,
                "tenant_id": tenant_id,
                "tenant_slug": row.slug,
            },
        }

    async def refresh(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type")

        tenant_id = payload["tenant_id"]
        user_id = payload["user_id"]
        role = payload["role"]

        result = await self.db.execute(
            text("""
                SELECT u.email, t.slug
                FROM public.tenant_users u
                JOIN public.tenants t ON t.id = u.tenant_id
                WHERE u.id = :user_id AND u.tenant_id = :tenant_id
            """),
            {"user_id": user_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()

        email = row.email if row else ""
        new_access = create_access_token(tenant_id, user_id, role, email)
        new_refresh = create_refresh_token(tenant_id, user_id, role, email)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": row.email if row else "",
                "role": role,
                "tenant_id": tenant_id,
                "tenant_slug": row.slug if row else None,
            },
        }

    async def logout(self, access_token: str) -> None:
        pass
