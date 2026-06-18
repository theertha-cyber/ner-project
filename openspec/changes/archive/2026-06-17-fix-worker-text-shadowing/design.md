## Context

`src/extraction_service/worker.py` imports `text` from SQLAlchemy at module level to construct parameterised SQL statements. Inside the per-document processing loop, the response body from the document service is stored in a local variable also named `text`. After that assignment every subsequent call to `text(...)` within the same loop iteration invokes a `str` object, not the SQLAlchemy helper, raising `TypeError` that the bare `except Exception` silently converts to `failed += 1`.

## Goals / Non-Goals

**Goals:**
- Eliminate the name collision so the SQLAlchemy `text()` helper is callable throughout the loop body
- Keep the fix minimal and mechanical — no refactoring beyond the rename

**Non-Goals:**
- Improving error handling or logging in the worker
- Addressing the `document_id = NULL` design gap in `extraction_runs`
- Any change to the API contract, database schema, or Celery task signature

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| None | — | This is a single-file variable rename with no architectural implications |

## Decisions

### Decision 1: Rename `text` → `doc_text` at both assignment sites

**Choice:** Rename the local variable to `doc_text` where it is assigned (`doc_text = text_resp.json().get("text", "")`) and at its single usage (`tokens = doc_text.split()`). The SQLAlchemy import alias remains `text` unchanged.

**Rationale:** Minimal diff, zero behavioural change outside unblocking the `INSERT`. Renaming the import would be a wider diff touching every SQL call in the file with no benefit.

**Alternatives considered:**
- Import alias: `from sqlalchemy import text as sa_text` — larger diff, affects every SQL call in the file unnecessarily
- Extract entity insertion to a helper function with its own import scope — over-engineering for a rename

## Risks / Trade-offs

- [No meaningful risk] → This is a two-line rename with no logic change. The only observable effect is that the `INSERT` now executes as intended.

## Migration Plan

No deployment steps required. The fix is a source-only change; no migration, no feature flag, no rollback concern.

## Open Questions

_(none)_
