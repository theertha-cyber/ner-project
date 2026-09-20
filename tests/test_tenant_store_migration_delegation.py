"""Static enforcement for ADR-017 Design Decision 5 (openspec change
`single-source-tenant-ddl`): a tenant-scoped Alembic migration's `upgrade()`
must delegate its DDL to a `src/shared/tenant_store/revisions` module instead
of hand-writing it, so the same DDL reaches `tenant_owned` Azure data planes
via `migrate.py`. Migration `055_chat_messages_attachments.py` originally
shipped without doing this -- no matching revision module existed, so
`migrate.py` never applied the column to tenant-owned stores while platform
tenants got it, breaking chat for an affected tenant. This test makes that
class of gap fail the build instead of shipping silently.

Migrations that existed before this check was introduced are grandfathered
below by explicit filename -- retrofitting all ~55 of them (many predate the
`revisions/` convention entirely) is out of scope. Migration `055` itself is
NOT grandfathered: it is the motivating case and must pass for real. Every
new tenant-scoped migration added after this change must delegate or carry
an explicit exemption comment.
"""

import ast
from pathlib import Path

import pytest

VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"

EXEMPT_COMMENT_MARKER = "tenant-store-revision: exempt"

TENANT_SCOPED_DDL_MARKERS = ("tenant_template.", "pg_namespace")

REVISIONS_IMPORT_MARKERS = (
    "src.shared.tenant_store.revisions",
    "src/shared/tenant_store/revisions",
)

# Migrations 001-052 predate this check and are not required to delegate.
# 053, 054 and 055 are deliberately excluded -- they are the migrations this
# check exists for (053/054 fixed alongside 055, same bug class).
GRANDFATHERED_MIGRATIONS = frozenset(
    {
        "001_initial_schema.py",
        "002_tenant_template_schema.py",
        "003_document_service_tables.py",
        "004_annotation_service_tables.py",
        "005_training_service_tables.py",
        "006_mlflow_tracking_columns.py",
        "007_add_extraction_run_columns.py",
        "008_add_document_id_to_extracted_entities.py",
        "009_add_bio_tags_to_spans.py",
        "010_chatbot_infrastructure.py",
        "011_analytics_materialized_views.py",
        "012_reconcile_training_jobs_columns.py",
        "013_add_missing_created_at_columns.py",
        "014_add_imported_annotations_table.py",
        "015_backfill_analytics_materialized_views.py",
        "016_backfill_training_jobs_error_message.py",
        "017_add_reviewed_columns_to_imported_annotations.py",
        "018_reconcile_model_versions_columns.py",
        "019_backfill_model_versions_label_list.py",
        "020_create_audit_events_table.py",
        "021_document_chunks_page_metadata.py",
        "022_document_purpose_scoping.py",
        "023_reconcile_tenant_schemas.py",
        "024_hybrid_retrieval_hnsw.py",
        "025_add_run_number_columns.py",
        "026_document_entities.py",
        "027_conversation_entity_state.py",
        "028_entity_definition_value_kind.py",
        "029_document_entities_typed_values.py",
        "030_document_uploaded_by.py",
        "031_training_jobs_hyperparams_nullable.py",
        "032_chat_message_feedback.py",
        "033_chat_messages_response_time_ms.py",
        "034_document_checksum_index.py",
        "035_document_entities_provenance.py",
        "036_extraction_runs_processing_mode.py",
        "037_entity_definitions_view_metadata.py",
        "038_document_provenance_and_retention.py",
        "038b_llm_prelabeling_columns.py",
        "039_seed_bootstrap.py",
        "039b_tenant_integration_profiles.py",
        "040_confidence_routed_review.py",
        "041_notifications_and_training_eligibility.py",
        "042_automated_annotation_guided_workflow.py",
        "043_schema_proposal_qa_pair.py",
        "044_entity_type_provenance.py",
        "045_imported_annotation_pending_mapping.py",
        "046_training_job_source_scope.py",
        "047_chat_messages_export_rows.py",
        "048_chat_message_chart.py",
        "049_tenant_data_source_connections.py",
        "050_azure_blob_sync_ledger.py",
        "051_external_pg_contracts.py",
        "052_tenant_data_plane.py",
    }
)


