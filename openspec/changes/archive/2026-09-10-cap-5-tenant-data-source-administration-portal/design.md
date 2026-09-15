## Context

The portal is a Next.js app (`src/portal`) behind the existing authenticated `(auth)` layout and app shell. Tenant-admin navigation is role-derived from `navFor` (`src/portal/src/lib/nav-config.ts`) and currently exposes document upload but no data-source route. Same-origin `/api/*` calls are proxied to the gateway by `next.config.js` rewrites, and authenticated calls go through `authFetch` (`src/portal/src/lib/auth-fetch.ts`), which passes unrecognized `/api/v1/*` paths through as relative URLs. The CAP-2 through CAP-4 backends expose tenant-scoped safe contracts (safe `Connection`/`ConnectionPage` shapes, closed provider schemas, finite outcome classes, `Idempotency-Key` mutations); the portal consumes them and owns no backend records. Visual authority is the UI contract (`docs/design/ui-contract.md`: Clean foundation with existing portal override, web, tokens `src/portal/design-system/ner-portal/tokens.css` imported first in `globals.css`) and the three approved mockups. Azure live verification stays deferred per `run.provisioning` — this capability verifies against fixtures/fakes and remains inactive against live Azure until approved resources exist.

## Goals / Non-Goals

**Goals:**

- Give tenant admins the three inventory screens (SCR-1–SCR-3) with URL-backed collections, safe lifecycle actions, and contract administration, all inside the existing shell, tokens, and light/dark mode.
- Make every lifecycle, sync, contract, and drift state actionable while rendering only safe shapes (field names, finite outcome classes, reason codes, request IDs).
- Keep all portal tests hermetic: fixtures/fakes for backend contracts, no live Azure.

**Non-Goals:**

- No backend, API, schema, or contract change; CAP-2 through CAP-4 requirement behaviour is untouched.
- No redesign of upload/chat UI; no new browser, localisation, or accessibility promises beyond the UI contract.
- No direct query rows, SQL text, or tenant content rendering anywhere.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant-scoped data isolation | Portal sends tenant context via auth only; never a tenant selector or cross-tenant parameter. |
| ADR-011-tenant-scoped-azure-connection-control-plane | Finite Azure connections, closed schemas, activation evidence, idempotency | UI exposes only the two approved providers, closed field sets, evidence checklist, and `Idempotency-Key` mutations; renders finite safe outcomes only. |
| ADR-012-durable-azure-blob-source-synchronization | Durable Blob sync with safe aggregate status | Sync panel shows schedule/state/aggregate outcomes only, never blob content or provider payloads. |
| ADR-013-contract-governed-external-postgresql-chat | Versioned schema contracts gate direct chat | SCR-3 manages contract metadata/validation/drift only; no rows or SQL displayed. |
| ADR-014-local-compose-delivery-topology | Local compose delivery | Portal additions must run under the existing compose/standalone Next.js setup with no new service. |

No ADR is fully superseded (ADR-008/009/010 partially supersede ADR-002/006 clauses unrelated to this design). No in-force ADR needs revisiting.

## Decisions

### Decision 1: Routes under `(auth)/settings/data-sources`

**Choice:** Implement `src/portal/src/app/(auth)/settings/data-sources/page.tsx`, `[connectionId]/page.tsx`, and `[connectionId]/schema-contracts/page.tsx` inside the existing `(auth)` group so the current auth layout, shell, and tenant-admin guard apply unchanged; add one `tenant_admin` entry (`Data Sources`, `/settings/data-sources`) to `navFor` plus a `SCREEN_TITLES` key.

**Rationale:** Reuses authentication, authorization, sidebar, and responsive collapse with zero new plumbing; matches the inventory navigation model (`/settings/data-sources` entry, `/login` for unauthenticated, safe authorization state for non-admins).

**Alternatives considered:**
- Top-level `(auth)/data-sources` routes — ruled out because the inventory fixes the `/settings/data-sources` path and deep links/history depend on it.
- Separate layout for admin screens — ruled out because it would fork the shell the contract requires us to reuse.

### Decision 2: Relative-URL data layer through `authFetch`, no `resolveUrl` change

