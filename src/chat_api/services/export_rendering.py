import csv
import io

from openpyxl import Workbook

# Ties this feature's storage guarantee to sql_generator.py's own hard cap (its
# `LIMIT` clamp never lets a generated query return more than 1000 rows). Snapshots
# are capped again here, defensively, so a future change to that clamp cannot
# silently remove this feature's only size guarantee (design.md Risks; ADR-014
# Negative consequence; verification.md Hallucination Risk 6).
MAX_EXPORT_ROWS = 1000

# Cell values beginning with any of these characters are interpreted as a formula
# by Excel/Sheets/LibreOffice on open — a well-known CSV/Excel-injection class
# (OWASP). Rows in an export snapshot originate from extracted document/entity
# data the platform does not author, so every cell value is treated as untrusted
# text (design.md Decision 4; verification.md Hallucination Risk 5).
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def cap_rows(rows: list[dict] | None) -> list[dict]:
    """Defensively caps a raw SQL result to MAX_EXPORT_ROWS before it is persisted
    as an export snapshot, regardless of how many rows the caller passed in."""
    if not rows:
        return []
    return rows[:MAX_EXPORT_ROWS]


def _sanitize_cell(value) -> object:
    if isinstance(value, str) and value and value[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + value
    return value


def _columns(rows: list[dict]) -> list[str]:
    columns: list[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


def render_csv(rows: list[dict]) -> bytes:
    columns = _columns(rows)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _sanitize_cell(row.get(col)) for col in columns})
    return buffer.getvalue().encode("utf-8")


def render_xlsx(rows: list[dict]) -> bytes:
    columns = _columns(rows)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(columns)
    for row in rows:
        sheet.append([_sanitize_cell(row.get(col)) for col in columns])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
