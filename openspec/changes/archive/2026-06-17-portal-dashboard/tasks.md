## 1. Setup: Install TanStack Query

- [x] 1.1 Run `npm install @tanstack/react-query` in `src/portal` and confirm the package appears in `package.json` under dependencies.
- [x] 1.2 Add `QueryClientProvider` to `src/portal/src/app/layout.tsx`, wrapping `AuthProvider` (and `ToastProvider` if present) with a `new QueryClient()` instance created via `useMemo` or module-level singleton. *(Verifies scenario 20: QueryClientProvider wraps the app)*
- [x] 1.3 Run `npx tsc --noEmit` from `src/portal` — confirm no type errors introduced by the new package.

## 2. Types: DashboardData Shape

- [x] 2.1 Create `src/portal/src/types/dashboard.ts` defining: `StatItem { label, value: number | null, unit, sub, delta, dir?: "up" | "warn" }`, `ActivityRow { tag, tk, title, sub, go }`, `SideRow { label, val, pct, c }`, `SideMetric { k, v }`, and `DashboardData` with all fields from spec (kicker, title, line, stats[4], pTitle, pMeta, pRows[4], sideTop, sideMeta, big, bigUnit, bar, sideMetrics[3], sideBot, sideRows[]).
- [x] 2.2 Export a `DashboardSummaryResponse` type: `{ data: DashboardData; sources: Record<"tenants"|"training"|"documents"|"annotations"|"models", boolean> }`.
- [x] 2.3 Verify field names match the mockup's `dashData(role)` shape exactly (risk mitigation for hallucination risk 1).

## 3. Gateway: Dashboard Summary Endpoint

- [x] 3.1 Create `src/gateway/api/v1/dashboard.py` with `router = APIRouter(prefix="/dashboard", tags=["dashboard"])`. Add `GET /summary` endpoint with `Depends(require_tenant_role)` authentication — returns 401 for unauthenticated requests. *(Verifies scenario 7: unauthenticated request rejected; satisfies risk mitigation 4)*
- [x] 3.2 Implement `system_admin` branch: query `SELECT COUNT(*) FROM public.tenants` using the existing DB session, populate `stats[0].value` with real count, set `sources.tenants: true`, set all other `sources` to `false`, return static mockup values for all non-tenant fields.
- [x] 3.3 Implement `tenant_admin`, `annotator`, and `business_user` branches: return role-appropriate static mockup structure with `null` for all numeric values, all `sources` set to `false` (services not yet wired). *(Verifies scenarios 2, 3, 4)*
- [x] 3.4 Implement partial-failure response pattern: each service call is wrapped in `try/except`; exception sets `sources.{service}: false` and leaves the relevant `stats[*].value` as `null`. *(Verifies scenario 5: partial service failure degrades gracefully)*
- [x] 3.5 Register `dashboard.py` router in `src/gateway/main.py` under the `/api/v1` prefix.
- [x] 3.6 Verify `request.state.token_tenant_id` (from JWT) is used for tenant scoping in non-admin paths — no user-supplied tenant param accepted. *(ADR-001 compliance)*
- [x] 3.7 Smoke-test: `curl -X GET /api/v1/dashboard/summary` with a valid system_admin JWT; confirm `sources.tenants: true` and a non-null `stats[0].value`. *(Verifies scenario 6)*

## 4. Hook: useDashboardData

- [x] 4.1 Create `src/portal/src/hooks/use-dashboard-data.ts` using `useQuery` from `@tanstack/react-query`. Configure: `queryKey: ["dashboard-summary"]`, `queryFn` calls `GET /api/v1/dashboard/summary` with auth header from `useAuth()`, `refetchInterval: 30_000`, `staleTime: 15_000`, `placeholderData: keepPreviousData` (v5 API — NOT `keepPreviousData: true`). *(Verifies scenario 19, risk mitigation 3)*
- [x] 4.2 Map the `go` field in `ActivityRow` to hrefs via a `GO_HREF` lookup object: `{ training: "/training-jobs", annotation: "/annotation", documents: "/documents", extractions: "/extractions", models: "/models" }`. Export `goToHref(go: string): string`. *(Risk mitigation 2: verify against `navFor` hrefs in `nav-config.ts`)*
- [x] 4.3 Export `useDashboardData()` returning `{ data: DashboardData | undefined, isLoading, isError, sources }`.

## 5. Components: Stat Card

- [x] 5.1 Create `src/portal/src/components/dashboard/StatCard.tsx`. Props: `StatItem`. Renders: value (or `—` if null) + unit, label, sub, delta string, directional indicator (green arrow icon for `dir: "up"`, amber dot for `dir: "warn"`, none for neither). *(Verifies scenario 14: warn direction renders amber indicator)*
- [x] 5.2 Create `src/portal/src/components/dashboard/StatCardSkeleton.tsx` rendering a shimmer placeholder with the same dimensions as `StatCard`. No spinner.
- [x] 5.3 Ensure the 4-card strip: renders `StatCardSkeleton` × 4 when `isLoading`, renders `StatCard` × 4 with live values when data is present. *(Verifies scenarios 12, 13)*

