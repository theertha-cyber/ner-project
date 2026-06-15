import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


class TrainingJobRepository:

    @staticmethod
    async def create(session: AsyncSession, tenant_id: str, job_id: str, hyperparams: dict, celery_task_id: str | None = None) -> dict:
        schema = _schema(tenant_id)
        now = datetime.now(timezone.utc)
        await session.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, celery_task_id, created_at)
                VALUES (:id, :tenant_id, 'pending_approval', CAST(:hyperparams AS jsonb), :celery_task_id, :created_at)
            """),
            {"id": job_id, "tenant_id": tenant_id, "hyperparams": json.dumps(hyperparams), "celery_task_id": celery_task_id, "created_at": now},
        )
        await session.commit()
        return {"id": job_id, "tenant_id": tenant_id, "status": "pending_approval", "hyperparams": hyperparams, "celery_task_id": celery_task_id}

    @staticmethod
    async def get_by_id(session: AsyncSession, tenant_id: str, job_id: str) -> dict | None:
        schema = _schema(tenant_id)
        result = await session.execute(
            text(f"SELECT * FROM {schema}.training_jobs WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": job_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return dict(row._mapping)

    @staticmethod
    async def list_by_tenant(session: AsyncSession, tenant_id: str, status_filter: str | None = None, page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
        schema = _schema(tenant_id)
        conditions = "tenant_id = :tenant_id"
        params = {"tenant_id": tenant_id}
        if status_filter:
            conditions += " AND status = :status"
            params["status"] = status_filter

        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM {schema}.training_jobs WHERE {conditions}"),
            params,
        )
        total = count_result.scalar()

        offset = (page - 1) * per_page
        result = await session.execute(
            text(f"SELECT * FROM {schema}.training_jobs WHERE {conditions} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            {**params, "limit": per_page, "offset": offset},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]
        return rows, total

    @staticmethod
    async def update_status(session: AsyncSession, tenant_id: str, job_id: str, status: str, **extra) -> None:
        schema = _schema(tenant_id)
        set_clauses = ["status = :status"]
        field_map = {"status": status}
        for key, val in extra.items():
            set_clauses.append(f"{key} = :{key}")
            field_map[key] = val
        set_sql = ", ".join(set_clauses)
        field_map["id"] = job_id
        field_map["tenant_id"] = tenant_id
        await session.execute(
            text(f"UPDATE {schema}.training_jobs SET {set_sql} WHERE id = :id AND tenant_id = :tenant_id"),
            field_map,
        )
        await session.commit()


class ModelVersionRepository:

    @staticmethod
    async def create(session: AsyncSession, tenant_id: str, version_id: str, version_number: int, training_job_id: str) -> dict:
        schema = _schema(tenant_id)
        now = datetime.now(timezone.utc)
        await session.execute(
            text(f"""
                INSERT INTO {schema}.model_versions (id, tenant_id, version_number, training_job_id, status, created_at)
                VALUES (:id, :tenant_id, :version_number, :training_job_id, 'training', :created_at)
            """),
            {"id": version_id, "tenant_id": tenant_id, "version_number": version_number, "training_job_id": training_job_id, "created_at": now},
        )
        await session.commit()
        return {"id": version_id, "tenant_id": tenant_id, "version_number": version_number, "training_job_id": training_job_id, "status": "training"}

    @staticmethod
    async def get_by_id(session: AsyncSession, tenant_id: str, version_id: str) -> dict | None:
        schema = _schema(tenant_id)
        result = await session.execute(
            text(f"SELECT * FROM {schema}.model_versions WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": version_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return dict(row._mapping)

    @staticmethod
    async def list_by_tenant(session: AsyncSession, tenant_id: str) -> list[dict]:
        schema = _schema(tenant_id)
        result = await session.execute(
            text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tenant_id ORDER BY version_number DESC"),
            {"tenant_id": tenant_id},
        )
        return [dict(r._mapping) for r in result.fetchall()]

    @staticmethod
    async def update_status(session: AsyncSession, tenant_id: str, version_id: str, status: str, **extra) -> None:
        schema = _schema(tenant_id)
        set_clauses = ["status = :status"]
        field_map = {"status": status}
        for key, val in extra.items():
            set_clauses.append(f"{key} = :{key}")
            field_map[key] = val
        set_sql = ", ".join(set_clauses)
        field_map["id"] = version_id
        field_map["tenant_id"] = tenant_id
        await session.execute(
            text(f"UPDATE {schema}.model_versions SET {set_sql} WHERE id = :id AND tenant_id = :tenant_id"),
            field_map,
        )
        await session.commit()

    @staticmethod
    async def get_active(session: AsyncSession, tenant_id: str) -> dict | None:
        schema = _schema(tenant_id)
        result = await session.execute(
            text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tenant_id AND status = 'promoted' ORDER BY version_number DESC LIMIT 1"),
            {"tenant_id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return dict(row._mapping)

    @staticmethod
    async def get_next_version_number(session: AsyncSession, tenant_id: str) -> int:
        schema = _schema(tenant_id)
        result = await session.execute(
            text(f"SELECT COALESCE(MAX(version_number), 0) + 1 FROM {schema}.model_versions WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        return result.scalar()
