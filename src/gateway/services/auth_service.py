import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.auth import verify_password, create_access_token, create_refresh_token, decode_token
from src.shared.exceptions import AuthError, NotFoundError


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def login(self, email: str, password: str) -> dict:
        result = await self.db.execute(
            text("""
                SELECT u.id, u.password_hash, u.role, u.status, u.tenant_id,
                       t.slug, t.status as tenant_status
                FROM public.tenant_users u
                JOIN public.tenants t ON t.id = u.tenant_id
                WHERE u.email = :email
            """),
            {"email": email},
        )
        row = result.fetchone()

        if not row or not verify_password(password, row.password_hash):
            raise AuthError("Invalid email or password")

        if row.status != "active":
            raise AuthError("User account is inactive")

        if row.tenant_status == "inactive":
            raise AuthError("Tenant is deactivated")

        tenant_id = str(row.tenant_id)
        user_id = str(row.id)
        access_token = create_access_token(tenant_id, user_id, row.role)
        refresh_token = create_refresh_token(tenant_id, user_id, row.role)

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

        new_access = create_access_token(tenant_id, user_id, role)
        new_refresh = create_refresh_token(tenant_id, user_id, role)

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
