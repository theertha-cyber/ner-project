## Why

The NER platform has six backend microservices but no frontend. Without a bootstrapped Next.js project, shared design tokens, and reusable UI primitives, every subsequent screen spec (SP-02 through SP-11) would have to rediscover font choices, colour values, and component contracts independently — causing drift and rework. This change establishes the single foundational layer all screen work depends on.

## What Changes

- New monorepo workspace `src/portal/` — Next.js 14 App Router project (TypeScript, ESLint, Prettier)
- Tailwind CSS configured with CSS custom-property design tokens mirroring the mockup's colour, typography, and spacing palette
- `next/font/google` wired for Hanken Grotesk (display), Inter (body), and JetBrains Mono (code/label)
- Dark-mode class strategy (`class` strategy via `darkMode`) with `useDarkMode` hook persisted to `localStorage`
- Shared UI primitive library under `src/portal/src/components/ui/`: Badge, StatCard, SlideOver, MiniBar, SegmentControl, Spinner, PlaceholderScreen
- `useToast` hook with a `<ToastProvider>` rendering ephemeral `ok`/`bad` notification banners
- `authFetch` interceptor stub (interface only — no JWT logic; that is SP-02) so primitives can be authored against a stable import path
- `src/portal/src/lib/api.ts` exporting typed base-URL constants for all six services (values from environment variables)

No business logic, no authentication, no API calls beyond stub constants.

## Capabilities

### New Capabilities

- `project-scaffold`: Next.js 14 App Router workspace at `src/portal/` — `package.json`, `tsconfig.json`, `next.config.ts`, `tailwind.config.ts`, `postcss.config.js`, `.eslintrc.json`, `prettier.config.js`, root `layout.tsx` with font and provider wiring, `globals.css` with Tailwind directives and CSS variable declarations.
- `design-tokens`: Full token set defined as CSS custom properties in `globals.css` and referenced in `tailwind.config.ts` — colour palette (primary brand blue, neutral greys, semantic status colours), radius scale, shadow levels, and the three-font stack. Tokens map 1-to-1 to the mockup's glassmorphism and status-chip visual language.
- `ui-primitives`: Eight stateless React components exported from `src/portal/src/components/ui/index.ts` — `Badge`, `StatCard`, `SlideOver`, `MiniBar`, `SegmentControl`, `Spinner`, `PlaceholderScreen` — each typed, Tailwind-styled, and covered by Vitest + Testing Library unit tests.
- `utility-hooks`: `useDarkMode` (class toggle + localStorage persistence) and `useToast` (imperative toast API over a `ToastProvider`) — both exported from `src/portal/src/hooks/`.

### Modified Capabilities

*(none — no existing specs)*

## Impact

- **New directory**: `src/portal/` — no existing service code touched
- **Package manager**: `npm` workspace entry added to the root `package.json` (`workspaces: ["src/portal"]`)
- **Environment variables**: `.env.local.example` in `src/portal/` documents `NEXT_PUBLIC_GATEWAY_URL`, `NEXT_PUBLIC_DOCUMENT_URL`, `NEXT_PUBLIC_ANNOTATION_URL`, `NEXT_PUBLIC_TRAINING_URL`, `NEXT_PUBLIC_MODEL_SERVING_URL`, `NEXT_PUBLIC_EXTRACTION_URL`
- **Dependencies**: SP-02 (auth) and all screen specs (SP-03 through SP-11) import from the primitives and hooks defined here; this change must be merged before any of them can start
- **No backend changes** in this change

## Open Questions

- Should `src/portal/` be a standalone npm workspace entry in the root `package.json`, or use a separate `apps/portal/` directory following Turborepo conventions? (Proceeding with `src/portal/` per PROJECT.md repo structure — revisit if the team adopts Turborepo.)
- Token names: the mockup uses inline hex values. Token aliases (e.g. `--color-brand-primary`) will be derived from visual inspection of `docs/NER Platform.dc.html`. If the design ever gets Figma variables, a re-mapping pass will be needed.
