## Context

The model-serving service needs to resolve the active model version and label list for a tenant before running inference. It does this by calling the training service's `GET /api/v1/models/active` endpoint. The training service endpoint requires `system_admin` callers to explicitly provide `?tenant_id=<tid>` — a deliberate design pattern shared across the training service API (e.g., `training-jobs` spec line 46).

Today, `_resolve_active_version()` and `_resolve_label_list()` both create a `system_admin` JWT and call the endpoint without the query parameter. The endpoint returns HTTP 400, and both functions silently fall back to the base model / CoNLL labels. Every extraction from every tenant returns base model results regardless of what's promoted.

A previous fix cycle (archive `2026-07-13-fix-model-loading-and-label-mapping`) fixed the port-routing issue (model-serving was calling the wrong port), but the `?tenant_id` query parameter was never added — so the calls still fail structurally.

## Goals / Non-Goals

**Goals:**

- Make `_resolve_active_version()` and `_resolve_label_list()` pass the tenant ID when calling the training service as `system_admin`.
- Preserve the existing fallback-to-base behavior for genuine transient errors (connection timeouts, 5xx).

**Non-Goals:**

- No changes to the training service endpoint's auth semantics.
- No new observability or alerting (separate concern).
- No changes to the warmup path or any other inter-service call.

## Currently-In-Force ADRs

All ADRs in `docs/adr/` have status **Proposed**. None are formally accepted. The most relevant is ADR-008 (Base Model as Default), which mandates the fallback-to-base behavior that we are preserving.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-008 | Base model as version 0; fallback when no promoted model exists | Fallback MUST remain for genuine errors. This fix ensures fallback fires only on transient failures, not on every call. |

## Decisions

### Decision 1: Pass `tenant_id` as query parameter (fix in model-serving only)

**Choice:** Add `params={"tenant_id": tenant_id}` to the `requests.get()` call in both `_resolve_active_version()` and `_resolve_label_list()`.

**Rationale:** The training service endpoint already accepts `tenant_id` as a query parameter for `system_admin` callers. This is the minimal change — two one-line additions, no schema changes, no new settings, no behavior change to the training service's auth model.

**Alternatives considered:**
- **Change the training service to read tenant_id from JWT for system_admin**: Would couple the endpoint's auth logic to the caller's token structure. The current design (system_admin must be explicit about which tenant) is deliberate — see `training-jobs` spec — and changing it would introduce inconsistency.
- **Make model-serving use `tenant_admin` role**: Would require changes to token creation and auth checks, and would conflate model-serving's internal identity with a tenant-specific role.

### Decision 2: Preserve existing error handling

**Choice:** Do not change the `if resp.status_code != 200: return "base", 0` fallback.

**Rationale:** Genuine transient failures (network blips, training service restart) should not break extraction. Once the `?tenant_id` parameter is present, a 400 only occurs for actual misconfiguration (unlikely) or transient server errors (rare). The fallback is a safety net, not a bug.

### Decision 3: Increase extraction engine timeout to 90s

**Choice:** Change `httpx.AsyncClient(timeout=30)` to `httpx.AsyncClient(timeout=90)` in `extraction_engine.py`.

**Rationale:** The extraction engine's 30s timeout is too tight for cold-start model loading (downloading 411 MiB from MinIO + ONNX Runtime init can exceed 30s on first request). The warmup endpoint already uses 90s. This is consistent with the existing pattern.

**Alternatives considered:**
- **Keep 30s, rely on warmup**: Warmup now works correctly with the `?tenant_id` fix, so the model should be pre-loaded. But cache eviction (30min TTL), restarts, or transient warmup failures still leave the cold-start path vulnerable. Defensive increase is cheap.
- **Make timeout configurable**: Unnecessary for a single constant change; can be extracted later if needed.

## Risks / Trade-offs

- [400 from model-serving now means something real] → With the fix, a 400 from these calls would indicate a genuine issue (wrong tenant_id, malformed request, server error). The fallback masks it, as before. No observability change is introduced here; that's a separate concern.
- [Regression if the training service endpoint's auth contract changes in the future] → Low risk. The `system_admin + ?tenant_id` pattern is shared across the training service API and is documented in specs. Any change would be a coordinated API version change.
- [Extraction request hangs for 90s on failure] → Acceptable trade-off. A failed extraction already blocks for 30s; 90s matches the warmup convention and is still below typical API gateway timeouts.

## Migration Plan

1. Add `params={"tenant_id": tenant_id}` to `_resolve_active_version()` `requests.get()` call.
2. Add `params={"tenant_id": tenant_id}` to `_resolve_label_list()` `requests.get()` call.
3. Rebuild and restart the `model_serving` container.
4. Change `timeout=30` to `timeout=90` in `extraction_engine.py`. No rebuild needed (no Dockerfile change).
5. Verify: make an extraction → response should show the promoted version number and custom labels, not base model/CoNLL.

Rollback: Revert the timeout change and restart `extraction_service`.

## Open Questions

None.
