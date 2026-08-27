"""`load_entity_definition_specs` — the catalog read the relational projection routes on.

A sibling of `load_entity_type_config` rather than a widening of it: that function's
`dict[str, EntityTypeConfig]` return type is consumed by `apply_semantic_normalization` and
`postprocess_document`, neither of which has any interest in `cardinality` or `sql_identifier`.

Covers verification.md row 35 and task 3.3.
"""

import uuid

import pytest
from sqlalchemy import create_engine, text

from src.extraction_service.services.semantic_normalizer import load_entity_definition_specs
from src.shared.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


def _insert(conn, tenant_id, name, **columns):
    conn.execute(
        text(
            "INSERT INTO public.entity_definitions "
            "(id, tenant_id, name, sql_identifier, cardinality, value_kind, is_active, "
            " base_label_mapping, version) "
            "VALUES (:id, :tid, :name, :identifier, :cardinality, :value_kind, :active, "
            "        :mapping, 1)"
        ),
        {
            "id": str(uuid.uuid4()),
            "tid": tenant_id,
            "name": name,
            "identifier": columns.get("sql_identifier"),
            "cardinality": columns.get("cardinality", "multi"),
            "value_kind": columns.get("value_kind"),
            "active": columns.get("is_active", True),
            "mapping": columns.get("base_label_mapping"),
        },
    )


@pytest.fixture
def catalog(sync_engine, setup_database):
    """Two tenants' definitions, including one row the loader must refuse to render."""
    tenant = f"loader-{uuid.uuid4().hex[:8]}"
    other = f"loader-other-{uuid.uuid4().hex[:8]}"
    with sync_engine.begin() as conn:
        for tid in (tenant, other):
            conn.execute(
                text(
                    "INSERT INTO public.tenants "
                    "(id, name, slug, status, max_users, max_documents, max_storage_gb, "
                    " max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
        _insert(conn, tenant, "SKILL", sql_identifier="e_skill")
        _insert(
            conn,
            tenant,
            "EMAIL",
            sql_identifier="e_email",
            cardinality="single",
            value_kind="text",
        )
        _insert(
            conn,
            tenant,
            "Employer",
            sql_identifier="e_employer",
            base_label_mapping='{"ORG": ["employer"]}',
        )
        _insert(conn, tenant, "RETIRED", sql_identifier="e_retired", is_active=False)
        # Created before `037`'s backfill, or by a create path that forgot to assign one.
        _insert(conn, tenant, "UNASSIGNED", sql_identifier=None)
        _insert(conn, other, "OTHER_TENANT_TYPE", sql_identifier="e_aaa_other")
    yield tenant, other
    with sync_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id IN (:a, :b)"),
            {"a": tenant, "b": other},
        )
        conn.execute(
            text("DELETE FROM public.tenants WHERE id IN (:a, :b)"),
            {"a": tenant, "b": other},
        )


async def test_returns_only_the_requested_tenants_definitions(sync_engine, catalog):
    tenant, _other = catalog
    with sync_engine.connect() as conn:
        specs = load_entity_definition_specs(conn, tenant)
    assert {s.name for s in specs} == {"SKILL", "EMAIL", "Employer", "RETIRED"}


async def test_null_identifier_rows_are_omitted(sync_engine, catalog):
    # Skipped rather than slugged: a read-time slug is not stable across processes, so two
    # workers could create tables under different names for the same entity type.
    tenant, _other = catalog
    with sync_engine.connect() as conn:
        specs = load_entity_definition_specs(conn, tenant)
    assert "UNASSIGNED" not in {s.name for s in specs}
    assert all(s.sql_identifier for s in specs)


async def test_inactive_definitions_are_still_returned(sync_engine, catalog):
    # Deactivation excludes a definition from projection and from the query surface, but the
    # delete path needs to know its table exists so a re-extraction clears its stale rows.
    tenant, _other = catalog
    with sync_engine.connect() as conn:
        specs = load_entity_definition_specs(conn, tenant)
    retired = next(s for s in specs if s.name == "RETIRED")
    assert retired.is_active is False


async def test_ordering_is_deterministic_by_sql_identifier(sync_engine, catalog):
    tenant, _other = catalog
    with sync_engine.connect() as conn:
        first = load_entity_definition_specs(conn, tenant)
        second = load_entity_definition_specs(conn, tenant)
    identifiers = [s.sql_identifier for s in first]
    assert identifiers == sorted(identifiers)
    assert identifiers == [s.sql_identifier for s in second]


async def test_catalog_fields_round_trip(sync_engine, catalog):
    tenant, _other = catalog
    with sync_engine.connect() as conn:
        specs = {s.name: s for s in load_entity_definition_specs(conn, tenant)}

    assert specs["EMAIL"].cardinality == "single"
    assert specs["EMAIL"].value_kind == "text"
    assert specs["SKILL"].cardinality == "multi"
    # The mapping is what routes a base-model tenant's CoNLL labels; a string that never
    # became a dict would empty that tenant's whole query surface with no error.
    assert specs["Employer"].base_label_mapping == {"ORG": ["employer"]}
