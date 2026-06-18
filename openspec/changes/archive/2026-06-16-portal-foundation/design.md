## Context

The NER platform has no frontend today. Six FastAPI microservices are running (gateway:8000, document:8001, annotation:8002, training:8003, model-serving:8004, extraction:8005) with JWT auth embedding `tenant_id`, `user_id`, and `role`. The interactive mockup at `docs/NER Platform.dc.html` defines the target visual language: glassmorphism cards, CSS custom-property colour tokens, a three-font stack, and role-aware navigation.

This design covers the structural layer only — project scaffold, design tokens, shared primitives, and utility hooks. No auth logic, routing, or screen implementations are in scope.

## Goals / Non-Goals

**Goals:**

- Bootstrap `src/portal/` as a Next.js 14 App Router TypeScript workspace
- Define and document all CSS custom-property design tokens in one authoritative file
- Ship eight typed, tested, zero-business-logic UI primitives that all screen specs import
- Establish stable import paths (`@/components/ui`, `@/hooks`, `@/lib/api`) that downstream specs can reference without modification
- Wire dark-mode toggle with class strategy and localStorage persistence
- Define environment variable interface for all six service base URLs

**Non-Goals:**

- JWT authentication or token refresh (SP-02)
- Any route or page beyond the root `layout.tsx` and a placeholder `page.tsx`
- Real API calls (service base-URL constants are defined but no fetches)
- Storybook or design system documentation site
- CI/CD pipeline wiring (separate change)
- SSR data fetching — all components are `"use client"` SPA-style

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 OpenSpec Governance | All changes go through proposal → design → spec → tasks → evidence gates | This document is required before specs and tasks can be written |
| ADR-005 OpenCode Agent Boundaries | Agents must not write code outside their role scope | Implementation must stay in `src/portal/`; no backend files touched |

ADR-001, ADR-002, ADR-003, ADR-006, ADR-007 cover backend concerns and impose no direct constraints on the frontend scaffold.

## Decisions

### Decision 1: SPA-style client components — no Next.js API routes for data

**Choice:** All portal pages and data-fetching components carry `"use client"`. Browsers call microservice endpoints directly. Next.js API routes (`pages/api/` or `app/api/`) are not used.

**Rationale:** The mockup is a single-page JS application. Routing all requests through a Next.js API layer would add latency and duplicate business logic already handled by the gateway service. Direct browser-to-service calls match the existing JWT flow (token sent as `Authorization: Bearer <token>` in every request).

**Alternatives considered:**
- Next.js API routes as a BFF — ruled out: adds a Node.js request hop with no benefit when the gateway already handles auth, rate limiting, and tenant context
- RSC (React Server Components) with server-side data fetching — ruled out: requires access tokens on the server, which conflicts with the chosen auth model (access token in memory only, SP-02)

### Decision 2: Tailwind CSS with CSS custom-property tokens, not plain Tailwind theme values

**Choice:** Design tokens are declared as CSS custom properties on `:root` and `:root.dark` in `globals.css`. The `tailwind.config.ts` references them via `var(--token-name)`. Components use semantic Tailwind classes like `bg-brand-primary` that resolve to `var(--color-brand-primary)`.

**Rationale:** CSS variable tokens allow the dark-mode swap to happen in a single class toggle on `<html>` without any JS-based colour injection or re-render cascade. This also future-proofs tenant-specific theming (a future change could inject per-tenant CSS variables without rebuilding the component library).

**Alternatives considered:**
- Plain Tailwind theme values with `dark:` prefix utilities — ruled out: each component would need dual `dark:` variants for every colour, making components verbose and coupling them to the dark/light dichotomy explicitly
- CSS-in-JS (styled-components, Emotion) — ruled out: conflicts with App Router's server component model and is not in the project stack (PROJECT.md specifies Tailwind)

### Decision 3: Dark-mode strategy — `class` on `<html>`, persisted to localStorage

**Choice:** `tailwind.config.ts` sets `darkMode: "class"`. The `useDarkMode` hook reads from `localStorage` on mount, applies or removes the `dark` class on `document.documentElement`, and writes back on toggle. SSR mismatch is suppressed by mounting only after hydration.

