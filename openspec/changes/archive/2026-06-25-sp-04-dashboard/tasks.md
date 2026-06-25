## 1. Backend — Dashboard Summary Endpoint

- [x] 1.1 Define `DashboardData` Pydantic response model in `src/gateway/api/v1/dashboard.py` with fields matching `dashData(role)` shape (kicker, title, line, stats[4], pTitle, pMeta, pRows[4], sideTop, sideMeta, big, bigUnit, bar, sideMetrics[3], sideBot, sideRows[3])
- [x] 1.2 Define `DashboardSourceStatus` model with a `sources` dict mapping service names to boolean availability flags
- [x] 1.3 Create `GET /api/v1/dashboard/summary` route with JWT auth dependency; decode role and tenant_id from token
- [x] 1.4 Implement role-to-service routing using a lookup table: system_admin calls tenants + training services; tenant_admin calls documents + annotation + training + models; annotator calls annotation + documents; business_user calls extraction + models
- [x] 1.5 Wrap each downstream service call in independent try/catch with short timeouts (5s connect, 10s read); on failure set null data + `sources.<name>: false`
- [x] 1.6 Wire `system_admin` tenant-count source using existing tenant DB query; all training-dependent fields return null for MVP (training service integration deferred)
- [x] 1.7 Add unit tests for dashboard summary endpoint: each role returns correct shape, partial failure returns null + sources, unauthenticated returns 401
- [x] 1.8 Register route in gateway's router and add to OpenAPI schema

## 2. Frontend — DashboardPage Component

- [x] 2.1 Define `DashboardData` TypeScript interface in `src/portal/lib/types.ts` with optional fields for null values
- [x] 2.2 Create `src/portal/app/dashboard/page.tsx` as `<DashboardPage>` self-contained component
- [x] 2.3 Implement TanStack Query `useDashboardSummary()` hook calling `GET /api/v1/dashboard/summary` with `refetchInterval: 30000`, `staleTime: 15000`, and `enabled` based on auth state
- [x] 2.4 Build layout toggle segment control (Editorial/Command) with `localStorage` persistence key `"portal-layout"`, defaulting to "Editorial"
- [x] 2.5 Build hero section: render kicker (JetBrains Mono 12px uppercase), title (Hanken Grotesk 800 38px), line (Inter 15px); Editorial mode uses transparent bg, Command mode uses dark container (#161b24, 24px radius, animated mesh gradient orbs, white title)
- [x] 2.6 Build stat card strip: 4-column grid, each card with value+unit (Hanken Grotesk 800 30px), label, sub (JetBrains Mono), delta pill with coloured background; skeleton shimmer placeholders during loading; `—` for null values; hover translateY(-2px)
- [x] 2.7 Build activity panel: 1.5fr in two-column grid, header with pTitle+pMeta, 4 clickable rows with status dot + tag pill + title + sub; row click calls `useRouter().push(mapped href)`
- [x] 2.8 Build secondary metrics panel: two stacked cards; top card shows big+bigUnit (Hanken Grotesk 800 44px primary colour), progress bar with growBar animation, 3 sideMetrics rows; bottom card shows mini bar chart with colour-coded bars
- [x] 2.9 Add `QueryClientProvider` to `app/layout.tsx` wrapping AuthProvider and ToastProvider
- [x] 2.10 Add unit tests: stat card rendering (live, skeleton, null), layout toggle persistence, activity row navigation, progress bar fill

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 3.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 3.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 3.6 Run `openspec validate sp-04-dashboard --type change --strict` and confirm it exits clean before archive.
