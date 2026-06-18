## 1. Workspace Setup

- [x] 1.1 Add `"src/portal"` to the `workspaces` array in the root `package.json` (create the array if absent)
- [x] 1.2 Create `src/portal/package.json` with `name: "@ner/portal"`, `private: true`, `scripts`: `dev`, `build`, `typecheck`, `lint`, `format`, `test`; declare Next.js 14, React 18, TypeScript 5, Tailwind CSS 3, `@testing-library/react`, `@testing-library/user-event`, `vitest`, `@vitejs/plugin-react`, `jsdom` as dependencies/devDependencies
- [x] 1.3 Create `src/portal/next.config.ts` (TypeScript config, no `src/` dir, App Router, no `output: 'export'`)
- [x] 1.4 Create `src/portal/tsconfig.json` with `"strict": true`, `"moduleResolution": "bundler"`, `"jsx": "preserve"`, and path alias `"@/*": ["./src/*"]`
- [x] 1.5 Create `src/portal/.eslintrc.json` extending `["next/core-web-vitals", "prettier"]`
- [x] 1.6 Create `src/portal/prettier.config.js` with `semi: true`, `singleQuote: false`, `trailingComma: "all"`, `printWidth: 100`
- [x] 1.7 Create `src/portal/postcss.config.js` with `tailwindcss` and `autoprefixer` plugins
- [x] 1.8 Create `src/portal/vitest.config.ts` with `environment: "jsdom"`, `globals: true`, `setupFiles: ["./src/test-setup.ts"]`, React plugin, and `@` path alias resolving to `src/portal/src`
- [x] 1.9 Create `src/portal/src/test-setup.ts` importing `@testing-library/jest-dom/vitest`
- [x] 1.10 Create `src/portal/.env.local.example` documenting all six `NEXT_PUBLIC_*` service URL variables
- [x] 1.11 Run `npm install --workspace=src/portal` and confirm it exits 0 *(verification rows 1, 12)*

## 2. Design Tokens

- [x] 2.1 Create `src/portal/src/app/globals.css` with `@tailwind base/components/utilities` directives and `:root` block declaring all colour tokens: brand group (`--color-brand-primary`, `--color-brand-hover`), surface group (3 tokens), text group (3 tokens), border group (2 tokens), 10 status tokens, 4 feedback tokens, 3 delta tokens
- [x] 2.2 Add `:root.dark` block to `globals.css` overriding all colour tokens with dark-mode counterparts — all 10 status tokens must be present *(verification row 16)*
- [x] 2.3 Add radius tokens to `globals.css` `:root`: `--radius-sm` (4px), `--radius-md` (8px), `--radius-lg` (12px), `--radius-xl` (16px), `--radius-full` (9999px)
- [x] 2.4 Add shadow tokens to `globals.css` `:root`: `--shadow-card` (glassmorphism drop shadow), `--shadow-overlay` (slide-over panel shadow)
- [x] 2.5 Create `src/portal/tailwind.config.ts` with `content: ["./src/**/*.{ts,tsx}"]`, `darkMode: "class"`, and `theme.extend` mapping Tailwind colour keys, fontFamily (`display`, `body`, `mono`), borderRadius, and boxShadow to their corresponding CSS variable tokens *(verification rows 7, 13, 19)*
- [x] 2.6 Audit: search `src/portal/src/` for hardcoded hex colour values outside `globals.css` and confirm none exist *(verification row 13)*

## 3. API Foundations

- [x] 3.1 Create `src/portal/src/lib/api.ts` exporting six typed constants (`GATEWAY_URL`, `DOCUMENT_URL`, `ANNOTATION_URL`, `TRAINING_URL`, `MODEL_SERVING_URL`, `EXTRACTION_URL`) reading from `process.env.NEXT_PUBLIC_*`, defaulting to `""` *(verification rows 8–9)*
- [x] 3.2 Create `src/portal/src/lib/auth-fetch.ts` exporting `authFetch(url: string, init?: RequestInit): Promise<Response>` as a pass-through to `fetch(url, init)` *(verification rows 41–42)*
- [x] 3.3 Write `src/portal/src/lib/api.test.ts`: test that missing env var returns `""` (row 8) and that defined env var is surfaced correctly (row 9)
- [x] 3.4 Write `src/portal/src/lib/auth-fetch.test.ts`: test that `authFetch` calls native `fetch` with the provided URL (row 41)

## 4. Root Layout and Font Wiring

- [x] 4.1 Create `src/portal/src/app/layout.tsx` (`"use client"`) importing `Hanken_Grotesk`, `Inter`, and `JetBrains_Mono` from `next/font/google`; expose them as CSS variables `--font-display`, `--font-body`, `--font-mono` via the `className` on `<html>`; import `globals.css`; wrap `children` with `<ToastProvider>` *(verification rows 10–11)*
- [x] 4.2 Add a synchronous inline `<script>` before `<body>` in `layout.tsx` that reads `localStorage.getItem("portal-theme")` and adds the `dark` class to `document.documentElement` to prevent hydration flicker
- [x] 4.3 Create `src/portal/src/app/page.tsx` rendering `<PlaceholderScreen title="NER Platform" />` as the root placeholder *(unblocks build verification)*

## 5. Utility Hooks