**Choice:** Add `src/portal/src/lib/data-sources.ts` (safe TypeScript types for `Connection`, `ConnectionPage`, outcome classes, reason codes; allowlisted query builders; `Idempotency-Key` generation) with hooks calling `authFetch` using relative `/api/v1/data-sources…` URLs, letting the existing `next.config.js` rewrite proxy them to the gateway.

**Rationale:** `resolveUrl` already passes unknown `/api/v1/*` paths through as relative URLs, so no shared-networking change is needed; collection state (search, filters, sort, page) stays URL-backed via Next.js search params for shareable deep links, page-1 reset on filter change, and out-of-range empty pages.

**Alternatives considered:**
- Extending `resolveUrl` with a data-sources branch — ruled out because pass-through already yields the same destination with less shared-code churn.
- Client-only filter/sort state — ruled out because the inventory requires URL-backed, server-backed collections.

### Decision 3: Reuse `ui` primitives, add `data-sources` components

**Choice:** Compose screens from existing `components/ui` primitives (`badge` for CMP-3 safe status with text equivalents, `filter-select`, `spinner`, `slide-over` for pause/replace/retire confirmations) plus a new `components/data-sources` folder for CMP-2/CMP-4/CMP-5/CMP-6/CMP-7/CMP-8/CMP-9/CMP-10. All styling resolves through the installed token file; no literal colours or radii.

**Rationale:** Keeps the Clean existing-portal override and light/dark behaviour; confirmations satisfy the destructive-action baseline control; colour is never the sole signal.

**Alternatives considered:**
- New bespoke component library for admin screens — ruled out as visual drift from the contract and duplicated maintenance.
- Inline fetch/state per page without shared components — ruled out because SCR-1 and SCR-3 share pagination/outcome patterns.

### Decision 4: Safe-type boundary at the TypeScript layer

**Choice:** The `data-sources.ts` types model only the safe response shape (provider, status enum, configured/secret field *names*, outcome classes, schedule links, timestamps). There is deliberately no type member for values, secrets, connection strings, diagnostics, SQL, or content — unrenderable by construction.

**Rationale:** Makes the never-render prohibition structural rather than a review-time promise; aligns with the `sensitive-data-classification-and-minimization` baseline control.

**Alternatives considered:**
- Mirroring full backend payloads and relying on components to omit fields — ruled out because one missed field leaks a secret.

### Decision 5: Fixture-backed verification, live Azure out of scope

**Choice:** Vitest + React Testing Library page/component tests with capability-specific fixtures for routes, URL state, collection controls, keyboard/focus order, confirmations, safe display, contract forms, and light/dark rendering; no test touches live Azure, consistent with the deferred `azure-blob-test-account` / `azure-postgres-test-instance` provisioning entries.

**Rationale:** Hermetic tests run in CI and on machines without approved cloud resources; live verification remains inactive until the operator approves resources and activation evidence.

**Alternatives considered:**
- Live-gateway integration tests — ruled out because provisioning records them as deferred/skip.

## Risks / Trade-offs

- [Filter/sort/pagination contract drift vs. backend allowlist (unknown-field rejection)] → Build query strings only from the allowlisted builder; tests assert exact parameter sets including the `last_activity`-desc/`id`-asc default.
- [A backend error payload containing provider diagnostics could reach the UI] → Render only the finite safe code + request ID from the error envelope; tests feed hostile payloads and assert no diagnostic text appears.
- [Idempotency-key reuse across different bodies surfaces `409 IDEMPOTENCY_KEY_REUSED`] → Generate a fresh key per distinct mutation intent; surface the 409 as a safe, recoverable notice, never a retry-with-same-key loop.
- [Contract JSON upload of large/invalid files] → Client-side parse with size cap, field-level safe errors, recoverable form state; no file content logged.

## Migration Plan

1. Merge portal-only change behind no flag (new routes are unreachable except via the new tenant-admin nav entry and direct URL).
2. Deploy with the existing standalone Next.js image under compose; no migration, no new service, no env change.
3. Rollback: revert the portal to the previous image; no backend state exists to unwind.

## Open Questions

- Secret-reference control shape (text reference vs. picker) — defaults to a validated text reference naming the secret; either satisfies the closed-schema boundary.
- None requiring a new ADR.
