"""masking suggestion sources

Widens `{tenant_schema}.suggested_spans`'s `ck_suggested_spans_source` CHECK constraint (added
in `038b`) from `('keyword', 'llm')` to also allow `'pattern'` and `'local_model'` — the two new
sources `automated-annotation-pii-masking` writes for spans found by local detection (a
`pattern`-sensitivity entity type's `validation_rule` regex, or the tenant's own locally-hosted
extraction model for a `local_only`-sensitivity type) rather than by the external LLM. `038b`'s
own comment anticipated exactly this: "a BERT-backed source is planned for a later change in
this same plan."

VARCHAR + CHECK, not a new ENUM, for the same reason `038b` chose it over one: the vocabulary
here is expected to grow, and adding a value to a Postgres ENUM is itself a migration.

Applied via `apply_to_all_tenant_schemas`, the same mechanism and same schema set `038b` used
(`tenant_template` included, so every tenant provisioned after this migration inherits the
widened constraint with no separate provisioning change).

Additive and reversible: `downgrade` restores the narrower constraint. A `pattern`- or
`local_model`-sourced row written under the new code would fail the restored constraint on a
future write, so — mirroring `038b`'s own caveat — downgrade should only be performed after
confirming no such rows exist.

Revision ID: 054
Revises: 053
Create Date: 2026-09-17

NOTE (renumbered 2026-09-18): originally revision "050" (down_revision "049"), renumbered ahead
of the main merge to resolve a collision with 050_azure_blob_sync_ledger.py.
"""
from alembic import op

from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None

_OLD_SOURCES = ("keyword", "llm")
_NEW_SOURCES = ("keyword", "llm", "pattern", "local_model")

_OLD_VALUES = ", ".join(f"'{value}'" for value in _OLD_SOURCES)
_NEW_VALUES = ", ".join(f"'{value}'" for value in _NEW_SOURCES)

_WIDEN_CHECK = (
    "ALTER TABLE {schema}.suggested_spans "
    "DROP CONSTRAINT IF EXISTS ck_suggested_spans_source, "
    f"ADD CONSTRAINT ck_suggested_spans_source CHECK (source IN ({_NEW_VALUES}))"
)

_NARROW_CHECK = (
    "ALTER TABLE {schema}.suggested_spans "
    "DROP CONSTRAINT IF EXISTS ck_suggested_spans_source, "
    f"ADD CONSTRAINT ck_suggested_spans_source CHECK (source IN ({_OLD_VALUES}))"
)


def upgrade() -> None:
    apply_to_all_tenant_schemas(op, _WIDEN_CHECK)


def downgrade() -> None:
    apply_to_all_tenant_schemas(op, _NARROW_CHECK)