- [x] 5.1 Create `src/portal/src/hooks/use-dark-mode.ts` implementing `useDarkMode()`: read `"portal-theme"` from `localStorage` on mount (default `"light"`), toggle the `dark` class on `document.documentElement`, persist on every toggle *(verification rows 46–50)*
- [x] 5.2 Create `src/portal/src/hooks/use-toast.tsx` implementing `ToastProvider` (context, queue of max 3, `setTimeout` auto-dismiss at 4000 ms with `clearTimeout` in cleanup) and `useToast()` hook that throws "useToast must be used within ToastProvider" when called outside provider *(verification rows 51–56)*
- [x] 5.3 Create `src/portal/src/hooks/index.ts` barrel re-exporting `useDarkMode`, `useToast`, and `ToastProvider` *(verification row 57)*
- [x] 5.4 Write `src/portal/src/hooks/use-dark-mode.test.ts` covering all five `useDarkMode` scenarios (rows 46–50): localStorage init dark, init light, toggle on, persist, toggle revert
- [x] 5.5 Write `src/portal/src/hooks/use-toast.test.tsx` covering all six `useToast` scenarios (rows 51–56): toast appears, ok colour, bad colour, auto-dismiss (fake timers), fourth toast replaces oldest, error outside provider

## 6. UI Primitives

- [x] 6.1 Create `src/portal/src/components/ui/badge.tsx`: `BadgeVariant` union type, `BadgeProps` interface, render a pill with `bg-status-{variant}` Tailwind class, default label from variant string *(verification rows 20–22)*
- [x] 6.2 Create `src/portal/src/components/ui/stat-card.tsx`: `StatCardProps` interface, render label/value/unit/delta/sub; apply `text-delta-up` / `text-delta-warn` / `text-delta-neutral` class based on `deltaDir`; apply `shadow-card` to card container *(verification rows 23–26)*
- [x] 6.3 Create `src/portal/src/components/ui/slide-over.tsx`: translate-based show/hide, backdrop overlay, `role="dialog"` with `aria-modal="true"`, focus-trap on open (focus first focusable element), Escape key listener calling `onClose`, backdrop click calling `onClose`, restore focus to trigger on close *(verification rows 27–30)*
- [x] 6.4 Create `src/portal/src/components/ui/mini-bar.tsx`: compute `clamp(used/max * 100, 0, 100)`%, apply `bg-warning` when ratio ≥ 0.9, otherwise `bg-brand-primary` *(verification rows 31–33)*
- [x] 6.5 Create `src/portal/src/components/ui/segment-control.tsx`: render buttons, apply active class to selected, `onClick` calls `onChange(value)`, Arrow Left/Right key handler moves focus between buttons *(verification rows 34–36)*
- [x] 6.6 Create `src/portal/src/components/ui/spinner.tsx`: animated `border-t` spinner with `size-4` (sm) or `size-6` (md) CSS class *(verification rows 37–38)*
- [x] 6.7 Create `src/portal/src/components/ui/placeholder-screen.tsx`: centred flex container, `<h1>` with `title` prop, sub-text "This screen is coming soon." *(verification rows 39–40)*
- [x] 6.8 Create `src/portal/src/components/ui/index.ts` barrel re-exporting all seven primitives *(verification row 43)*

## 7. Tests for UI Primitives

- [x] 7.1 Write `src/portal/src/components/ui/badge.test.tsx` covering rows 20–22: correct colour, custom label, no runtime error for valid variants
- [x] 7.2 Write `src/portal/src/components/ui/stat-card.test.tsx` covering rows 23–26: delta-up colour, delta-warn colour, absent optional props, shadow-card class
- [x] 7.3 Write `src/portal/src/components/ui/slide-over.test.tsx` covering rows 27–30: hidden when closed, visible when open, backdrop click, Escape key
- [x] 7.4 Write `src/portal/src/components/ui/mini-bar.test.tsx` covering rows 31–33: 30% width, warning colour at 90%, clamp to 100%
- [x] 7.5 Write `src/portal/src/components/ui/segment-control.test.tsx` covering rows 34–36: active style, onChange call, arrow-key focus
- [x] 7.6 Write `src/portal/src/components/ui/spinner.test.tsx` covering rows 37–38: md default, sm variant
- [x] 7.7 Write `src/portal/src/components/ui/placeholder-screen.test.tsx` covering rows 39–40: title present, no error

## 8. Build and Type Verification

- [x] 8.1 Run `npm run typecheck --workspace=src/portal` and confirm it exits 0 — path aliases, strict mode, and barrel imports all resolve *(verification rows 3, 43, 57)*
- [x] 8.2 Run `npm run lint --workspace=src/portal` and confirm it exits 0 *(verification row 5)*
- [x] 8.3 Run `npx prettier --check . --workspace=src/portal` and confirm it exits 0 *(verification row 6)*
- [x] 8.4 Run `npm run build --workspace=src/portal` and confirm it exits 0; inspect `.next/static/css/` for at least one compiled Tailwind rule *(verification rows 1, 7)*
- [x] 8.5 Confirm `src/portal/.env.local.example` exists and documents all six `NEXT_PUBLIC_*` variables *(verification rows 8–9)*

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (`npm test --workspace=src/portal` exits 0 with all 58 scenarios covered).
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register (token naming cross-ref, `darkMode: "class"` check, localStorage key consistency, timer cleanup, SlideOver focus trap, authFetch signature, barrel exports).
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (ADR-004 artifact gates satisfied, ADR-005 file scope check via `git diff --name-only`).
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate portal-foundation --type change --strict` and confirm it exits clean before archive.
