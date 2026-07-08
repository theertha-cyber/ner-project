## Context

The analytics query flow has three layers (frontend → gateway proxy → analytics service), and each has an error-handling gap:

1. **Frontend** (`page.tsx:154`): Only `{ data, isLoading }` is destructured from `useAnalyticsQuery`. When the API fails, React Query sets `data: undefined` and `isError: true`, but the results section (`page.tsx:336`) is gated on `queryEnabled && queryResult` — so the spinner stops and nothing renders. No error is surfaced.

2. **Gateway proxy** (`analytics_proxy.py:11-28`): The `_proxy()` function has no `try/except`. If the upstream analytics service is down, slow, or returns non-JSON, `httpx` or `resp.json()` throws an unhandled exception, yielding a generic FastAPI 500.

3. **Backend query** (`query.py:55-56`): The `except Exception` clause catches *everything* (missing tables, SQL syntax errors, schema-not-found, connection drops) and returns a misleading `504 "Query timed out"`. The real cause is hidden.

The existing `analytics-ui` spec at `openspec/specs/analytics-ui/spec.md` already has a "Error State Handling" requirement with one scenario (dashboard API returning 500), but it does not cover query-specific errors. The `analytics-query-api` spec at `openspec/specs/analytics-query-api/spec.md` has a timeout scenario but no coverage for other error modes.

## Goals / Non-Goals

**Goals:**
- Surface query API failures to the user as readable error banners
- Classify backend errors properly (timeout vs validation vs internal)
- Prevent silent failures at every layer
- Follow existing UI patterns (the `errorMessage` state + warning banner pattern at `page.tsx:158,223-228` is already used for export/refresh)

**Non-Goals:**
- Redesign the analytics page layout
- Change the query API contract (add new fields/endpoints)
- Add retry logic beyond what React Query already provides (`retry: 1`)
- Fix the dashboard widget error handling (already works: `page.tsx:189-199`)
- Fix the export error handling (already works: `page.tsx:176-179`)
- Add pagination controls (out of scope)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 | OpenSpec governance: proposal → design → spec → tasks → evidence → archive | Must follow the full pipeline |
| ADR-005 | OpenCode agent boundaries | Implementation changes must be within allowed edit roots |

No ADR is superseded or challenged by this design.

## Decisions

### Decision 1: Frontend error handling — use existing `errorMessage` pattern

**Choice:** Add `isError` and `error` destructuring from `useAnalyticsQuery`, and display the error using the existing `errorMessage` state + warning banner component.

**Rationale:**
- The page already has a working error banner pattern at lines 223-228 using the `errorMessage` state. Export and refresh both use it.
- Adding a separate query-specific error state would duplicate the rendering logic.
- React Query's `error` object carries the message thrown by `queryFn` (e.g., "Query failed: 500"), so we can display it directly.
- The `handleQuery` function already calls `setErrorMessage(null)` on click — we just need to set it on error too.

**Alternatives considered:**
- Using a toast/notification system — the page doesn't use one, introducing a new pattern is scope creep.
- Using React Query's global `onError` handler on QueryClient — too broad, would catch dashboard and other query errors too.

### Decision 2: Gateway proxy — structured error forwarding

**Choice:** Wrap the `_proxy()` function in `try/except` and return the upstream error status and detail when available, falling back to a 502 Bad Gateway.

**Rationale:**
- The gateway should be transparent: if upstream returns a structured error, pass it through.
- If the upstream is unreachable (connection refused, DNS failure, timeout), return 502 with a clear message.
- This avoids the current behaviour where a down analytics service yields an opaque FastAPI 500 with no useful detail.

**Alternatives considered:**
- Adding circuit breaker pattern — overengineered for a single-proxy use case.
- Using a custom httpx transport with retries — the existing 60s timeout is sufficient; retries at the gateway would mask upstream failures.

### Decision 3: Backend — typed exception handling

**Choice:** Replace `except Exception` with specific exception types:
- `asyncio.TimeoutError` / SQLAlchemy `exc.TimeoutError` → 504
- `sqlalchemy.exc.OperationalError` (connection, table not found) → 502
- `sqlalchemy.exc.ProgrammingError` (schema, syntax) → 422 or 502 depending on cause
- Other exceptions → 500 with generic message

**Rationale:**
- The current catch-all hides real problems (e.g., missing materialized views, wrong column names).
- Proper classification lets the frontend show meaningful errors instead of a misleading "timeout."

**Alternatives considered:**
- Using a middleware to catch all DB errors — that would affect all endpoints, not just query, and could break the dashboard export which has its own error handling. Better to scope the change to the query endpoint.

## Risks / Trade-offs

- [Gateway error forwarding may expose internal service names] → The error detail is already visible in the upstream response; the gateway only passes it through. No new information is leaked.
- [Backend error classification may miss edge-case exceptions] → The `except Exception` fallback ensures no error goes unhandled; the classification just adds specificity for known types.
- [Frontend error banner overlaps with export/refresh errors] → The `errorMessage` state is shared; concurrent errors overwrite each other. This is acceptable because the user actions (query, export, refresh) are mutually exclusive in the UI.

## Migration Plan

1. Apply frontend changes (error destructuring + setErrorMessage on query failure)
2. Apply gateway changes (try/except in _proxy)
3. Apply backend changes (typed exception handling)
4. Run existing tests: `pytest tests/test_analytics_query_api.py`
5. Manual smoke test: verify error banner appears when analytics service is stopped

Rollback: revert the three changed files. No data migration required.

## Open Questions

1. The user reports "2020" — is this HTTP 202 (Accepted) from `/refresh` being confused with query, or something else? Clarify before verifying the fix.
