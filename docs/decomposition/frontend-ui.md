# Feature Decomposition: Frontend UI

## Summary

A Next.js (App Router, SPA-style) frontend for the Multi-Tenant NER Platform, built in `src/portal/`. The UI covers nine functional surfaces: Login, role-specific Dashboard, Annotation Workspace, Tenant Management, Training Jobs, Documents, Entity Types, Model Registry, and Users. The design system is derived directly from the interactive mockup at `docs/NER Platform.dc.html` — same CSS variable tokens, same three-font stack (Hanken Grotesk / Inter / JetBrains Mono), same component patterns. All data fetching is client-side (browser → microservices directly). Auth uses access token in memory (React context) + refresh token in an `httpOnly` cookie, requiring a small change to the gateway's auth endpoints.

---

## Source Documents

- `docs/NER Platform.dc.html` — full interactive mockup (design reference for all screens)
- `docs/support.js` — dc-runtime (React component engine powering the mockup; read for component logic, not for reuse)
- `README.md` — complete API endpoint reference
- `PROJECT.md` — tech stack, service topology, coding conventions
- `openspec/specs/*/spec.md` — backend spec for each domain (annotation-workspace, training-jobs, model-registry, etc.)

---

## Brainstorm Notes

**Key decisions from Phase 1:**
- **Scope**: Mockup-faithful screens (Login, Dashboard, Annotation, Tenants, Training) + API-ready screens inferred from mockup visual language (Documents, Entity Types, Model Registry, Users). Extractions, Audit Log, Analytics Chatbot, Settings → placeholder nav items only.
- **Framework**: Next.js App Router, all `use client` components, SPA-style. Next.js used as router and bundler only — no SSR, no Server Components, no Route Handlers.
- **Styling**: Tailwind CSS with CSS variable extensions. The mockup's `:root` token block becomes the canonical design system — translated to `tailwind.config.ts` theme extensions.
- **Auth**: Access token in React context (memory). Refresh token in `httpOnly; Secure; SameSite=Strict` cookie. **Requires one backend change**: `POST /api/v1/auth/login` and `POST /api/v1/auth/refresh` in `src/gateway/api/v1/auth.py` must add `Set-Cookie` on the response.
- **Data fetching**: TanStack Query (React Query) for server state, caching, and background refetch. `authFetch()` wrapper in SP-02 attaches `Authorization: Bearer` and triggers silent refresh on 401.
- **Dark mode**: `data-theme="dark"` on root `div`, persisted to `localStorage`.

**Codebase findings:**
- `src/portal/` does not yet exist. SP-01 creates it from scratch.
- The mockup's `Component` class (`renderVals()`) is the authoritative source for which state drives which UI element — used as the data contract reference when designing component props.
- The role-nav matrix in the mockup (`navFor(role)`) is the source of truth for role-based nav items. Matches backend JWT role values: `system_admin`, `tenant_admin`, `annotator`, `business_user`.
- The annotation workspace is the most complex screen: it encodes a full token-click labeling model with group-aware span selection, suggestion promotion, and two distinct layout modes.
- Training jobs screen is the second most complex: it includes live epoch polling (running jobs), role-gated approve/reject, and a multi-step status timeline.
- Screens without mockup designs (Documents, Entity Types, Model Registry, Users) all have complete API specs in `README.md`. Their UI should follow the mockup's table+slide-over pattern established in Tenants.

---

## Specs

### [SP-01] Project Foundation & Design System

**Domain**: `portal-foundation`

**Scope**
Bootstrap the `src/portal/` Next.js TypeScript project with Tailwind configured to the mockup's design token system, the three-font stack loaded, and a library of shared primitive components used by every subsequent spec. No business logic, no API calls.

**Requirement Coverage**
Implied by all screens: every UI spec depends on a shared token layer, font stack, and primitive components. The mockup defines these in its `<style>` block (lines 14–55): CSS variables for `--surface`, `--ink`, `--primary`, `--good`, `--warn`, `--bad`, `--shadow`, `--glass`, and their dark-mode overrides under `[data-theme="dark"]`. Keyframe animations (`fadeUp`, `popIn`, `slideOver`, `spin`, `pulse`, `growBar`, etc.) are also shared.

**Evidence**
All subsequent specs reference shared primitives. Without this spec, no other spec can render consistently. Completion is demonstrated when a smoke-test page renders the design token palette, all font weights, a sample `<Badge>`, `<StatCard>`, `<SlideOver>`, `<Toast>`, `<SegmentControl>`, `<MiniBar>`, and `<Spinner>` in both light and dark mode.

