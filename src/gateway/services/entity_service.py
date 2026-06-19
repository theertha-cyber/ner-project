import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import generate_uuid, validate_base_label_mapping
from src.shared.exceptions import ValidationError, NotFoundError


class EntityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_entity_type(self, tenant_id: str, payload: dict) -> dict:
        mapping = payload.get("base_label_mapping")
        validation_error = validate_base_label_mapping(mapping)
        if validation_error:
            raise ValidationError(validation_error)

        entity_id = generate_uuid()
        await self.db.execute(
            text("""
                INSERT INTO public.entity_definitions
                    (id, tenant_id, name, description, examples, validation_rule,
                     target_table, base_label_mapping, required_flag, version)
                VALUES (:id, :tid, :name, :desc, :examples, :rule,
                        :target, :mapping, :required, 1)
            """),
            {
                "id": entity_id,
                "tid": tenant_id,
                "name": payload["name"],
                "desc": payload.get("description"),
                "examples": json.dumps(payload.get("examples")) if payload.get("examples") is not None else None,
                "rule": payload.get("validation_rule"),
                "target": payload.get("target_table"),
                "mapping": json.dumps(mapping) if isinstance(mapping, dict) else mapping,
                "required": payload.get("required_flag", False),
            },
        )
        await self.db.commit()

        return await self._get_by_id(tenant_id, entity_id)

    async def list_entity_types(self, tenant_id: str, is_active: bool | None = None) -> dict:
        conditions = ["tenant_id = :tid"]
        params = {"tid": tenant_id}
        if is_active is not None:
            conditions.append("is_active = :active")
            params["active"] = is_active

        where = " AND ".join(conditions)
        result = await self.db.execute(
            text(f"""
                SELECT id, name, description, examples, validation_rule, target_table,
                       base_label_mapping, version, required_flag, is_active, created_at, updated_at
                FROM public.entity_definitions WHERE {where}
                ORDER BY created_at DESC
            """),
            params,
        )
        rows = result.fetchall()
        entities = [self._row_to_dict(r) for r in rows]
        return {"entity_types": entities}

    async def get_entity_type(self, tenant_id: str, entity_id: str) -> dict:
        data = await self._get_by_id(tenant_id, entity_id)
        if not data:
            raise NotFoundError("EntityType", entity_id)
        return data

    async def update_entity_type(self, tenant_id: str, entity_id: str, payload: dict) -> dict:
        existing = await self._get_by_id(tenant_id, entity_id)
        if not existing:
            raise NotFoundError("EntityType", entity_id)

        mapping = payload.get("base_label_mapping", existing["entity_type"].get("base_label_mapping"))
        if mapping is not None:
            validation_error = validate_base_label_mapping(mapping)
            if validation_error:
                raise ValidationError(validation_error)

        allowed_fields = {
            "description", "examples", "validation_rule", "target_table",
            "base_label_mapping", "required_flag",
        }
        updates = {k: v for k, v in payload.items() if k in allowed_fields}
        if "name" in payload:
            updates["name"] = payload["name"]

        if updates:
            if "base_label_mapping" in updates and isinstance(updates["base_label_mapping"], dict):
                updates["base_label_mapping"] = json.dumps(updates["base_label_mapping"])
            if "examples" in updates and updates["examples"] is not None:
                updates["examples"] = json.dumps(updates["examples"])
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["id"] = entity_id
            await self.db.execute(
                text(f"UPDATE public.entity_definitions SET version = version + 1, {set_clause} WHERE id = :id"),
                updates,
            )
            await self.db.commit()

        return await self._get_by_id(tenant_id, entity_id)

    async def soft_delete_entity_type(self, tenant_id: str, entity_id: str) -> dict:
        existing = await self._get_by_id(tenant_id, entity_id)
        if not existing:
            raise NotFoundError("EntityType", entity_id)

        await self.db.execute(
            text("UPDATE public.entity_definitions SET is_active = false WHERE id = :id"),
            {"id": entity_id},
        )
        await self.db.commit()

        return await self._get_by_id(tenant_id, entity_id)

    async def _get_by_id(self, tenant_id: str, entity_id: str) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT id, name, description, examples, validation_rule, target_table,
                       base_label_mapping, version, required_flag, is_active, created_at, updated_at
                FROM public.entity_definitions
                WHERE id = :id AND tenant_id = :tid
            """),
            {"id": entity_id, "tid": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {"entity_type": self._row_to_dict(row)}

    def _row_to_dict(self, r) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "examples": r.examples,
            "validation_rule": r.validation_rule,
            "target_table": r.target_table,
            "base_label_mapping": r.base_label_mapping,
            "version": r.version,
            "required_flag": r.required_flag,
            "is_active": r.is_active,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        }
