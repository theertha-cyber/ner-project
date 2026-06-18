## Context

The portal currently has a working login flow (SP-02) and a bare `/dashboard` redirect page, but no persistent chrome. Every authenticated route is a blank canvas. All eight feature screens planned for SP-04 through SP-11 need a shared layout that provides sidebar navigation, screen identity (title + path in the topbar), dark mode, and role-aware UI. Without this shell, each feature spec would have to re-implement navigation independently, creating divergence.

Current file layout that this change reorganises:

```
app/
  layout.tsx          ← root (keeps AuthProvider, fonts)
  page.tsx            ← root placeholder (stays)
  admin/
    layout.tsx        ← existing role-guard (will be absorbed)
    page.tsx          ← redirect to /admin/tenants
    tenants/…         ← existing pages (move)
    jobs/…            ← existing pages (move)
  login/page.tsx      ← SP-02 (stays, unauthenticated)
  dashboard/page.tsx  ← SP-02 router (move)
```

After this change:

```
app/
  layout.tsx          ← root (unchanged)
  page.tsx            ← root placeholder (unchanged)
  (auth)/
    layout.tsx        ← NEW: RequireAuth + AppShell
    dashboard/page.tsx
    admin/
      page.tsx
      tenants/…
      jobs/…          ← (renamed from jobs → training-jobs below)
    annotation/page.tsx   ← placeholder
    training-jobs/page.tsx ← placeholder
    models/page.tsx   ← placeholder
    documents/page.tsx ← placeholder
    entity-types/page.tsx ← placeholder
    users/page.tsx    ← placeholder
    extractions/page.tsx ← placeholder
    audit/page.tsx    ← placeholder
    settings/page.tsx ← placeholder
  login/
    page.tsx          ← stays (public)
```

## Goals / Non-Goals

**Goals:**
- Single authenticated layout (`app/(auth)/layout.tsx`) that applies `RequireAuth` and `AppShell` to every nested route.
- Sidebar: 248 px, sticky full-height, logo + tenant pill + role-nav + user strip.
- Topbar: 62 px, screen title + JetBrains Mono path, search placeholder, role-switcher (DEMO_MODE only), dark mode toggle, avatar.
- Role-nav matrix (`navFor`) for all four roles matching the mockup exactly.
- Placeholder screens for every nav item without an implemented screen.
- Migrate existing admin pages with no URL change.
- Active nav highlight driven by `usePathname()`.

**Non-Goals:**
- Tenant-switch flow — the tenant pill is display-only.
- Command palette / ⌘K search — visual placeholder only.
- Responsive / mobile layout — desktop-first, no hamburger menu.
- Dashboard, annotation, training, or any feature screen content — those are SP-04+.
- Badge counts from live APIs — static counts in `navFor` (will be replaced in SP-04).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via separate DB schemas | Sidebar must display tenant context from JWT (`tenantSlug`, `tenantName`) — never cross-tenant data |
| ADR-004 | OpenSpec spec-driven governance | Shell layout is implemented under this change's spec; no ambient code outside reviewed artifacts |
| ADR-005 | Agent permission boundaries | Role-switcher is a developer convenience — must be gated so it cannot appear in production (`NEXT_PUBLIC_DEMO_MODE`) |

## Decisions

### Decision 1: Next.js `(auth)` route group for the authenticated layout

**Choice:** Use a parenthesised route group `app/(auth)/` so all authenticated routes share one `layout.tsx` without the group name appearing in the URL.

**Rationale:** Next.js App Router route groups are the idiomatic way to apply a shared layout to a set of routes without affecting URL structure. This avoids the brittle approach of wrapping individual page exports in the shell and keeps the URL `/admin/tenants` unchanged after the migration.

**Alternatives considered:**
- Wrap each page manually in `<AppShell>` — rejected: requires touching every page and creates divergence risk.
- Keep the existing `app/admin/layout.tsx` approach and duplicate it for other sections — rejected: each section would need its own layout; no single place to add RequireAuth for all authenticated routes.