**NFRs**
- Tailwind purge must not strip CSS variable references from inline `style` props.
- Dark mode via `data-theme` attribute (not Tailwind's `class` strategy) to match the mockup's approach.
- Fonts loaded via `next/font/google` for self-hosting; no external Google Fonts request at runtime.

**Constraints**
- Must use Next.js App Router (App directory, not Pages).
- TypeScript strict mode.
- `src/portal/` is a standalone Next.js app with its own `package.json` — not a workspace package.

**Assumptions**
- Tailwind v3 (compatible with Next.js 14+).
- The design token values are taken verbatim from the mockup's `:root` block — no redesign.
- Mobile layout is out of scope; desktop-first (min 1024px) only.

**Contracts / Interfaces**
Shared components exported from `src/portal/components/ui/`:
```ts
<Badge variant="active"|"inactive"|"running"|"completed"|"failed"|"pending_approval"|"queued"|"rejected"|"cancelled"|"promoted"> {children} </Badge>
<StatCard label={string} value={string} unit={string} delta={string} deltaDir="up"|"warn"|"neutral" sub={string} />
<SlideOver open={boolean} onClose={() => void} width={number?}> {children} </SlideOver>
<MiniBar used={number} max={number} />
<SegmentControl options={Array<{label, value}>} value={string} onChange={fn} />
<Spinner size="sm"|"md" />
<PlaceholderScreen title={string} />
useToast() → { toast(msg, kind?: "ok"|"bad") }
<ToastProvider> / <ToastContainer>
useDarkMode() → { dark: boolean, toggle: () => void }
```

**Prerequisites**: None

**Implementation Notes**
- `tailwind.config.ts` extend `colors` with the design token names (`primary`, `ink`, `surface`, etc.) mapping to CSS variable references: `'primary': 'var(--primary)'`. This lets Tailwind classes like `bg-primary`, `text-ink-2` work.
- The `growBar`, `popIn`, `slideOver`, `fadeUp`, `spin`, `pulse` keyframes should be added to `tailwind.config.ts` under `theme.extend.keyframes` and `animation`.
- `SlideOver` needs a CSS `animation: slideOver` on mount — use a `data-open` attribute + Tailwind `data-[open]:translate-x-0` pattern or a simple `useEffect` class toggle.

---

### [SP-02] Auth Flow

**Domain**: `portal-auth`

**Scope**
Login screen (matches mockup glassmorphism design exactly), JWT auth context with access token in React memory, `httpOnly` cookie for refresh token, a `authFetch()` interceptor that silently refreshes on 401, logout, and a `<RequireAuth>` route guard. Includes the gateway backend change to set `Set-Cookie` on login/refresh responses.

**Requirement Coverage**
From `README.md` Auth section: `POST /api/v1/auth/login` returns `access_token` + `refresh_token`. `POST /api/v1/auth/refresh` reissues both. `POST /api/v1/auth/logout` is a stub. JWT claims include `tenant_id`, `user_id`, `role`. From the mockup: login screen with email + password fields, a "Sign in →" primary CTA, and four demo role-chip shortcuts (system_admin, tenant_admin, annotator, business_user).

**Evidence**
Demonstrated by: (1) submitting the login form issues a real `/auth/login` call, sets the `httpOnly` cookie for the refresh token, stores the access token in context; (2) navigating to a protected route while unauthenticated redirects to `/login`; (3) letting the 15-minute access token expire and making an API call silently refreshes and retries; (4) logout clears context and redirects to `/login`.

**NFRs**
- Access token must never be written to `localStorage` or `sessionStorage`.
- `authFetch()` must be safe to call concurrently — only one refresh in-flight at a time (use a pending-promise singleton).
- The `Set-Cookie` header from the backend must use `Secure` (requires HTTPS in production; dev can omit `Secure` on localhost).

**Constraints**
- **Backend change required**: `src/gateway/api/v1/auth.py` — `login` and `refresh` endpoints must add a `Set-Cookie: refresh_token=<token>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=604800` header on their `JSONResponse`. This is a prerequisite to implementing silent refresh.
- The gateway does not currently set cookies. Until this change ships, token refresh can fall back to response-body refresh token (stored in memory only, lost on page reload).

**Assumptions**
- The `role` and `tenant_id` fields in the JWT payload are sufficient for client-side role-gating — no additional `/me` endpoint call needed.
- Demo role chips in the mockup (4 hardcoded credentials) are for development only; they hit real API endpoints.
- On page reload, if the refresh cookie exists, `AuthContext` on mount calls `/auth/refresh` to restore the access token before rendering protected routes.

**Contracts / Interfaces**
```ts
// AuthContext
interface AuthUser {
  userId: string
  tenantId: string
  role: "system_admin" | "tenant_admin" | "annotator" | "business_user"
  email: string
}
interface AuthContextValue {
  user: AuthUser | null
  accessToken: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}
useAuth(): AuthContextValue

// Fetch wrapper — used by all other specs for API calls
authFetch(url: string, init?: RequestInit): Promise<Response>

// Route guard
<RequireAuth roles?: AuthUser["role"][]> {children} </RequireAuth>
```

**Prerequisites**: [SP-01]

**Implementation Notes**
- `authFetch` lives in `src/portal/lib/api.ts`. It prepends the correct service base URL based on route prefix (`/api/v1/admin` → gateway port 8000, `/api/v1/documents` → doc service port 8001, etc.). In development a `.env.local` maps each service URL; in production, an ingress/gateway handles routing.
- Use a `useRef` for the pending-refresh promise to survive re-renders without stale closure issues.
- The login page is at `/login` (unauthenticated). `<RequireAuth>` wraps the layout in `app/layout.tsx` and redirects to `/login` via `useRouter().replace()`.

---

### [SP-03] App Shell

**Domain**: `portal-shell`

**Scope**
The persistent application chrome: sidebar with role-specific navigation, topbar with screen title / search hint / role-switcher widget / dark mode toggle / user avatar, main content routing, and placeholder screens for all out-of-scope nav items. This spec establishes the URL-to-screen mapping for all subsequent specs.

**Requirement Coverage**
From the mockup: `<aside>` sidebar (lines 124–157) with logo, tenant switcher pill, role-specific nav items (with badge counts), user info strip, and logout. `<header>` topbar (lines 162–182) with screen title + path, search hint, role-switch segment control, dark mode button, and avatar. Role-nav matrix from `navFor(role)` in the mockup component. Placeholder screens for nav items with no implemented screen.

**Evidence**
Demonstrated by: switching the active role in the topbar role-switcher re-renders the sidebar with the correct nav items and badges; navigating between implemented screens updates the topbar title and path; unauthenticated access to any route redirects to `/login`; out-of-scope nav items navigate to a "Coming soon" placeholder with the screen name.

**NFRs**
- Active nav item highlight must match the current route, not just component state.
- Sidebar must be `position: sticky; height: 100vh` (overflow: auto on nav section), matching the mockup.
- Dark mode toggle persists to `localStorage` via `useDarkMode()` from SP-01 and applies `data-theme="dark"` on the root `<div>`.

**Constraints**
- The role-switcher widget in the topbar (SA/TA/AN/BU chips) is a development/demo convenience, not a production feature. It should be gated behind `NODE_ENV !== 'production'` or a `NEXT_PUBLIC_DEMO_MODE` env flag.
- Tenant switcher pill in the sidebar is display-only for now (shows tenant name + slug from JWT). Full tenant-switch flow is out of scope.

**Assumptions**
- URL structure: `/dashboard`, `/annotation`, `/admin/tenants`, `/training`, `/documents`, `/entity-types`, `/models`, `/users` — all under the authenticated layout.
- Badge counts on nav items (e.g. "Training Queue · 2") come from the dashboard data query already loaded; they are not fetched independently by the shell.
- The search bar (`⌘K`) is a visual placeholder only — no command palette implementation in this spec.

**Contracts / Interfaces**
```ts
// Navigation config (derived from mockup's navFor())
interface NavItem {
  id: string
  icon: string
  label: string
  href: string
  roles: AuthUser["role"][]
  badge?: string | number
}

// Layout component consumed by all screen specs
<AppShell badgeCounts?: Record<string, number>>
  {children}
</AppShell>
```

Route map:
```
/login              → LoginPage (SP-02, unauthenticated)
/dashboard          → DashboardPage (SP-04)
/annotation         → AnnotationPage (SP-05)
/admin/tenants      → TenantsPage (SP-06) [system_admin only]
/training           → TrainingPage (SP-07)
/documents          → DocumentsPage (SP-08)
/entity-types       → EntityTypesPage (SP-09)
/models             → ModelRegistryPage (SP-10)
/users              → UsersPage (SP-11)
/extractions        → PlaceholderScreen [business_user, tenant_admin]
/audit              → PlaceholderScreen [system_admin]
/settings           → PlaceholderScreen [all]
```

**Prerequisites**: [SP-01], [SP-02]

**Implementation Notes**
- Use Next.js App Router layout nesting: `app/(auth)/layout.tsx` wraps all authenticated screens in `<RequireAuth>` + `<AppShell>`.
- `app/(public)/login/page.tsx` is outside the auth layout.
- Nav active state: `usePathname()` from `next/navigation` matched against each `NavItem.href`.

---

### [SP-04] Dashboard

**Domain**: `portal-dashboard`

**Scope**
Role-specific dashboard page for all four roles (system_admin, tenant_admin, annotator, business_user), each with a hero section, four stat cards, a primary activity panel, and a secondary model/quota panel. Two layout variants (Editorial A / Command B) toggled by a segment control. All data is fetched client-side and composed from multiple services.

**Requirement Coverage**
From the mockup `dashData(role)` method (lines 866–927): four distinct data shapes per role with different KPIs, primary panel content (approval queue / pipeline activity / annotation tasks / recent extractions), and secondary panel content (platform health / active model metrics / dataset readiness / top extracted fields). From the mockup layout (lines 187–279): hero, 4-column stat strip, two-column panel grid.

**Evidence**
Demonstrated by: (1) each role sees a hero kicker/title/line matching their context; (2) stat values are live from APIs (not hardcoded); (3) primary panel rows are clickable and navigate to the relevant screen; (4) switching between Editorial/Command layouts changes the hero presentation without re-fetching data.

**NFRs**
- Dashboard must load without a full-page spinner — use TanStack Query's `placeholderData` or skeleton cards while fetching.
- Data must not go stale while the user is on the page — set `refetchInterval: 30_000` for the running-job counts.

**Constraints**
- Dashboard data is a composite of multiple service APIs. Each data source fails independently — if the training service is down, the stat cards that don't depend on it still render.
- The `system_admin` role's "Pending approvals" stat requires calling the training service across all tenants — the backend currently only supports per-tenant job queries. For MVP, this can show the count for the system_admin's own tenant, or be hardcoded to a polling query with a `?status=pending_approval` filter (the gateway's approve endpoint accepts `?tenant_id` as a query param).

**Assumptions**
- Dashboard queries per role:
  - `system_admin`: `GET /api/v1/admin/tenants` (tenant count), `GET /api/v1/training-jobs?status=pending_approval` (per tenant)
  - `tenant_admin`: `GET /api/v1/documents`, `GET /api/v1/training-jobs`, `GET /api/v1/models/active`
  - `annotator`: `GET /api/v1/annotation-tasks`, `GET /api/v1/documents/{id}/spans` (aggregated)
  - `business_user`: `GET /api/v1/models/active`, extraction stats (placeholder if extraction history endpoint doesn't exist)
- "Editorial" vs "Command" is a pure visual toggle (no data change); preference stored in `localStorage`.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET /api/v1/admin/tenants            → gateway :8000
GET /api/v1/training-jobs            → training :8003
GET /api/v1/models/active            → training :8003
GET /api/v1/documents                → document :8001
GET /api/v1/annotation-tasks         → annotation :8002

// Component
<DashboardPage />   // self-contained, reads role from useAuth()
```

**Prerequisites**: [SP-03]

**Implementation Notes**
- Use `useQuery` per data source with independent error/loading states.
- The `growBar` animation on stat card progress bars should trigger on mount — use a `useEffect` with a short delay to apply the `animate-grow-bar` class after paint.
- The primary panel's row click handlers use `useRouter().push(row.href)` — the href is derived from the same `go` field in the mockup's `pRows`.

---

### [SP-05] Annotation Workspace

**Domain**: `portal-annotation`

**Scope**
The annotation screen for annotators and tenant admins. Two layout modes (3-pane and focus), a token-click labeling model where words in the document are colored and clickable, an entity type palette, a span inspector for selected spans (with retype and delete), a suggestion panel for pre-labeled spans (promote/dismiss), a pre-label trigger, and annotation task status transitions (unannotated → in-progress → completed).

**Requirement Coverage**
From the mockup annotation section (lines 283–429) and `annoVals()` method (lines 929–991): task queue (left column), document viewer with token-level span coloring (middle), entity type palette with armed-type highlighting and span counts (right), span inspector panel (char_start, char_end, confidence, retype buttons, delete), suggestion groups (dashed border, promote/dismiss), pre-label button, armed-mode banner, and task status segment control. From `openspec/specs/annotation-workspace/spec.md`: Span CRUD, task management, dataset export, pre-labeling specs.

**Evidence**
Demonstrated by: (1) clicking a word while an entity type is armed creates a confirmed span via `POST /documents/{id}/spans`; (2) clicking a confirmed span (no armed type) opens the span inspector; (3) "Pre-label" triggers `POST /documents/{id}/prelabel` and renders suggestions with dashed styling; (4) "Promote" on a suggestion calls `POST /documents/{id}/spans/promote/{suggest_id}`; (5) completing a task validates at least one confirmed span exists then calls `PATCH /annotation-tasks/{id}`.

**NFRs**
- Document text rendering must handle 1000+ tokens without layout jank — use CSS `flex-wrap` token layout (matching the mockup's `docRows` approach) not a virtualized list.
- Span coloring must update optimistically on click (no API round-trip delay visible to user).
- The floating label palette in focus mode must be `position: fixed` and not overlap scrolled content.

**Constraints**
- The mockup's token model is word-granular (split on whitespace). The annotation service stores char-based offsets (`char_start`, `char_end`). The frontend must convert: given the document text and a list of confirmed spans, reconstruct which token indices map to which span, and convert a token click back to `char_start`/`char_end` offsets.
- The document text is fetched from `GET /api/v1/documents/{id}/text` (document service port 8001). This endpoint must exist — verify against `src/document_service/api/v1/documents.py` before building.
- Span inspector "retype" currently calls `PATCH /documents/{id}/spans/{span_id}` with a new `entity_type`. Confirm this endpoint is implemented.

**Assumptions**
- The left queue panel shows annotation tasks from `GET /api/v1/annotation-tasks` filtered to the current user's assigned tasks.
- Only one document is active at a time; switching documents in the queue resets span state.
- Span groups (consecutive same-type tokens) are computed client-side from the flat span list — not a backend concept.
- The "3-pane vs Focus" layout mode preference is stored in `localStorage`.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET  /api/v1/annotation-tasks                          → annotation :8002
GET  /api/v1/documents/{id}/text                       → document :8001
GET  /api/v1/documents/{id}/spans                      → annotation :8002
POST /api/v1/documents/{id}/spans                      → annotation :8002
PATCH /api/v1/documents/{id}/spans/{span_id}           → annotation :8002
DELETE /api/v1/documents/{id}/spans/{span_id}          → annotation :8002
POST /api/v1/documents/{id}/prelabel                   → annotation :8002
POST /api/v1/documents/{id}/spans/promote/{suggest_id} → annotation :8002
GET  /api/v1/documents/{id}/spans?type=suggested       → annotation :8002
PATCH /api/v1/annotation-tasks/{id}                    → annotation :8002
GET  /api/v1/entity-types                              → gateway :8000

// Core state types
interface TokenSpan { tokenIndex: number; entityTypeId: string; spanId: string }
interface Suggestion { tokenIndex: number; entityTypeId: string; suggestId: string }
```

**Prerequisites**: [SP-03]

**Implementation Notes**
- Keep span state in a local `useReducer` (not TanStack Query cache) for optimistic updates. Sync with server on mount and after each mutation.
- The char-offset ↔ token-index conversion: tokenize the raw document text with the same `str.split()` logic used by the backend (annotation service export uses this). Compute `char_start` as `tokens.slice(0, tokenIndex).join(' ').length + tokenIndex` (accounting for spaces).
- The armed-type banner and escape-to-disarm (`onDisarm`) should respond to `keydown: 'Escape'` globally while the annotation screen is mounted.
- In focus mode, the floating panel (`position: fixed; top: 140px; right: 30px`) should be hidden when the inspector has nothing selected.

---

### [SP-06] Tenant Management

**Domain**: `portal-tenants`

**Scope**
System-admin-only screen at `/admin/tenants`. Paginated tenant table with status filter tabs and per-row quota mini-bars. A detail slide-over showing quota usage and a deactivate/reactivate danger zone. A create-tenant slide-over with name, auto-generated slug, and quota inputs.

**Requirement Coverage**
From the mockup `isTenants` section (lines 431–532) and `tenantVals()` method (lines 994–1032): tenant table with columns (name/slug, status badge, users progress, docs progress, storage progress, model count, chevron), filter tabs (all/active/inactive with counts), detail slide-over (quota bars, created date, deactivate/reactivate button, danger zone note), create slide-over (name input, read-only slug preview, 4 quota number inputs, submit with loading spinner). From `README.md` Admin section: `GET/POST /api/v1/admin/tenants`, `GET /api/v1/admin/tenants/{id}`, `PUT /api/v1/admin/tenants/{id}`, `POST /api/v1/admin/tenants/{id}/deactivate`.

**Evidence**
Demonstrated by: (1) the table lists all tenants with live quota bars; (2) clicking a row opens the detail slide-over fetching `GET /admin/tenants/{id}` for user count; (3) "Deactivate tenant" calls `POST /admin/tenants/{id}/deactivate` and reflects `status: inactive` immediately; (4) "Create tenant" submits `POST /admin/tenants` and the new row appears with a highlight animation.

**NFRs**
- The create form slug must auto-generate from the name field in real time (matching `slugify()` from the mockup: lowercase, non-alphanumeric → `-`, trim leading/trailing `-`).
- Quota mini-bars use color thresholds: `< 70%` → primary, `70–84%` → warn, `≥ 85%` → bad (matching mockup's `barColor()` function).
- The screen is only reachable by `system_admin` — `<RequireAuth roles={["system_admin"]}>` wraps the page.

**Constraints**
- No `user_count` in the list endpoint response — the detail slide-over must call `GET /admin/tenants/{id}` to get it. The list view shows only data from the list response.
- Pagination: the API uses `page` + `per_page` offset pagination. Implement simple previous/next controls. Cursor-based pagination shown in the mockup is a label-only detail; the API is offset-based.

**Assumptions**
- The detail slide-over does not allow editing quotas inline — a separate "Edit" action (calling `PUT /admin/tenants/{id}`) is a stretch goal, not required for this spec.
- The `fresh` row highlight (primary-soft background on newly created tenants) fades after 3 seconds via a CSS animation.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET  /api/v1/admin/tenants                  → gateway :8000
GET  /api/v1/admin/tenants/{id}             → gateway :8000
POST /api/v1/admin/tenants                  → gateway :8000
POST /api/v1/admin/tenants/{id}/deactivate  → gateway :8000
```

**Prerequisites**: [SP-03]

**Implementation Notes**
- TanStack Query `invalidateQueries(["tenants"])` after create/deactivate to trigger list refetch.
- The slide-over uses the shared `<SlideOver>` from SP-01 (`width: 420` for detail, `440` for create — matching mockup pixel values).
- Deactivate button is always visible in the danger zone but shows "Reactivate tenant" when status is already inactive — same endpoint logic applies via the current `POST .../deactivate` toggle behavior.

---

### [SP-07] Training Jobs

**Domain**: `portal-training`

**Scope**
Training job screen at `/training` for tenant admins and system admins. A filterable job list (left column) and a detail panel (right). Detail panel shows: status timeline, live epoch/loss progress bar (polling for running jobs), hyperparameter grid, evaluation metrics with bar charts, dataset→job→model lineage strip, MLflow run deep link, and role-gated action buttons (approve/reject for system_admin; cancel for tenant_admin). A "Submit job" slide-over with hyperparameter form.

**Requirement Coverage**
From the mockup `isTraining` section (lines 534–688) and `trainVals()` method (lines 1035–1097): job list cards with animated pulse dot for running jobs, filter tabs (all/running/pending_approval/completed/failed), detail panel with timeline dots (`dTimeline`), running progress block with animated bar, metric gauges (`dMetrics`), lineage strip, MLflow anchor tag, action buttons (`dActions`) gated by `isAdmin`. Submit slide-over: learning_rate input, num_epochs range slider (1–50), batch_size + max_seq_length grid, 500-span preflight check banner. From `README.md` Training section: full job lifecycle, approve/reject/cancel endpoints.

**Evidence**
Demonstrated by: (1) the list shows live job statuses; (2) selecting a running job shows the epoch progress bar advancing via polling; (3) system_admin sees "Approve & queue" + "Reject" for a `pending_approval` job; (4) tenant_admin sees "Cancel request" for the same job; (5) submitting the new-job form with < 500 spans shows the error state; with ≥ 500 spans, calls `POST /training-jobs` and the new card appears as `pending_approval`.

**NFRs**
- Epoch polling interval: `refetchInterval: 5_000` only when the selected job has `status === "running"`.
- The `growBar` animation on metric bars must re-trigger when the selected job changes — use a `key={selectedJobId}` prop on the metrics container.

**Constraints**
- The span-count preflight check (`GET /annotation-export` or a span count query) must be performed before the submit form is shown — not after submit. The mockup shows "812 confirmed spans · meets the 500-span minimum" as a pre-check banner. The backend enforces this server-side too (returns 422 if < 500), so client-side is a UX check only.
- The `?tenant_id=<uuid>` query param on approve/reject requires the frontend to know the tenant's UUID. This comes from the JWT `tenant_id` claim for `tenant_admin`; for `system_admin` approving another tenant's job, it comes from the job record's `tenant_id` (currently not returned by `GET /training-jobs` — flag as a potential backend gap).

**Assumptions**
- The span count for the preflight is fetched by counting spans from `GET /annotation-export` response lines — a JSONL count. An alternative is a dedicated count endpoint; if unavailable, the check calls `GET /annotation-export` and counts newlines.
- `tFilter` (the status filter) is URL-searchable (`?status=running`) for deep-linking from the dashboard primary panel rows.
- The MLflow run URL in the detail panel opens in a new tab (`target="_blank"`). It uses the `mlflow_run_url` field from the job response, which is computed server-side from `NER_MLFLOW_TRACKING_URI`.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET  /api/v1/training-jobs                          → training :8003
GET  /api/v1/training-jobs/{id}                     → training :8003
POST /api/v1/training-jobs                          → training :8003
POST /api/v1/training-jobs/{id}/cancel              → training :8003
POST /api/v1/training-jobs/{id}/approve?tenant_id=  → training :8003
POST /api/v1/training-jobs/{id}/reject?tenant_id=   → training :8003
GET  /api/v1/annotation-export                      → annotation :8002 (span preflight)
```

**Prerequisites**: [SP-03]

**Implementation Notes**
- Conditional polling: `useQuery({ ..., refetchInterval: selectedJob?.status === "running" ? 5000 : false })`.
- The timeline dots are derived client-side from the job status using the same chain logic as the mockup (`lifecycle` array, `failOrder` map). Encode this as a pure `getTimeline(status)` utility function.
- The new-job slide-over uses a `<input type="range">` for epochs with an `accent-color: var(--primary)` Tailwind custom CSS — verify Tailwind's `accent-*` utilities cover this.

---

### [SP-08] Documents

**Domain**: `portal-documents`

**Scope**
Document management screen at `/documents` for tenant_admin, annotator, and business_user. A paginated document list with status filter and per-row status badges. A file upload area (drag-drop + click-to-browse) with file type/size validation. Soft delete. Auto-polling for documents in `pending` or `processing` status.

**Requirement Coverage**
From the mockup nav config (documents appears for all non-system_admin roles). From `README.md` Document Ingestion section: `POST /api/v1/documents` (multipart, ≤50MB, accepted types: pdf/jpg/jpeg/png/tif/tiff), `GET /api/v1/documents` (paginated, status filter), `GET /api/v1/documents/{id}`, `DELETE /api/v1/documents/{id}` (soft delete → `status: deleted`). Response includes `filename`, `content_type`, `file_size`, `status` (pending/processing/processed/deleted/failed), `created_at`, `blob_path`.

**Evidence**
Demonstrated by: (1) dragging a PDF onto the upload zone calls `POST /documents` and the new row appears with `status: pending`; (2) the status auto-updates to `processed` within the polling window; (3) attempting to upload a `.exe` shows an inline error before the API is called; (4) soft delete marks the row as `deleted` and removes it from the active filter.

**NFRs**
- Upload shows a progress bar using the `XMLHttpRequest.upload.onprogress` event (not `fetch`, which doesn't support upload progress).
- File size validated client-side before upload (reject > 50MB with an inline error, not a toast).
- Status polling: `refetchInterval: 3_000` while any document in the list has `status: "pending"` or `status: "processing"`.

**Constraints**
- The design follows the mockup's table+slide-over visual language (see Tenants table as the reference). There is no mockup screen for documents specifically — the column layout should be: filename, content type, size, status badge, created date, delete button.
- No document preview in this spec. Clicking a document row navigates to the annotation screen with that document pre-selected (future integration point).

**Assumptions**
- Pagination uses `page` + `per_page` offset controls (previous/next).
- Status filter tabs: All, Pending, Processing, Processed, Failed (matching `documents.status` enum values; "deleted" not shown by default).
- The drag-drop zone is always visible above the table, not a slide-over.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET    /api/v1/documents           → document :8001
POST   /api/v1/documents           → document :8001 (multipart/form-data)
GET    /api/v1/documents/{id}      → document :8001
DELETE /api/v1/documents/{id}      → document :8001
```

**Prerequisites**: [SP-03]

**Implementation Notes**
- Use `XMLHttpRequest` in a custom `useUpload()` hook to get upload progress. Wrap in a `useMutation`-compatible interface for TanStack Query integration.
- Accepted MIME types for the `<input type="file">` accept attribute: `"application/pdf,image/jpeg,image/png,image/tiff"`.
- Drag-drop: `onDragOver` / `onDrop` on the zone `div`; call `e.preventDefault()` on both. Visual state change (border highlight) via a `isDragging` boolean state.

---

### [SP-09] Entity Types

**Domain**: `portal-entity-types`

**Scope**
Entity type configuration screen at `/entity-types` for tenant_admin. A list of all entity types (active and inactive) with an active/inactive filter. A create/edit slide-over with fields for name, description, examples (tag-input), base_label_mapping (multi-select checkboxes for PER/ORG/LOC/MISC), and required/target_table fields. Soft delete (deactivate).

**Requirement Coverage**
From `README.md` Entity Types section: `POST /api/v1/entity-types` (name required; optional description, examples, validation_rule, target_table, base_label_mapping, required_flag), `GET /api/v1/entity-types` (?is_active filter), `GET /api/v1/entity-types/{id}`, `PUT /api/v1/entity-types/{id}` (increments version), `DELETE /api/v1/entity-types/{id}` (sets is_active: false). The `base_label_mapping` keys must be one of: `PER`, `ORG`, `LOC`, `MISC`.

**Evidence**
Demonstrated by: (1) the list shows entity types with version number, active status badge, and base_label_mapping displayed as CoNLL label chips; (2) creating a new type via the slide-over with `base_label_mapping: { "ORG": ["vendor_name"] }` succeeds and the new type appears; (3) submitting an invalid label key like `INVALID` shows the 422 error inline; (4) deactivating a type sets `is_active: false` and the badge changes.

**NFRs**
- The examples field should be a tag-input (press Enter to add, click × to remove). Stored as a JSON array in the API.
- `base_label_mapping` UI: four checkboxes (PER, ORG, LOC, MISC) — checking one adds the entity type name as a value under that key in the mapping object.

**Constraints**
- `base_label_mapping` is a `Record<"PER"|"ORG"|"LOC"|"MISC", string[]>`. The UI simplifies this to: which CoNLL labels map to this entity type. The value array always contains just the entity type's own name.
- Version number increments on every `PUT` — display it in the list but do not expose it as an editable field.

**Assumptions**
- The create and edit actions share the same slide-over form component (`<EntityTypeForm>`), with the edit pre-populated from `GET /entity-types/{id}`.
- The `validation_rule` and `target_table` fields are text inputs with no special validation on the frontend.
- No bulk operations in this spec.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET    /api/v1/entity-types           → gateway :8000
GET    /api/v1/entity-types/{id}      → gateway :8000
POST   /api/v1/entity-types           → gateway :8000
PUT    /api/v1/entity-types/{id}      → gateway :8000
DELETE /api/v1/entity-types/{id}      → gateway :8000
```

**Prerequisites**: [SP-03]

---

### [SP-10] Model Registry

**Domain**: `portal-model-registry`

**Scope**
Model version screen at `/models` for tenant_admin and business_user. A list of all model versions ordered by version number (descending) with status lifecycle badges. A detail view (inline or side panel) showing evaluation metrics (F1, precision, recall, loss), artifact path, MLflow run link, and promote/demote/warmup action buttons. Only one model can be `promoted` at a time.

**Requirement Coverage**
From `README.md` Model Registry section: `GET /api/v1/models` (all versions, descending), `GET /api/v1/models/active` (promoted model), `POST /api/v1/models/{id}/promote` (auto-archives existing promoted; triggers warmup), `POST /api/v1/models/{id}/demote`, `POST /api/v1/models/{id}/warmup`. Status lifecycle: `training → completed → promoted → archived`. Metrics: `eval_loss`, `eval_precision`, `eval_recall`, `eval_f1`. The `promote` endpoint calls model-serving warmup internally — frontend just calls promote and shows the result.

**Evidence**
Demonstrated by: (1) the list shows all versions with correct status badges and metrics; (2) the `promoted` version is visually distinct (primary badge); (3) clicking "Promote" on a `completed` model calls `POST /models/{id}/promote`, the previously promoted version becomes `archived`, and the new one becomes `promoted`; (4) the MLflow run link opens in a new tab; (5) "Warmup" on a non-active version shows success toast.

**NFRs**
- Only `tenant_admin` sees the promote/demote/warmup action buttons. `business_user` sees the list as read-only.
- After promote, invalidate both the list query and the active model query to update the dashboard secondary panel.

**Constraints**
- The `mlflow_run_url` field is computed server-side from `NER_MLFLOW_TRACKING_URI`. In development, this is `http://localhost:5000/...`. The frontend renders this as a link without transformation.
- Demote is only available on `promoted` models. Promote is only available on `completed` models. These guards exist server-side too (return 422 otherwise) — the UI hides the inappropriate button to avoid the round-trip.

**Assumptions**
- The layout follows the mockup's two-column pattern (list + detail). When no model is selected, the detail panel shows an empty state.
- Per-entity metrics (e.g. `vendor_name_f1`) from the training metrics object are displayed in a collapsible section below the main metrics grid, not all shown by default.

**Contracts / Interfaces**
```ts
// Consumed APIs
GET  /api/v1/models               → training :8003
GET  /api/v1/models/active        → training :8003
POST /api/v1/models/{id}/promote  → training :8003
POST /api/v1/models/{id}/demote   → training :8003
POST /api/v1/models/{id}/warmup   → training :8003
```

**Prerequisites**: [SP-03]

---

### [SP-11] Users

**Domain**: `portal-users`

**Scope**
User management screen at `/users` for tenant_admin. A list of all users in the tenant with role and status. A create-user slide-over (email, password, role selector). Inline role/status update. Soft delete (deactivate → `status: inactive`).

**Requirement Coverage**
From `README.md` Users section: `GET /api/v1/tenants/{slug}/users` (?role filter), `POST /api/v1/tenants/{slug}/users` (email, password, role — with password rules: min 8 chars, 1 upper, 1 lower, 1 digit), `GET /api/v1/tenants/{slug}/users/{uid}`, `PUT /api/v1/tenants/{slug}/users/{uid}` (role/status), `DELETE /api/v1/tenants/{slug}/users/{uid}` (soft delete). Quota enforced: 429 if `max_users` exceeded.

**Evidence**
Demonstrated by: (1) the list shows all tenant users with role badges and active/inactive status; (2) creating a user with a weak password shows inline validation before calling the API; (3) creating a user when at quota limit shows the 429 error in a toast; (4) updating a user's role via an inline dropdown calls `PUT .../users/{uid}`; (5) deactivating a user sets `status: inactive`.

**NFRs**
- Password rules must be validated client-side in real time (same rules as backend: length ≥ 8, ≥1 upper, ≥1 lower, ≥1 digit) with an indicator row per rule.
- The `tenant_slug` needed for all user API endpoints is derived from the JWT `tenant_id` claim. The gateway resolves slug from the URL — use the slug stored from the login response or fetch it from `GET /admin/tenants/{id}` on auth init.

**Constraints**
- The user API routes use `{slug}` not `{tenant_id}`. The JWT carries `tenant_id` (UUID). Either store the slug at login time (it's in the login response under `user.tenant_slug`) or call `GET /admin/tenants/{id}` to resolve it. The login response currently returns `tenant_slug: null` for `system_admin` — handle this edge case.
- Only `tenant_admin` can access this screen — `system_admin` creates users via a different flow (not in scope).

**Assumptions**
- Role selector for create/update: `["tenant_admin", "business_user", "annotator"]` — cannot create a `system_admin` from this screen.
- The current user cannot deactivate their own account (guard client-side by comparing `uid` with `useAuth().user.userId`).
- No pagination required (most tenants have ≤ 25 users by quota). Show all users in a single list.

**Contracts / Interfaces**
```ts
// Consumed APIs (slug resolved from auth context)
GET    /api/v1/tenants/{slug}/users          → gateway :8000
POST   /api/v1/tenants/{slug}/users          → gateway :8000
PUT    /api/v1/tenants/{slug}/users/{uid}    → gateway :8000
DELETE /api/v1/tenants/{slug}/users/{uid}    → gateway :8000
```

**Prerequisites**: [SP-03]

---

## Dependency Order (Suggested Implementation Sequence)

```
Wave 1 — Infrastructure (no prerequisites):
  SP-01  Project Foundation & Design System

Wave 2 — Auth (depends on Wave 1):
  SP-02  Auth Flow
  ↳ Backend prerequisite (parallel): add Set-Cookie to gateway auth.py

Wave 3 — Shell (depends on Wave 2):
  SP-03  App Shell

Wave 4 — Screens (all depend on Wave 3, parallelisable):
  SP-06  Tenant Management     ← mockup-faithful, system_admin critical path
  SP-07  Training Jobs         ← mockup-faithful, most complex API surface
  SP-05  Annotation Workspace  ← most complex UI logic
  SP-04  Dashboard             ← composite; benefits from SP-06/07 done first
  SP-08  Documents             ← simpler CRUD, unblocks annotation workflow
  SP-09  Entity Types          ← simpler CRUD
  SP-10  Model Registry        ← simpler CRUD + promote/demote
  SP-11  Users                 ← simpler CRUD
```

---

## Cross-Cutting Concerns

**API client layer** (`src/portal/lib/api.ts` — from SP-02):
- `authFetch(url, init)` attaches `Authorization: Bearer <token>`, handles 401 by refreshing once, retries. All screen specs use this, never raw `fetch`.
- Service URL prefixes are configured via `NEXT_PUBLIC_*` env vars (e.g. `NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000`). SP-01 creates `.env.local.example`.

**Error handling**:
- 4xx errors (except 401): show inline error message in the form/panel where the action was triggered. Use the `error.code` + `error.message` from the standard `{ "error": { "code", "message", "request_id" } }` envelope.
- 5xx / network errors: show a toast via `useToast()` from SP-01.
- 401 after refresh fails: redirect to `/login` with a toast "Session expired".

**Role-based access**:
- `<RequireAuth roles={[...]}>` from SP-02 wraps restricted pages.
- Role-gated UI elements (approve/reject buttons, tenant deactivate, etc.) are conditionally rendered based on `useAuth().user.role`.
- `system_admin` has a special `tenant_id: "system"` in the JWT — handle this in screens that require a real tenant UUID.

**Loading and empty states**:
- All list screens show skeleton rows (3–5 rows of `animate-pulse` blocks) while loading — use `isFetching` from TanStack Query.
- Empty states show a centered message + contextual CTA (e.g. "No documents yet — upload your first document").

**Toast system** (from SP-01 `useToast()`):
- `toast(msg, "ok")` — primary color checkmark, 2.6s auto-dismiss.
- `toast(msg, "bad")` — bad color ✕, 2.6s auto-dismiss.
- Positioned `fixed; bottom: 26px; left: 50%; translateX(-50%)` matching the mockup exactly.

**Dark mode**:
- `useDarkMode()` from SP-01 sets `data-theme="dark"` on the root `<div>` in the app layout.
- All CSS variables automatically switch via the `[data-theme="dark"]` block.
- Preference key in `localStorage`: `"ner-theme"`.

**Coding conventions** (from `PROJECT.md`):
- Files: `kebab-case` (TypeScript/React).
- Components: `PascalCase`.
- Functions/methods: `camelCase`.
- No comments unless the WHY is non-obvious.

---

## Recommended Next Step

Run `/opsx:new` to create a new OpenSpec change for Wave 1, starting with **SP-01 (Project Foundation & Design System)**. This is the only spec with no prerequisites — completing it unblocks all subsequent work. The backend gateway change (adding `Set-Cookie` to auth endpoints) can be opened as a parallel change to avoid blocking SP-02.
