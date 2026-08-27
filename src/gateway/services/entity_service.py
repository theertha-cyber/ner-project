import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.gateway.models import generate_uuid, validate_base_label_mapping
from src.extraction_service.services.semantic_normalizer import SUPPORTED_KINDS
from src.shared.entity_views import (
    CARDINALITIES,
    CARDINALITY_MULTI,
    load_definition_specs,
    reconcile_entity_tables,
    schema_for_tenant,
    to_sql_identifier,
)
from src.shared.exceptions import ValidationError, NotFoundError

# Every read path selects the same column list. Stated once so a column added to one cannot be
# missing from the other — which is how `cardinality` stayed invisible to the UI after `037`
# added it.
_ENTITY_COLUMNS = """
    id, name, description, examples, validation_rule, target_table,
    base_label_mapping, value_kind, value_unit, cardinality, sql_identifier,
    version, required_flag, is_active, created_at, updated_at
"""


def _validate_value_kind(value_kind) -> str | None:
    if value_kind is None:
        return None
    if value_kind not in SUPPORTED_KINDS:
        return f"value_kind must be one of {sorted(SUPPORTED_KINDS)}, got '{value_kind}'"
    return None


def _validate_cardinality(cardinality) -> str | None:
    """Rejected here, before the write. Migration `037`'s CHECK constraint is the backstop, and
    reaching it would surface as a 500 on what is really a malformed request."""
    if cardinality is None:
        return None
    if cardinality not in CARDINALITIES:
        return (
            f"cardinality must be one of {sorted(CARDINALITIES)}, got '{cardinality}'"
        )
    return None


class EntityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _taken_identifiers(self, tenant_id: str) -> set[str]:
        """The tenant's already-assigned `sql_identifier` values.

        Per-tenant, not global: generated tables live in separate tenant schemas (ADR-001), so
        two tenants sharing `e_skill` is correct rather than a collision, and the partial unique
        index `037` creates is on `(tenant_id, sql_identifier)`."""
        result = await self.db.execute(
            text(
                "SELECT sql_identifier FROM public.entity_definitions "
                "WHERE tenant_id = :tid AND sql_identifier IS NOT NULL"
            ),
            {"tid": tenant_id},
        )
        return {row[0] for row in result.fetchall()}

    async def _reconcile(self, tenant_id: str) -> None:
        """Bring the tenant's generated tables in line with the catalog it just changed.

        Called from all four write paths, in that call's own transaction, so a definition and
        the relation it describes can never be committed apart. Never drops anything: `is_active`
        is a reversible flag, so deactivation stops projection and leaves the table and its rows
        alone. Run-start reconciliation in the extraction worker is the safety net that covers a
        tenant these paths never fired for."""
        specs = await load_definition_specs(self.db, tenant_id)
        await reconcile_entity_tables(self.db, schema_for_tenant(tenant_id), specs)

    async def create_entity_type(self, tenant_id: str, payload: dict) -> dict:
        mapping = payload.get("base_label_mapping")
        validation_error = validate_base_label_mapping(mapping)
        if validation_error:
            raise ValidationError(validation_error)

        value_kind_error = _validate_value_kind(payload.get("value_kind"))
        if value_kind_error:
            raise ValidationError(value_kind_error)

        cardinality_error = _validate_cardinality(payload.get("cardinality"))
        if cardinality_error:
            raise ValidationError(cardinality_error)

        entity_id = generate_uuid()
        # Assigned here, once, and never changed afterwards. Omitting it — as this INSERT did
        # until now — leaves `sql_identifier` NULL, and a NULL-identifier definition is skipped
        # by both the reconciler and the projection: the entity type extracts into
        # `document_entities` normally while being absent from the entire relational query
        # surface, with no error anywhere. `to_sql_identifier` is imported rather than
        # reimplemented so this and migration `037`'s backfill cannot disagree about a name.
        sql_identifier = to_sql_identifier(
            payload["name"], await self._taken_identifiers(tenant_id)
        )
        await self.db.execute(
            text("""
                INSERT INTO public.entity_definitions
                    (id, tenant_id, name, description, examples, validation_rule,
                     target_table, base_label_mapping, value_kind, value_unit, cardinality,
                     sql_identifier, required_flag, is_active, version)
                VALUES (:id, :tid, :name, :desc, :examples, :rule,
                        :target, :mapping, :value_kind, :value_unit, :cardinality,
                        :sql_identifier, :required, :active, 1)
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
                "value_kind": payload.get("value_kind"),
                "value_unit": payload.get("value_unit"),
                # `multi` is the default because a genuinely multi-valued entity rendered as a
                # child table is always correct, whereas a multi-valued entity marked `single`
                # silently discards every value but one from the query surface.
                "cardinality": payload.get("cardinality") or CARDINALITY_MULTI,
                "sql_identifier": sql_identifier,
                "active": payload.get("is_active", True),
                "required": payload.get("required_flag", False),
            },
        )
        await self._reconcile(tenant_id)
        await self.db.commit()

        return await self._get_by_name(tenant_id, payload["name"])

    async def list_entity_types(self, tenant_id: str, is_active: bool | None = None) -> dict:
        conditions = ["tenant_id = :tid"]
        params = {"tid": tenant_id}
        if is_active is not None:
            conditions.append("is_active = :active")
            params["active"] = is_active

        where = " AND ".join(conditions)
        result = await self.db.execute(
            text(f"""
                SELECT {_ENTITY_COLUMNS}
                FROM public.entity_definitions WHERE {where}
                ORDER BY created_at DESC
            """),
            params,
        )
        rows = result.fetchall()
        entities = [self._row_to_dict(r) for r in rows]
        return {"entity_types": entities}

    async def get_entity_type(self, tenant_id: str, name: str) -> dict:
        data = await self._get_by_name(tenant_id, name)
        if not data:
            raise NotFoundError("EntityType", name)
        return data

    async def update_entity_type(self, tenant_id: str, name: str, payload: dict) -> dict:
        existing = await self._get_by_name(tenant_id, name)
        if not existing:
            raise NotFoundError("EntityType", name)

        mapping = payload.get("base_label_mapping", existing.get("base_label_mapping"))
        if mapping is not None:
            validation_error = validate_base_label_mapping(mapping)
            if validation_error:
                raise ValidationError(validation_error)

        if "value_kind" in payload:
            value_kind_error = _validate_value_kind(payload.get("value_kind"))
            if value_kind_error:
                raise ValidationError(value_kind_error)

        if "cardinality" in payload:
            cardinality_error = _validate_cardinality(payload.get("cardinality"))
            if cardinality_error:
                raise ValidationError(cardinality_error)

        # `sql_identifier` is deliberately absent: it is assigned once at create and never
        # changed, so renaming an entity type's display name cannot rename its table, break a
        # saved query, or orphan the old one.
        allowed_fields = {
            "description", "examples", "validation_rule", "target_table",
            "base_label_mapping", "required_flag", "value_kind", "value_unit",
            "cardinality",
        }
        updates = {k: v for k, v in payload.items() if k in allowed_fields}

        if updates:
            if "base_label_mapping" in updates and isinstance(updates["base_label_mapping"], dict):
                updates["base_label_mapping"] = json.dumps(updates["base_label_mapping"])
            if "examples" in updates and updates["examples"] is not None:
                updates["examples"] = json.dumps(updates["examples"])
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            updates["name"] = name
            updates["tid"] = tenant_id
            await self.db.execute(
                text(f"UPDATE public.entity_definitions SET version = version + 1, {set_clause} WHERE name = :name AND tenant_id = :tid"),
                updates,
            )
            # `cardinality` or `value_kind` may have changed, which moves where the entity
            # type's values are queried from. Neither representation is migrated and neither is
            # dropped: the old relation keeps its rows and the new one starts empty until the
            # affected documents are re-extracted.
            await self._reconcile(tenant_id)
            await self.db.commit()

        return await self._get_by_name(tenant_id, name)

    async def toggle_entity_type(self, tenant_id: str, name: str, is_active: bool) -> dict:
        existing = await self._get_by_name(tenant_id, name)
        if not existing:
            raise NotFoundError("EntityType", name)

        await self.db.execute(
            text("UPDATE public.entity_definitions SET is_active = :active WHERE name = :name AND tenant_id = :tid"),
            {"active": is_active, "name": name, "tid": tenant_id},
        )
        await self._reconcile(tenant_id)
        await self.db.commit()

        return await self._get_by_name(tenant_id, name)

    async def soft_delete_entity_type(self, tenant_id: str, name: str) -> dict:
        existing = await self._get_by_name(tenant_id, name)
        if not existing:
            raise NotFoundError("EntityType", name)

        await self.db.execute(
            text("UPDATE public.entity_definitions SET is_active = false WHERE name = :name AND tenant_id = :tid"),
            {"name": name, "tid": tenant_id},
        )
        # There is no hard delete for an entity type, only this flag, and `toggle_entity_type`
        # flips it back. Reconciling here therefore must not drop the table — doing so would
        # turn an undo button into a data-loss event.
        await self._reconcile(tenant_id)
        await self.db.commit()

        return await self._get_by_name(tenant_id, name)

    async def _get_by_name(self, tenant_id: str, name: str) -> dict | None:
        result = await self.db.execute(
            text(f"""
                SELECT {_ENTITY_COLUMNS}
                FROM public.entity_definitions
                WHERE name = :name AND tenant_id = :tid
            """),
            {"name": name, "tid": tenant_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def _row_to_dict(self, r) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "examples": json.loads(r.examples) if isinstance(r.examples, str) else (r.examples or []),
            "validation_rule": r.validation_rule,
            "target_table": r.target_table,
            "base_label_mapping": json.loads(r.base_label_mapping) if isinstance(r.base_label_mapping, str) else (r.base_label_mapping or {}),
            "value_kind": r.value_kind or "text",
            "value_unit": r.value_unit,
            # Returned on every read path: without it the edit form cannot show an entity
            # type's persisted cardinality and silently resets it to the default on every save.
            "cardinality": r.cardinality or CARDINALITY_MULTI,
            # Read-only metadata. A client-supplied value is ignored rather than rejected —
            # see the create and update paths, which never read it from the payload.
            "sql_identifier": r.sql_identifier,
            "version": r.version,
            "required_flag": r.required_flag,
            "is_active": r.is_active,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        }
