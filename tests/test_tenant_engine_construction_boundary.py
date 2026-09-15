"""Source checks for the tenant-data-plane-routing spec's scenario #7: "Workers use the
resolver" — no tenant-schema access constructs an engine from the platform database URL
directly, and no SQL executed on a tenant session references `public.*` (Design D10).

These are architecture tests, not behavioural ones: they grep `src/` so a future PR that
reintroduces `create_engine(settings.database_url_sync)` for tenant data, or a
`public.*` join inside a tenant-session query, fails CI immediately rather than
surfacing later as a silent platform-database write for a `tenant_owned` tenant.
"""

import re
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

# Files allowed to construct an engine directly from the platform database URL — every
# one is either the resolver itself, or a deploy-time / control-plane-only bootstrap
# that never touches a tenant schema (Design D4's alternative-considered allowlist:
# "database.py, seed.py, verify_schema.py, and MLflow bootstrap").
ALLOWLISTED_DIRECT_ENGINE_FILES = {
    SRC_ROOT / "shared" / "database.py",
    SRC_ROOT / "shared" / "tenant_store" / "migrate.py",
    SRC_ROOT / "gateway" / "seed.py",
    SRC_ROOT / "gateway" / "verify_schema.py",
}

_DIRECT_ENGINE_RE = re.compile(
    r"create_(?:async_)?engine\(\s*settings\.database_url(?:_sync)?\b"
)

# A SQL string that references BOTH a tenant schema placeholder and `public.` in the
# same statement — the exact shape of the `documents.py` uploader-join defect Design
# D10 names. Scoped to text(f"""...""") / text(f"...") blocks so it does not flag a
# file that happens to have unrelated public.* and {schema}. queries nearby.
_TEXT_BLOCK_RE = re.compile(r'text\(\s*f?"""(.*?)"""\s*\)', re.DOTALL)
_TEXT_BLOCK_RE_SINGLELINE = re.compile(r'text\(\s*f"([^"\n]*)"\s*\)')
_SCHEMA_PLACEHOLDER_RE = re.compile(r"\{schema\}|\{_schema\(|\{schema_for_tenant\(")
_PUBLIC_REF_RE = re.compile(r"\bpublic\.")


def _iter_py_files():
    return sorted(SRC_ROOT.rglob("*.py"))


def test_no_direct_platform_engine_construction_outside_allowlist():
    offenders = []
    for path in _iter_py_files():
        if path in ALLOWLISTED_DIRECT_ENGINE_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _DIRECT_ENGINE_RE.search(line):
                offenders.append(f"{path.relative_to(SRC_ROOT.parent)}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "Direct engine construction from settings.database_url(_sync) outside the "
        "allowlisted files (tenant-schema access must route through "
        "EngineResolver):\n" + "\n".join(offenders)
    )


def test_no_cross_schema_public_join_in_tenant_session_sql():
    offenders = []
    for path in _iter_py_files():
        text = path.read_text(encoding="utf-8")
        blocks = _TEXT_BLOCK_RE.findall(text) + _TEXT_BLOCK_RE_SINGLELINE.findall(text)
        for block in blocks:
            if _SCHEMA_PLACEHOLDER_RE.search(block) and _PUBLIC_REF_RE.search(block):
                offenders.append(f"{path.relative_to(SRC_ROOT.parent)}: {block.strip()[:120]}")
    assert offenders == [], (
        "SQL referencing both a tenant schema placeholder and `public.` in the same "
        "statement (Design D10 — split into a separate control-plane lookup):\n"
        + "\n".join(offenders)
    )


def test_allowlist_files_actually_exist():
    """Guards the allowlist itself against typos/renames going stale."""
    missing = [str(p) for p in ALLOWLISTED_DIRECT_ENGINE_FILES if not p.exists()]
    assert missing == [], f"Allowlisted files no longer exist: {missing}"