**Rationale:** The mockup has a first-class dark toggle. `class`-based strategy gives full control without relying on the OS `prefers-color-scheme` media query, which the user may not want to follow. localStorage persistence survives page refreshes.

**Alternatives considered:**
- `media` strategy (Tailwind's default) — ruled out: no user-controllable toggle; OS preference overrides the UI button
- Cookie-based persistence with server-side class injection — ruled out: over-engineered for this SPA; would require a middleware and adds SSR complexity

### Decision 4: Font loading via `next/font/google`, not CDN link tags

**Choice:** `Hanken_Grotesk`, `Inter`, and `JetBrains_Mono` are imported from `next/font/google` in `layout.tsx` and exposed as CSS variables (`--font-display`, `--font-body`, `--font-mono`) referenced in `tailwind.config.ts`.

**Rationale:** `next/font/google` self-hosts fonts at build time (zero external font requests at runtime), eliminates FOUT, and is the idiomatic Next.js 14 approach. Fonts become CSS variables so any component can reference them without prop drilling.

**Alternatives considered:**
- Google Fonts `<link>` in `<head>` — ruled out: external network dependency at runtime; blocked by strict CSP policies common in enterprise deployments
- Local font files checked into the repo — ruled out: large binary blobs in git history; `next/font/google` handles caching automatically

### Decision 5: Primitive components co-located in `src/portal/src/components/ui/`, not a separate package

**Choice:** All eight primitives live inside the portal workspace. They are not published to an npm registry or extracted to a `packages/ui` shared package.

**Rationale:** There is only one frontend consumer (the portal). Extracting to a shared package adds a publish/link cycle and build complexity with no current benefit. If a second frontend surface emerges, extraction is straightforward.

**Alternatives considered:**
- `packages/ui` monorepo package — ruled out: premature abstraction; YAGNI
- Third-party component library (shadcn/ui, Radix) — ruled out: the mockup's visual language (glassmorphism, specific token names, tight role-variant logic) would require heavy overrides, adding complexity and bundle weight for uncertain gain

### Decision 6: `authFetch` stub — interface only in this change

**Choice:** `src/portal/src/lib/auth-fetch.ts` exports the function signature and type (`authFetch(url, init?) → Promise<Response>`) with a pass-through implementation. SP-02 replaces the body with real token injection and refresh logic.

**Rationale:** Screen specs (SP-03 onward) must import `authFetch` at known paths. Defining the stub here allows spec authors to write components that compile and test in isolation before SP-02 is merged. The pass-through body avoids phantom errors in development.

**Alternatives considered:**
- Leave `authFetch` entirely to SP-02 — ruled out: screen specs would have a compile-time dependency on SP-02 merging first, serialising parallel work
- Export just the type, no implementation — ruled out: TypeScript module imports don't resolve if the runtime export is missing; a stub avoids this

## Risks / Trade-offs

- [Dark-mode hydration flicker] → Apply an inline `<script>` in `layout.tsx` before the `<body>` that reads localStorage and sets the `dark` class synchronously, preventing the flash. This is a Next.js-standard pattern.
- [CSS variable names diverge from mockup as the design evolves] → Token names are finalised in `design-tokens` spec (owned by this change). A one-time audit against the mockup HTML before merge is the mitigation.
- [Font loading adds to bundle] → `next/font/google` is display-swap by default; LCP impact is bounded. Acceptable for an internal platform.
- [Co-located primitives can't be shared across future portals] → Accepted; YAGNI. Extraction path is documented above.

## Migration Plan

This is a net-new directory with no existing code to migrate.

1. Create `src/portal/` workspace and install dependencies
2. Add `"src/portal"` to `workspaces` in root `package.json`
3. Implement scaffold, tokens, primitives, and hooks per task list
4. Verify `npm run build` and `npm test` pass inside `src/portal/`
5. No rollback needed — all changes are additive and isolated to `src/portal/`

## Open Questions

- Should the root `package.json` gain a `workspaces` field, or should `src/portal/` be fully standalone (own `node_modules`, not linked)? The team is small (1-3); a workspace root reduces duplication. Proceeding with workspace entry; adjust if Turborepo is adopted later.
- The mockup uses a `backdrop-filter: blur(...)` glassmorphism style that may degrade on Safari iOS 15 and below. Acceptable for an internal tool; revisit if mobile browser support becomes a requirement.
