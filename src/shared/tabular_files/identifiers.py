"""SQL-safe identifiers from spreadsheet headers (tabular-file-ingestion spec).

Lowercase, runs of non-alphanumerics to `_`, trim `_`, `c_` prefix when the
result is empty, starts with a digit, or is a reserved word, truncate to 63
characters, then de-duplicate with `_2`, `_3`, ... The original header is kept
by the caller as the display label. Table names follow the same rules.
"""

from __future__ import annotations

import re

MAX_IDENTIFIER_LENGTH = 63

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# SQL keywords that would need quoting in PostgreSQL or DuckDB, plus the ones the
# validator's grammar treats as clause keywords. A header that sanitizes to one of
# these gets the `c_` prefix so a generated statement never needs a quoted name.
RESERVED_WORDS = frozenset({
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "asymmetric",
    "attach", "between", "both", "by", "call", "case", "cast", "check", "collate",
    "column", "constraint", "copy", "create", "cross", "current_catalog",
    "current_date", "current_role", "current_schema", "current_time",
    "current_timestamp", "current_user", "default", "deferrable", "delete", "desc",
    "describe", "detach", "distinct", "do", "drop", "else", "end", "except",
    "exists", "false", "fetch", "for", "foreign", "from", "full", "grant", "group",
    "having", "ilike", "in", "initially", "inner", "insert", "install", "intersect",
    "into", "is", "join", "lateral", "leading", "left", "like", "limit", "load",
    "localtime", "localtimestamp", "not", "null", "offset", "on", "only", "or",
    "order", "outer", "over", "partition", "placing", "pragma", "primary",
    "qualify", "references", "returning", "right", "select", "session_user", "set",
    "similar", "some", "symmetric", "table", "then", "to", "trailing", "true",
    "union", "unique", "update", "user", "using", "variadic", "when", "where",
    "window", "with",
})


def sanitize_identifier(header) -> str:
    """One header to one identifier, without de-duplication."""
    value = "" if header is None else str(header)
    value = _NON_ALNUM_RE.sub("_", value.strip().lower()).strip("_")
    if not value:
        return "c_column"
    if value[0].isdigit() or value in RESERVED_WORDS:
        value = f"c_{value}"
    return value[:MAX_IDENTIFIER_LENGTH].rstrip("_")


def sanitize_all(headers) -> list[str]:
    """Sanitizes a header row and de-duplicates in order with `_2`, `_3`, ..."""
    seen: set[str] = set()
    identifiers: list[str] = []
    for header in headers:
        base = sanitize_identifier(header)
        candidate = base
        n = 2
        while candidate in seen:
            suffix = f"_{n}"
            candidate = base[: MAX_IDENTIFIER_LENGTH - len(suffix)] + suffix
            n += 1
        seen.add(candidate)
        identifiers.append(candidate)
    return identifiers


def is_valid_identifier(value) -> bool:
    """Whether an administrator-supplied identifier is already in canonical
    sanitized form (the review endpoint refuses anything else)."""
    return (
        isinstance(value, str)
        and bool(IDENTIFIER_RE.match(value))
        and value not in RESERVED_WORDS
        and sanitize_identifier(value) == value
    )
