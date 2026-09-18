"""The tenant-store revision interface (ADR-017, Design D5).

A revision is a module in this package named `NNNN_<name>.py` exposing:

    REVISION: int                                  # unique, strictly increasing
    def statements(schema: str) -> list[str]: ...  # idempotent DDL, like baseline.py

Every Alembic migration that changes a tenant-scoped table ships a matching revision
here in the same PR — `tests/test_tenant_store_parity.py` fails the build otherwise.
The tenant-scoped Alembic migration then calls this module's `statements()` inside its
own `tenant_template` + `pg_namespace` loop, so the DDL exists in exactly one place.

"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from src.shared.tenant_store.baseline import BASELINE_REVISION

# A store below this revision fails closed for content routes (`migration_required`)
# until a later `migrate.py` run brings it current. Bumped only when an old revision is
# retired (its DDL folded into a later one, or the data it wrote is no longer read) —
# never on every new revision, which would force every store current on every deploy.
MIN_SUPPORTED_TENANT_STORE_REVISION = BASELINE_REVISION


def _discover() -> list[ModuleType]:
    import src.shared.tenant_store.revisions as pkg

    modules = []
    for _, name, is_pkg in pkgutil.iter_modules(pkg.__path__):
        if is_pkg or name.startswith("_"):
            continue
        modules.append(importlib.import_module(f"{pkg.__name__}.{name}"))
    return sorted(modules, key=lambda m: m.REVISION)


def all_revisions() -> list[ModuleType]:
    return _discover()


def pending_revisions(current_revision: int) -> list[ModuleType]:
    return [m for m in _discover() if m.REVISION > current_revision]


def latest_revision() -> int:
    modules = _discover()
    return max((m.REVISION for m in modules), default=BASELINE_REVISION)