def _upgrade_source(module_source: str) -> str:
    """The source text of the module's top-level `upgrade()` function, or ''
    if it has none."""
    tree = ast.parse(module_source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            segment = ast.get_source_segment(module_source, node)
            return segment or ""
    return ""


def touches_tenant_scoped_ddl(upgrade_source: str) -> bool:
    return any(marker in upgrade_source for marker in TENANT_SCOPED_DDL_MARKERS)


def delegates_to_revisions_module(module_source: str) -> bool:
    return any(marker in module_source for marker in REVISIONS_IMPORT_MARKERS)


def is_explicitly_exempt(module_source: str) -> bool:
    return EXEMPT_COMMENT_MARKER in module_source


def check_migration_source(module_source: str) -> str | None:
    """Returns a failure reason string if `module_source`'s `upgrade()` touches
    tenant-scoped DDL without delegating to a revisions module and isn't
    exempted, else `None`."""
    upgrade_source = _upgrade_source(module_source)
    if not touches_tenant_scoped_ddl(upgrade_source):
        return None
    if is_explicitly_exempt(module_source):
        return None
    if delegates_to_revisions_module(module_source):
        return None
    return (
        "upgrade() touches tenant-scoped DDL but does not import from "
        "src.shared.tenant_store.revisions. Add a matching revisions/NNNN_*.py "
        "module and delegate to it (ADR-017 Design Decision 5), or add a "
        "'# tenant-store-revision: exempt — <reason>' comment if this is "
        "intentional."
    )


def _migration_files() -> list[Path]:
    return sorted(
        p for p in VERSIONS_DIR.glob("*.py") if p.name not in ("__init__.py",)
    )


@pytest.mark.parametrize("path", _migration_files(), ids=lambda p: p.name)
def test_tenant_scoped_migration_delegates_to_revisions_module(path: Path) -> None:
    if path.name in GRANDFATHERED_MIGRATIONS:
        pytest.skip("grandfathered: predates the delegation check")

    failure = check_migration_source(path.read_text(encoding="utf-8"))
    assert failure is None, f"{path.name}: {failure}"


def test_motivating_migrations_are_not_grandfathered() -> None:
    """053-055 are the motivating cases for this check -- they must never be
    silently grandfathered even if the filename set above is regenerated carelessly."""
    assert "053_documents_conversation_id.py" not in GRANDFATHERED_MIGRATIONS
    assert "054_document_chunks_conversation_id.py" not in GRANDFATHERED_MIGRATIONS
    assert "055_chat_messages_attachments.py" not in GRANDFATHERED_MIGRATIONS


def test_check_fails_on_the_original_pre_fix_055_shape() -> None:
    """Regression test: reproduces migration 055's DDL as it shipped originally
    (hand-written SQL, no revisions import) and confirms the check flags it."""
    pre_fix_source = '''
from alembic import op

revision = "055"
down_revision = "054"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
            ADD COLUMN IF NOT EXISTS attachments JSONB
    """)
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('
                    ALTER TABLE %I.chat_messages
                        ADD COLUMN IF NOT EXISTS attachments JSONB
                ', schema_name);
            END LOOP;
        END $$;
    """)
'''
    failure = check_migration_source(pre_fix_source)
    assert failure is not None
    assert "src.shared.tenant_store.revisions" in failure


def test_check_passes_on_the_delegating_055_shape() -> None:
    delegating_source = '''
import importlib

from alembic import op
from sqlalchemy import text

revision = "055"
down_revision = "054"

_revision_003 = importlib.import_module(
    "src.shared.tenant_store.revisions.003_chat_messages_attachments"
)


def upgrade() -> None:
    bind = op.get_bind()
    for statement in _revision_003.statements("tenant_template"):
        op.execute(statement)
    schema_names = bind.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname LIKE 'tenant\\\\_%' AND nspname != 'tenant_template'"
        )
    ).scalars().all()
    for schema_name in schema_names:
        for statement in _revision_003.statements(schema_name):
            op.execute(statement)
'''
    assert check_migration_source(delegating_source) is None


def test_check_ignores_migrations_with_no_tenant_scoped_ddl() -> None:
    platform_only_source = '''
from alembic import op


def upgrade() -> None:
    op.execute("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS foo text")
'''
    assert check_migration_source(platform_only_source) is None


def test_check_honours_the_exemption_comment() -> None:
    exempt_source = '''
# tenant-store-revision: exempt — one-off backfill script, not a shape change
from alembic import op


def upgrade() -> None:
    op.execute("ALTER TABLE tenant_template.foo ADD COLUMN IF NOT EXISTS bar text")
'''
    assert check_migration_source(exempt_source) is None


def test_check_ignores_downgrade_only_ddl() -> None:
    """`downgrade()` is never scanned -- the revisions/ system has no downgrade
    path, so there is nothing for a hand-written downgrade to drift against."""
    upgrade_only_source = '''
import importlib

_revision_099 = importlib.import_module(
    "src.shared.tenant_store.revisions.099_example"
)


def upgrade() -> None:
    for statement in _revision_099.statements("tenant_template"):
        pass


def downgrade() -> None:
    op.execute("ALTER TABLE tenant_template.foo DROP COLUMN IF EXISTS bar")
'''
    assert check_migration_source(upgrade_only_source) is None
