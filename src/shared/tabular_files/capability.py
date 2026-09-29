"""Server-side tabular-file capability resolution (tabular-file-chat spec).

Answers one question per chat turn: which of this authenticated tenant's
uploaded files are `ready` right now, and under which served contracts? Only
the tenant id from the authenticated context is authority. `session` must be a
**platform** session (Design D10) — the tables are `public.*`, and a
`tenant_owned` tenant's resolved session has none.
"""

from __future__ import annotations

import logging

from src.shared.config import settings
from src.shared.tabular_files.store import ready_contracts

logger = logging.getLogger(__name__)

NOT_EXECUTABLE = "not_executable"


async def resolve_tabular_capability(session, tenant_id: str) -> dict:
    """Returns ``{"executable": True, "files": [served, ...]}`` or
    ``{"executable": False, "reason": "not_executable"}``. Never raises for the
    absence of files. With the kill switch off it returns non-executable
    without reading any table."""
    if not settings.tabular_files_enabled:
        return {"executable": False, "reason": NOT_EXECUTABLE}
    files = await ready_contracts(session, tenant_id)
    if not files:
        return {"executable": False, "reason": NOT_EXECUTABLE}
    logger.info("tabular_capability_resolved", extra={"executable": True, "files": len(files)})
    return {"executable": True, "files": files}


def validation_contract(files: list[dict]) -> dict:
    """The `validate_statement` contract: every served relation with its
    included columns, and no joins — so any multi-relation statement is
    `unapproved_join` (ADR-018 decision 5)."""
    relations = {}
    for served in files:
        contract = served["contract"]
        relations[contract["relation"]] = {
            "columns": [c["name"] for c in contract["columns"]],
            "description": contract.get("description"),
            "column_descriptions": {c["name"]: c.get("description") for c in contract["columns"]
                                    if c.get("description")},
        }
    return {"relations": relations, "joins": []}


def relation_index(files: list[dict]) -> dict[str, dict]:
    """Relation name to its served file record."""
    return {served["contract"]["relation"]: served for served in files}