### Decision 2: `AppShell` as a single client component, children passed as `{children}`

**Choice:** `AppShell` is a `"use client"` component that reads `useAuth()`, `useDarkMode()`, and `usePathname()`. The `(auth)/layout.tsx` (a Server Component) renders `<RequireAuth><AppShell>{children}</AppShell></RequireAuth>`.

**Rationale:** The sidebar needs live auth state (user email, role, tenant), dark mode state, and the current pathname for active-nav highlighting — all of which require client-side hooks. Isolating this in a single client component keeps server components in the leaf pages.

**Alternatives considered:**
- Full Server Component shell with client islands — rejected: the sidebar needs `useAuth` which is context-based and requires a client boundary anyway.
- Inline everything in `layout.tsx` as client — rejected: Next.js strongly recommends keeping layouts as Server Components where possible; wrapping children in a client component is the standard pattern.

### Decision 3: `navFor(role)` as a pure function in `src/lib/nav-config.ts`

**Choice:** Export a `navFor(role: AuthUser["role"]): NavItem[]` function and a `SCREEN_TITLES` map from a dedicated module. Both `AppShell` and future breadcrumb/head components import from this single source.

**Rationale:** Centralising nav metadata means URL changes, badge updates, or new roles only touch one file. The mockup's `navFor` is already written as a pure function — this is a direct translation.

**Alternatives considered:**
- Inline nav arrays inside `AppShell` — rejected: duplicated if a second consumer (e.g., mobile nav) ever appears; harder to unit test.
- Derive from Next.js route manifest — rejected: overkill; roles, icons, and badge slots are not expressible from file paths alone.

### Decision 4: Role-switcher gated behind `NEXT_PUBLIC_DEMO_MODE`

**Choice:** The topbar role-switcher (SA/TA/AN/BU chips) renders only when `process.env.NEXT_PUBLIC_DEMO_MODE === "true"`, evaluated inline (not a module-level const) so `vi.stubEnv` works in tests.

**Rationale:** Matches the demo-chips pattern already established in the login page (SP-02). ADR-005 requires that ambient developer credentials/conveniences cannot appear in production.

**Alternatives considered:**
- `NODE_ENV !== "production"` — ruled out by user: `NEXT_PUBLIC_DEMO_MODE` is the project-standard gate, allows staging environments to enable/disable independently.

## Risks / Trade-offs

- [Moving files breaks any direct imports] → All imports use `@/…` aliases; `tsconfig.json` paths resolve from `src/`, not from the file tree — no import changes needed for consumers.
- [Existing admin layout's role-guard logic is removed] → The `(auth)/layout.tsx` applies `RequireAuth` globally; the `system_admin`-only guard for `/admin/*` moves into the `(auth)/admin/layout.tsx` using `<RequireAuth roles={["system_admin"]}>`.
- [Placeholder screens may confuse users who navigate to them] → Each placeholder clearly states "Coming soon · <screen name>" and does not render empty or crash.
- [Active nav highlight fails on nested routes] → Use `usePathname().startsWith(item.href)` for prefix matching, not strict equality, so `/admin/tenants/new` still highlights the Tenants item.

## Migration Plan

1. Create `app/(auth)/layout.tsx` with `RequireAuth` + `AppShell`.
2. Move `app/dashboard/page.tsx` → `app/(auth)/dashboard/page.tsx`.
3. Move `app/admin/` → `app/(auth)/admin/` (all pages and sub-layouts); delete old `app/admin/layout.tsx`.
4. Add `app/(auth)/admin/layout.tsx` with `<RequireAuth roles={["system_admin"]}>`.
5. Add placeholder pages for all remaining nav targets.
6. Delete `app/page.tsx` root placeholder (root `/` now falls through to the auth layout's redirect via `dashboard/page.tsx`).

No backend changes. No database migrations. Rollback: revert file moves and delete `(auth)/`.

## Open Questions

- None outstanding. Route migration strategy and demo gate confirmed before design.
