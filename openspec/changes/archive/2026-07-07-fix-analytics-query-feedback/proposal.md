## Why

When a user selects filters on the Analytics page and presses the "Query" button, API failures are silently swallowed. The frontend destructures `{ data, isLoading }` from `useAnalyticsQuery` but does not destructure `isError` or `error`. When the API call fails, `data` is `undefined`, the spinner stops, and the user sees nothing — the button appears to do nothing. Multiple upstream layers compound the problem: the gateway proxy has no error handling, and the backend catches all exceptions as misleading "Query timed out" errors.

## What Changes

- **Frontend**: Destructure `isError` and `error` from `useAnalyticsQuery` and render an inline error banner when the query fails.
- **Frontend**: Reset `queryEnabled` to `false` on error so re-clicking Query re-triggers the fetch properly.
- **Gateway proxy**: Add `try/except` in `analytics_proxy.py` to surface upstream failures with appropriate status codes instead of generic 500s.
- **Backend query service**: Replace the catch-all `except Exception → 504` with specific error handling: distinguish DB errors, schema errors, validation errors, and actual timeouts.
- **Spec-level updates**: Update `analytics-ui` spec to require error/loading/empty states for query results. Update `analytics-query-api` spec to define distinct error response schemas for different failure modes.

## Capabilities

### New Capabilities

- `query-error-feedback`: User-facing error display and retry behaviour for the analytics query flow.

### Modified Capabilities

- `analytics-ui`: REQUIREMENTS CHANGE — query results section must show error banner and loading state; previously unaddressed error handling is now a first-class requirement.
- `analytics-query-api`: REQUIREMENTS CHANGE — API must return distinct error codes/categories (timeout, validation, internal) instead of a blanket 504; error response schema is now part of the contract.

## Impact

| Area | What changes |
|---|---|
| `src/portal/src/app/(auth)/analytics/page.tsx` | Add `isError`/`error` destructuring, error banner, loading state refinement |
| `src/portal/src/hooks/use-analytics-data.ts` | No changes needed (hook already returns React Query's standard fields) |
| `src/gateway/api/v1/analytics_proxy.py` | Add try/except with proper status code forwarding |
| `src/analytics_service/api/v1/query.py` | Replace catch-all `except Exception` with typed exception handling |
| `openspec/specs/analytics-ui/spec.md` | Add ACs for error/loading/empty states |
| `openspec/specs/analytics-query-api/spec.md` | Add ACs for distinct error response schemas |

No new dependencies, no infrastructure changes, no breaking API changes.

## Open Questions

1. The user reports Docker returning "2020". Is this HTTP 202 from `/refresh` being confused with query, or a Docker exit code? Need to confirm which specific response is seen.
2. Are there existing error display patterns in other pages (e.g., dashboard, document list) to follow?
