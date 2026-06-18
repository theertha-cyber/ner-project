from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import Tenant, slugify, generate_uuid
from src.shared.auth import hash_password, validate_password
from src.shared.exceptions import NotFoundError, ConflictError, ValidationError


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, payload: dict) -> dict:
        name = payload["name"]
        slug = payload.get("slug", slugify(name))
        admin_email = payload["admin_email"]
        admin_password = payload["admin_password"]

        password_error = validate_password(admin_password)
        if password_error:
            raise ValidationError(password_error)

        existing = await self.db.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": slug},
        )
        if existing.fetchone():
            raise ConflictError("Tenant", "slug", slug)

        tenant_id = generate_uuid()
        await self.db.execute(
            text("""
                INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions)
                VALUES (:id, :name, :slug, 'active', :max_users, :max_docs, :max_storage, :max_models)
            """),
            {
                "id": tenant_id,
                "name": name,
                "slug": slug,
                "max_users": payload.get("max_users", 10),
                "max_docs": payload.get("max_documents", 1000),
                "max_storage": payload.get("max_storage_gb", 5),
                "max_models": payload.get("max_model_versions", 10),
            },
        )

        schema_name = f"tenant_{tenant_id}".replace("-", "_")
        await self.db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

        tables = await self.db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'")
        )
        for row in tables.fetchall():
            table_name = row[0]
            await self.db.execute(text(
                f"CREATE TABLE {schema_name}.{table_name} "
                f"(LIKE tenant_template.{table_name} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            ))

        # Create the initial tenant admin in the same transaction
        admin_id = generate_uuid()
        await self.db.execute(
            text("""
                INSERT INTO public.tenant_users (id, tenant_id, email, password_hash, role, status)
                VALUES (:id, :tid, :email, :pwd_hash, 'tenant_admin', 'active')
            """),
            {
                "id": admin_id,
                "tid": tenant_id,
                "email": admin_email,
                "pwd_hash": hash_password(admin_password),
            },
        )

        await self.db.commit()

        tenant_data = await self._get_by_id(tenant_id)
        return {
            "tenant": tenant_data,
            "admin_user": {"id": admin_id, "email": admin_email, "role": "tenant_admin"},
        }

    async def list_tenants(self, status: str | None = None, page: int = 1, per_page: int = 20) -> dict:
        conditions = []
        params = {}
        if status:
            conditions.append("status = :status")
            params["status"] = status

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * per_page

        count_result = await self.db.execute(
            text(f"SELECT COUNT(*) FROM public.tenants {where}"),
            params,
        )
        total = count_result.scalar()

        result = await self.db.execute(
            text(f"SELECT id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions, created_at FROM public.tenants {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": per_page, "offset": offset},
        )
        rows = result.fetchall()

        tenants = [
            {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "status": r.status,
                "max_users": r.max_users,
                "max_documents": r.max_documents,
                "max_storage_gb": r.max_storage_gb,
                "max_model_versions": r.max_model_versions,
                "created_at": str(r.created_at),
            }
            for r in rows
        ]

        return {"tenants": tenants, "total": total, "page": page, "per_page": per_page}

    async def get_tenant(self, tenant_id: str) -> dict:
        data = await self._get_by_id(tenant_id)
        if not data:
            raise NotFoundError("Tenant", tenant_id)

        user_count = await self.db.scalar(
            text("SELECT COUNT(*) FROM public.tenant_users WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )

        return {"tenant": {**data, "user_count": user_count}}

    async def update_tenant(self, tenant_id: str, payload: dict) -> dict:
        existing = await self._get_by_id(tenant_id)
        if not existing:
            raise NotFoundError("Tenant", tenant_id)

        allowed_fields = {"name", "max_users", "max_documents", "max_storage_gb", "max_model_versions"}
        updates = {k: v for k, v in payload.items() if k in allowed_fields}

        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = tenant_id
            await self.db.execute(
                text(f"UPDATE public.tenants SET {set_clause} WHERE id = :id"),
                updates,
            )
            await self.db.commit()

        data = await self._get_by_id(tenant_id)
        return {"tenant": data}

    async def deactivate_tenant(self, tenant_id: str) -> dict:
        existing = await self._get_by_id(tenant_id)
        if not existing:
            raise NotFoundError("Tenant", tenant_id)

        await self.db.execute(
            text("UPDATE public.tenants SET status = 'inactive' WHERE id = :id"),
            {"id": tenant_id},
        )
        await self.db.commit()

        data = await self._get_by_id(tenant_id)
        return {"tenant": data}

    async def _get_by_id(self, tenant_id: str) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT id, name, slug, status, max_users, max_documents,
                       max_storage_gb, max_model_versions, created_at, updated_at
                FROM public.tenants WHERE id = :id
            """),
            {"id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "slug": row.slug,
            "status": row.status,
            "max_users": row.max_users,
            "max_documents": row.max_documents,
            "max_storage_gb": row.max_storage_gb,
            "max_model_versions": row.max_model_versions,
            "created_at": str(row.created_at),
            "updated_at": str(row.updated_at),
        }
