from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import Tenant, slugify, generate_uuid, AuditEventKind
from src.gateway.services.audit_service import AuditService
from src.shared.auth import hash_password, validate_password
from src.shared.config import settings
from src.shared.exceptions import NotFoundError, ConflictError, ValidationError
from src.shared.integration_profile.service import create_initial_profile

DATA_PLANE_MODE_PLATFORM = "platform"
DATA_PLANE_MODE_TENANT_OWNED = "tenant_owned"


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, payload: dict, actor_email: str = "", actor_role: str = "") -> dict:
        name = payload["name"]
        slug = payload.get("slug", slugify(name))
        admin_email = payload["admin_email"]
        admin_password = payload["admin_password"]
        data_plane_mode = payload.get("data_plane_mode") or DATA_PLANE_MODE_PLATFORM

        password_error = validate_password(admin_password)
        if password_error:
            raise ValidationError(password_error)

        if data_plane_mode == DATA_PLANE_MODE_TENANT_OWNED and not settings.tenant_owned_data_plane_enabled:
            raise ValidationError(
                "tenant_owned data planes are disabled in this environment"
            )

        existing = await self.db.execute(
            text("SELECT id FROM public.tenants WHERE slug = :slug"),
            {"slug": slug},
        )
        if existing.fetchone():
            raise ConflictError("Tenant", "slug", slug)

        tenant_id = generate_uuid()
        admin_id = generate_uuid()
        try:
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

            if data_plane_mode == DATA_PLANE_MODE_PLATFORM:
                # Unchanged platform path: clone the template schema now, so the
                # tenant can be used the moment this transaction commits.
                schema_name = f"tenant_{tenant_id}".replace("-", "_")
                await self.db.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

                tables = await self.db.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'")
                )
                for row in tables.fetchall():
                    table_name = row[0]
                    await self.db.execute(text(
                        f"CREATE TABLE {schema_name}.{table_name} "
                        f"(LIKE tenant_template.{table_name} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES INCLUDING GENERATED)"
                    ))
                await self.db.execute(
                    text(
                        "INSERT INTO public.tenant_data_planes (tenant_id, mode, status, schema_revision) "
                        "VALUES (:tid, 'platform', 'ready', 1)"
                    ),
                    {"tid": tenant_id},
                )
                await create_initial_profile(self.db, tenant_id)
            else:
                # tenant_owned: no platform schema at all (tenant-provisioning spec's
                # "A tenant-owned tenant is not cloned on the platform"). The store is
                # provisioned once the tenant admin activates a data-plane connection
                # (tenant-residency-store-provisioning spec) — until then the tenant is
                # `awaiting_store` and every content route 409s (Design D9).
                await self.db.execute(
                    text(
                        "INSERT INTO public.tenant_data_planes (tenant_id, mode, status) "
                        "VALUES (:tid, 'tenant_owned', 'awaiting_store')"
                    ),
                    {"tid": tenant_id},
                )
                await create_initial_profile(
                    self.db, tenant_id,
                    relational_adapter="tenant_postgresql",
                    index_adapter="tenant_pgvector",
                    retention_mode="ephemeral",
                )

            # Create the initial tenant admin in the same transaction
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
        except Exception:
            # Provisioning is all-or-nothing: a failure at any step (tenant row,
            # schema, table clone, or admin user) must not leave a partially
            # provisioned tenant behind. Nothing here is committed until the
            # audit record below, but the rollback is made explicit rather than
            # relying on that as an incidental side effect.
            await self.db.rollback()
            raise

        audit = AuditService(self.db)
        await audit.record(
            actor=actor_email,
            role=actor_role,
            action="tenant.create",
            target=slug,
            kind=AuditEventKind.create,
        )

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
        # The list query below joins `tenant_data_planes`, which has its own
        # `status` column — qualified separately so the filter (tenant status)
        # never becomes ambiguous against it.
        where_qualified = "WHERE t." + " AND t.".join(conditions) if conditions else ""
        offset = (page - 1) * per_page

        count_result = await self.db.execute(
            text(f"SELECT COUNT(*) FROM public.tenants {where}"),
            params,
        )
        total = count_result.scalar()

        result = await self.db.execute(
            text(
                f"""
                SELECT t.id, t.name, t.slug, t.status, t.max_users, t.max_documents,
                       t.max_storage_gb, t.max_model_versions, t.created_at,
                       COALESCE(dp.mode, 'platform') AS data_plane_mode,
                       COALESCE(dp.status, 'ready') AS data_plane_status,
                       COALESCE(reg.document_count, 0) AS document_count
                FROM public.tenants t
                LEFT JOIN public.tenant_data_planes dp ON dp.tenant_id = t.id
                LEFT JOIN (
                    SELECT tenant_id, COUNT(*) AS document_count
                    FROM public.tenant_document_registry
                    WHERE status != 'error'
                    GROUP BY tenant_id
                ) reg ON reg.tenant_id = t.id
                {where_qualified}
                ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset
                """
            ),
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
                "data_plane": {"mode": r.data_plane_mode, "status": r.data_plane_status},
                "document_count": r.document_count,
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

    async def deactivate_tenant(self, tenant_id: str, actor_email: str = "", actor_role: str = "") -> dict:
        existing = await self._get_by_id(tenant_id)
        if not existing:
            raise NotFoundError("Tenant", tenant_id)

        await self.db.execute(
            text("UPDATE public.tenants SET status = 'inactive' WHERE id = :id"),
            {"id": tenant_id},
        )

        audit = AuditService(self.db)
        await audit.record(
            actor=actor_email,
            role=actor_role,
            action="tenant.deactivate",
            target=existing["slug"],
            kind=AuditEventKind.reject,
        )

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

        dp_row = (
            await self.db.execute(
                text(
                    "SELECT mode, status, health_outcome FROM public.tenant_data_planes WHERE tenant_id = :id"
                ),
                {"id": tenant_id},
            )
        ).fetchone()
        data_plane = (
            {"mode": dp_row.mode, "status": dp_row.status, "health": dp_row.health_outcome}
            if dp_row is not None
            else {"mode": "platform", "status": "ready", "health": None}
        )

        # Content-free registry (Design D7) — available regardless of the
        # tenant's data-plane mode or current reachability (ADR-017, task 13.4).
        document_count = await self.db.scalar(
            text(
                "SELECT COUNT(*) FROM public.tenant_document_registry "
                "WHERE tenant_id = :id AND status != 'error'"
            ),
            {"id": tenant_id},
        )

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
            "data_plane": data_plane,
            "document_count": document_count or 0,
        }