## 6. Components: Activity Panel

- [x] 6.1 Create `src/portal/src/components/dashboard/ActivityPanel.tsx`. Props: `{ pTitle, pMeta, pRows: ActivityRow[] }`. Renders header (pTitle + pMeta), then 4 rows each with: status tag pill (colour from `tk` value — `pending_approval` → amber, `completed` → green, `running` → blue, `failed` → red), title, sub. *(Verifies scenario 16)*
- [x] 6.2 Each row wraps in an `<button>` (or Next.js `<Link>`) that calls `router.push(goToHref(row.go))` on click. *(Verifies scenario 15: activity row navigates on click)*

## 7. Components: Secondary Metrics Panel

- [x] 7.1 Create `src/portal/src/components/dashboard/MetricsPanel.tsx`. Props: `{ sideTop, sideMeta, big, bigUnit, bar, sideMetrics, sideBot, sideRows }`.
- [x] 7.2 Render progress bar as a `div` with `style={{ width: "${bar}%" }}` inside a container — pure CSS, no library. *(Verifies scenario 17: progress bar fills to correct percentage)*
- [x] 7.3 Render `sideRows` mini bars with `style={{ background: row.c, width: "${row.pct}%" }}` — colour applied directly from the `c` string. *(Verifies scenario 18: sideRows mini bars render correct colours)*
- [x] 7.4 Render three `sideMetrics` rows with key label and value in JetBrains Mono (use `font-family: "JetBrains Mono", monospace` inline or via CSS class).

## 8. Components: Hero Section & Layout Toggle

- [x] 8.1 Create `src/portal/src/components/dashboard/DashboardHero.tsx`. Props: `{ kicker, title, line, layout: "editorial" | "command" }`. In `"editorial"` mode: kicker (small-caps label, muted), title (≥ 28px, Hanken Grotesk 700), line (supporting sentence). In `"command"` mode: single line with kicker + title inline (≤ 18px), line hidden. *(Verifies scenarios 8, 9)*
- [x] 8.2 Create `src/portal/src/hooks/use-layout-preference.ts`. Reads `localStorage["portal-layout"]` inside `useEffect` (default `"editorial"`), writes on change. Guards `typeof window !== "undefined"` to prevent SSR errors. *(Verifies scenario 10; risk mitigation 6)*
- [x] 8.3 Create a `SegmentControl` component (or reuse if one exists) with options `["Editorial", "Command"]`. Toggling calls `setLayout` from `useLayoutPreference()`. Layout state change does NOT trigger a new query fetch — purely visual. *(Verifies scenarios 10, 11)*

## 9. Dashboard Page: Assembly

- [x] 9.1 Rewrite `src/portal/src/app/(auth)/dashboard/page.tsx` as a `"use client"` component. Call `useDashboardData()` and `useLayoutPreference()`. Remove the `system_admin → /admin` redirect entirely. *(Verifies scenario 21: system_admin lands on dashboard; risk mitigation 5)*
- [x] 9.2 Compose the full layout: `DashboardHero` at top, SegmentControl (layout toggle), stat card strip (4 × `StatCard` or `StatCardSkeleton`), two-column grid on desktop (ActivityPanel left, MetricsPanel right).
- [x] 9.3 Verify system_admin hero shows `kicker: "Platform control plane"` when logged in as system_admin. *(Verifies scenario 1)*
- [x] 9.4 Verify `null` stat values render as `—` (not 0, not blank, not error).

## 10. App-Shell Delta: Remove system_admin Redirect

- [x] 10.1 Confirm `src/portal/src/app/(auth)/dashboard/page.tsx` contains no `router.replace("/admin")` call (done as part of 9.1 — mark this as double-check pass).
- [x] 10.2 Browser test: login as system_admin, navigate to `/dashboard` — confirm URL stays `/dashboard` and dashboard renders with "Platform control plane" kicker. *(Verifies spec app-shell scenario: system_admin lands on dashboard)*

## 11. TypeScript & Build Verification

- [x] 11.1 Run `npx tsc --noEmit` from `src/portal` — must exit clean with no errors.
- [x] 11.2 Run `npx next build` from `src/portal` — must complete without errors (or `next dev` smoke test if full build is slow).
- [ ] 11.3 Confirm no `console.error` in the browser related to `useQueryClient`, hydration mismatches, or missing QueryClientProvider.

## 12. Verification & Evidence

- [ ] 12.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 12.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 12.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 12.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 12.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 12.6 Run `openspec validate portal-dashboard --type change --strict` and confirm it exits clean before archive.
