# Verification Plan

**Change:** portal-foundation
**Generated:** 2026-06-15
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | project-scaffold | Next.js workspace structure | Workspace discoverable from repo root | Given a root `package.json` with a `workspaces` field listing `src/portal`, when `npm install` runs at the repo root, then `src/portal/node_modules` is populated and portal scripts are runnable | `npm install && npm run build --workspace=src/portal` exits 0 | - [ ] |
| 2 | project-scaffold | Next.js workspace structure | Next.js dev server starts | Given `.env.local` is populated, when `npm run dev` runs inside `src/portal/`, then the server starts on port 3000 with no compilation errors | Manual dev-server start; verify no error output | - [ ] |
| 3 | project-scaffold | TypeScript strict configuration | Path alias resolves at compile time | Given a component imports from `@/components/ui`, when `tsc --noEmit` runs, then no TS2307 error is produced | `npm run typecheck` exits 0 | - [ ] |
| 4 | project-scaffold | TypeScript strict configuration | Strict null checks enforced | Given `tsconfig.json` has `"strict": true`, when a file assigns `null` to a `string` variable, then `tsc` reports TS2322 | Introduce deliberate type error in scratch file; confirm error | - [ ] |
| 5 | project-scaffold | ESLint and Prettier configuration | Lint passes on the scaffold | Given scaffold files are written, when `npm run lint` runs, then ESLint exits 0 with no errors | `npm run lint` exits 0 | - [ ] |
| 6 | project-scaffold | ESLint and Prettier configuration | Format check consistent with config | Given files are formatted with Prettier, when `npx prettier --check .` runs, then it exits 0 | `npx prettier --check .` exits 0 | - [ ] |
| 7 | project-scaffold | Tailwind CSS integration | Tailwind classes compile without errors | Given a component uses a standard Tailwind class, when the Next.js build runs, then the compiled CSS contains the rule and PostCSS reports no errors | `npm run build` exits 0; inspect `.next/static/css/` for the rule | - [ ] |
| 8 | project-scaffold | Environment variable interface | Missing env variable does not crash at module load | Given `.env.local` omits `NEXT_PUBLIC_DOCUMENT_URL`, when `src/portal/src/lib/api.ts` is imported in a test, then `DOCUMENT_URL` equals `""` and no exception is thrown | Vitest test: `expect(DOCUMENT_URL).toBe("")` passes | - [ ] |
| 9 | project-scaffold | Environment variable interface | Defined env variable is surfaced correctly | Given `.env.local` sets `NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000`, when `GATEWAY_URL` is read from `api.ts`, then its value equals `"http://localhost:8000"` | Vitest test using `process.env` stub passes | - [ ] |
| 10 | project-scaffold | Root layout with provider wiring | Font variables present on html element | Given the app has rendered, when `getComputedStyle(document.documentElement)` is inspected, then `--font-display`, `--font-body`, and `--font-mono` are non-empty | Playwright/manual browser check post-hydration | - [ ] |
| 11 | project-scaffold | Root layout with provider wiring | ToastProvider is an ancestor of all pages | Given any page calls `useToast()`, when it renders, then no "must be used within ToastProvider" error is thrown | `npm test` passes; no context errors in dev server console | - [ ] |
| 12 | project-scaffold | Vitest and Testing Library setup | Test suite runs from repo root | Given test files exist, when `npm test --workspace=src/portal` runs, then Vitest executes and exits 0 when all pass | `npm test --workspace=src/portal` exits 0 | - [ ] |
| 13 | design-tokens | CSS custom-property token declarations | Token file is the single source of colour truth | Given `globals.css` declares all colour tokens, when the portal source is searched for hardcoded hex values matching any token colour, then no match is found outside `globals.css` | `grep -r "#[0-9a-fA-F]\{6\}" src/portal/src/` returns only `globals.css` entries | - [ ] |
| 14 | design-tokens | CSS custom-property token declarations | Dark overrides activate via class | Given `document.documentElement` has the `dark` class, when an element styled with `bg-surface` renders, then its computed background matches `--color-surface`'s dark value | Vitest JSDOM test: add `dark` class, assert computed style | - [ ] |
| 15 | design-tokens | Colour palette tokens | Status token maps to Badge variant | Given `--color-status-running` is declared in `:root`, when `<Badge variant="running" />` renders, then the badge's colour resolves to `--color-status-running` | Vitest snapshot or `toHaveStyle` assertion passes | - [ ] |
| 16 | design-tokens | Colour palette tokens | All status tokens have dark overrides | Given the `:root.dark` block in `globals.css`, when each status token name from `:root` is checked against `:root.dark`, then every status token has a corresponding override entry | Code review of `globals.css`; all 10 status tokens present in both blocks | - [ ] |
| 17 | design-tokens | Typography tokens | Font variable is present after hydration | Given the portal has hydrated, when `getPropertyValue("--font-display")` is called, then the value is a non-empty string | Browser DevTools check or Playwright assertion | - [ ] |
| 18 | design-tokens | Radius and shadow tokens | Card shadow token used on dashboard stat cards | Given `--shadow-card` is declared, when `<StatCard />` renders, then its `box-shadow` matches `--shadow-card` | Vitest `toHaveStyle` or `toHaveClass` assertion | - [ ] |
| 19 | design-tokens | Tailwind config token references | Tailwind class resolves to token | Given `tailwind.config.ts` maps `colors.brand-primary` to `var(--color-brand-primary)`, when a component uses `text-brand-primary`, then the generated CSS sets `color: var(--color-brand-primary)` | Inspect compiled CSS or run `npx tailwindcss` CLI on a test input | - [ ] |
| 20 | ui-primitives | Badge component | Badge renders correct colour for known variant | Given design tokens are declared, when `<Badge variant="running" />` renders, then the badge resolves to `--color-status-running` and displays "running" | Vitest test: `getByText("running")` present; style assertion | - [ ] |
| 21 | ui-primitives | Badge component | Badge uses custom label when provided | Given `<Badge variant="pending_approval" label="Needs Review" />`, when rendered, then the displayed text is "Needs Review" | Vitest: `getByText("Needs Review")` found; `queryByText("pending approval")` not found | - [ ] |
| 22 | ui-primitives | Badge component | Unknown variant falls back gracefully | Given a valid `BadgeVariant` string is passed, when the component renders, then no runtime error occurs | TypeScript compilation enforces valid values; runtime test with each variant | - [ ] |
| 23 | ui-primitives | StatCard component | Delta up indicator uses success colour | Given `<StatCard delta="+0.03" deltaDir="up" />`, when rendered, then delta text resolves to `--color-delta-up` | Vitest: `toHaveStyle({ color: "var(--color-delta-up)" })` passes | - [ ] |
| 24 | ui-primitives | StatCard component | Delta warn indicator uses warning colour | Given `<StatCard delta="+5" deltaDir="warn" />`, when rendered, then delta text resolves to `--color-delta-warn` | Vitest: `toHaveStyle({ color: "var(--color-delta-warn)" })` passes | - [ ] |
| 25 | ui-primitives | StatCard component | Optional props render nothing when absent | Given `<StatCard label="Tenants" value="7" />`, when rendered, then no delta indicator or subtitle is present | Vitest: `queryByTestId("delta")` returns null | - [ ] |
| 26 | ui-primitives | StatCard component | Card uses shadow-card token | Given `<StatCard label="Models" value="3" />` renders, when the card element's computed style is inspected, then `box-shadow` resolves to `--shadow-card` | Vitest or browser DevTools assertion | - [ ] |
| 27 | ui-primitives | SlideOver component | Panel is hidden when closed | Given `<SlideOver open={false} />`, when rendered, then the panel is not visible | Vitest: panel element has `display: none` or is fully translated off-screen | - [ ] |
| 28 | ui-primitives | SlideOver component | Panel is visible when open | Given `<SlideOver open={true} />`, when rendered, then the panel and backdrop are visible | Vitest: `getByRole("dialog")` is visible; backdrop present in DOM | - [ ] |
| 29 | ui-primitives | SlideOver component | onClose fires on backdrop click | Given `<SlideOver open={true} onClose={mockFn} />`, when a user clicks the backdrop, then `mockFn` is called once | Vitest `userEvent.click(backdrop)` → `expect(mockFn).toHaveBeenCalledOnce()` | - [ ] |
| 30 | ui-primitives | SlideOver component | onClose fires on Escape key | Given `<SlideOver open={true} onClose={mockFn} />`, when Escape is pressed, then `mockFn` is called once | Vitest `userEvent.keyboard("{Escape}")` → `expect(mockFn).toHaveBeenCalledOnce()` | - [ ] |
| 31 | ui-primitives | MiniBar component | Fill width proportional to used/max | Given `<MiniBar used={3} max={10} />`, when rendered, then fill element width is 30% | Vitest: fill element has `style.width === "30%"` | - [ ] |
| 32 | ui-primitives | MiniBar component | Fill uses warning colour at 90%+ usage | Given `<MiniBar used={9} max={10} />`, when rendered, then fill resolves to `--color-warning` | Vitest: fill element has warning class or `toHaveStyle` assertion | - [ ] |
| 33 | ui-primitives | MiniBar component | Fill is clamped to 100% when used exceeds max | Given `<MiniBar used={15} max={10} />`, when rendered, then fill width is 100% | Vitest: fill element `style.width === "100%"` | - [ ] |
| 34 | ui-primitives | SegmentControl component | Selected option is visually distinguished | Given SegmentControl with value `"a"`, when rendered, then "A" button has active style not applied to "B" | Vitest: active button has active class; inactive button does not | - [ ] |
| 35 | ui-primitives | SegmentControl component | Clicking an option calls onChange | Given SegmentControl with `onChange={mockFn}`, when "B" is clicked, then `mockFn` is called with `"b"` | Vitest `userEvent.click(bButton)` → `expect(mockFn).toHaveBeenCalledWith("b")` | - [ ] |
| 36 | ui-primitives | SegmentControl component | Component is keyboard navigable | Given focus is on the "A" button, when the right arrow key is pressed, then focus moves to "B" | Vitest `userEvent.keyboard("{ArrowRight}")` → `expect(bButton).toHaveFocus()` | - [ ] |
| 37 | ui-primitives | Spinner component | Spinner renders with default size | Given `<Spinner />`, when rendered, then the spinner element is present with the md size class | Vitest: spinner element exists; has `size-md` or equivalent class | - [ ] |
| 38 | ui-primitives | Spinner component | Spinner renders sm variant | Given `<Spinner size="sm" />`, when rendered, then the spinner has the sm size class (smaller than md) | Vitest: spinner element has `size-sm` class; not the md class | - [ ] |
| 39 | ui-primitives | PlaceholderScreen component | Title is displayed | Given `<PlaceholderScreen title="Model Registry" />`, when rendered, then "Model Registry" is in the DOM | Vitest: `getByText("Model Registry")` found | - [ ] |
| 40 | ui-primitives | PlaceholderScreen component | Component renders without additional props | Given `<PlaceholderScreen title="Documents" />`, when rendered, then no runtime error occurs | Vitest: component renders without throwing | - [ ] |
| 41 | ui-primitives | authFetch stub | authFetch pass-through calls native fetch | Given authFetch is imported and `fetch` is mocked, when `authFetch("http://localhost:8000/health")` is called, then the mock `fetch` is called with that URL and the response returned | Vitest with `vi.spyOn(global, "fetch")` asserts correct call | - [ ] |
| 42 | ui-primitives | authFetch stub | Import path is stable across SP-01 and SP-02 | Given a component imports `authFetch` from `@/lib/auth-fetch`, when SP-02 replaces the body, then the import path and signature remain unchanged | Code review: SP-02 implementation file path equals `src/portal/src/lib/auth-fetch.ts` | - [ ] |
| 43 | ui-primitives | Primitive barrel export | All primitives importable from barrel | Given `import { Badge, StatCard, SlideOver, MiniBar, SegmentControl, Spinner, PlaceholderScreen } from "@/components/ui"`, when `tsc --noEmit` runs, then all named exports resolve without error | `npm run typecheck` exits 0 with barrel import in a test file | - [ ] |
| 44 | ui-primitives | Unit test coverage for all primitives | Test files present for all primitives | Given the `src/portal/src/components/ui/` directory, when listed, then all seven `*.test.tsx` files exist | `ls src/portal/src/components/ui/*.test.tsx` lists 7 files | - [ ] |
| 45 | ui-primitives | Unit test coverage for all primitives | All tests pass | Given the portal is correctly configured, when `npm test --workspace=src/portal` runs, then all primitive tests pass | `npm test` exits 0 | - [ ] |
| 46 | utility-hooks | useDarkMode hook | Initialises from localStorage dark preference | Given `localStorage.setItem("portal-theme","dark")` before mount, when `useDarkMode()` initialises, then `dark === true` and `<html>` has the `dark` class | Vitest `renderHook` with JSDOM localStorage pre-set; assert `result.current.dark === true` | - [ ] |
| 47 | utility-hooks | useDarkMode hook | Initialises to light when localStorage is absent | Given `localStorage` has no `"portal-theme"` entry, when `useDarkMode()` initialises, then `dark === false` and `<html>` lacks the `dark` class | Vitest `renderHook` with empty localStorage; assert `result.current.dark === false` | - [ ] |
| 48 | utility-hooks | useDarkMode hook | toggle flips dark state and updates DOM | Given `dark === false`, when `toggle()` is called, then `dark === true` and `document.documentElement` has the `dark` class | Vitest: `act(() => result.current.toggle()); expect(result.current.dark).toBe(true)` | - [ ] |
| 49 | utility-hooks | useDarkMode hook | toggle persists preference to localStorage | Given `dark === false`, when `toggle()` is called, then `localStorage.getItem("portal-theme") === "dark"` | Vitest: `act(() => result.current.toggle()); expect(localStorage.getItem("portal-theme")).toBe("dark")` | - [ ] |
| 50 | utility-hooks | useDarkMode hook | Second toggle reverts to light | Given `dark === true`, when `toggle()` is called again, then `dark === false`, `dark` class is removed, and localStorage stores `"light"` | Vitest two-toggle sequence; assert final state | - [ ] |
| 51 | utility-hooks | useToast hook and ToastProvider | Toast appears on call | Given `ToastProvider` wraps the tree, when `toast("Operation succeeded", "ok")` is called, then a banner with that text is visible | Vitest: `getByText("Operation succeeded")` found after toast call | - [ ] |
| 52 | utility-hooks | useToast hook and ToastProvider | ok kind uses success colour | Given `toast("Saved", "ok")` is called, when the banner renders, then it resolves to `--color-success` | Vitest: banner element has success class or style | - [ ] |
| 53 | utility-hooks | useToast hook and ToastProvider | bad kind uses error colour | Given `toast("Failed", "bad")` is called, when the banner renders, then it resolves to `--color-error` | Vitest: banner element has error class or style | - [ ] |
| 54 | utility-hooks | useToast hook and ToastProvider | Banner auto-dismisses after 4 seconds | Given `toast("Processing…")` is called with fake timers, when 4000 ms elapse, then the banner is removed | Vitest: `vi.advanceTimersByTime(4000)` → `queryByText("Processing…")` returns null | - [ ] |
| 55 | utility-hooks | useToast hook and ToastProvider | Fourth toast replaces oldest when 3 visible | Given 3 banners are visible, when a 4th `toast()` is called, then the oldest is removed and the count stays at 3 | Vitest: render 4 toasts; assert only 3 banner elements | - [ ] |
| 56 | utility-hooks | useToast hook and ToastProvider | Calling useToast outside ToastProvider throws | Given a component calls `useToast()` without `ToastProvider` as ancestor, when it renders, then an error "useToast must be used within ToastProvider" is thrown | Vitest: `expect(() => render(<ComponentWithToast />)).toThrow("useToast must be used within ToastProvider")` | - [ ] |
| 57 | utility-hooks | Hook barrel export | Hooks importable from barrel | Given `import { useDarkMode, useToast, ToastProvider } from "@/hooks"`, when `tsc --noEmit` runs, then all named exports resolve without error | `npm run typecheck` exits 0 with barrel import in a test file | - [ ] |
| 58 | utility-hooks | Unit test coverage for hooks | Hook tests exist and pass | Given the portal is configured per project-scaffold spec, when `npm test --workspace=src/portal` runs, then `use-dark-mode.test.ts` and `use-toast.test.tsx` execute with no failures | `npm test` exits 0; test report shows both files | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | CSS variable token naming | AI generates different token names in `globals.css` vs. what is referenced in Tailwind config or component classes — e.g. `--color-primary` in CSS but `var(--color-brand-primary)` in Tailwind config | Cross-reference every `var(--...)` used in `tailwind.config.ts` and component files against the declarations in `globals.css`; any mismatch means the token is undefined at runtime |
| 2 | Dark mode strategy | AI implements `darkMode: "media"` in Tailwind config instead of `darkMode: "class"`, causing the toggle to have no effect (OS preference overrides it) | Open `tailwind.config.ts`; confirm `darkMode: "class"` is present; then manually toggle dark mode in the browser and confirm colours change |
| 3 | localStorage key consistency | AI uses different keys in the write vs. read path of `useDarkMode` (e.g. writes `"theme"` but reads `"portal-theme"`) — toggle appears to work once but loses state on refresh | Read `use-dark-mode.ts` end to end; confirm the same string literal is used in every `localStorage.getItem`, `localStorage.setItem`, and `localStorage.removeItem` call |
| 4 | Toast timer cleanup | AI sets a `setTimeout` for auto-dismiss but does not clear it in the cleanup function, causing a state update on an unmounted component | Inspect `use-toast.tsx` for a `useEffect` that returns a cleanup calling `clearTimeout`; run the timer test with React's strict mode enabled and confirm no "state update on unmounted component" warning |
| 5 | SlideOver focus trap | AI renders the panel but omits focus-trap logic — keyboard users can tab out of the slide-over into obscured background content | Manually open a SlideOver in the dev build; press Tab repeatedly; confirm focus does not escape the panel; verify an `aria-modal="true"` attribute or explicit focus-trap implementation is present |
| 6 | authFetch signature drift | AI modifies the function signature in SP-02 (e.g. adds required parameters) rather than replacing only the body — breaking all existing SP-01 consumers | Compare `authFetch` signature in `auth-fetch.ts` (SP-01 baseline) against the SP-02 replacement; the exported type must be identical |
| 7 | Missing barrel re-exports | AI creates component files but forgets to add new exports to `index.ts` barrels, causing TS2305 at import sites | Run `tsc --noEmit` with a file that imports every named export from `@/components/ui` and `@/hooks`; all 8 primitives and 3 hook exports must resolve |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004 OpenSpec Spec-Driven Development Governance | All changes require proposal → design → spec → tasks → evidence gates before archiving | This verification document must exist and be signed off; tasks must be written; evidence must be collected | Confirm all artifacts in `openspec/changes/portal-foundation/` exist and are non-empty before `/opsx:archive` is invoked |
| ADR-005 OpenCode Agent Permissions and Boundaries | Agents must not write code outside their role scope; frontend work is scoped to `src/portal/` | No files outside `src/portal/` and `openspec/changes/portal-foundation/` may be created or modified by the implementation agent | `git diff --name-only` after implementation: all changed files must be under `src/portal/` or `openspec/changes/portal-foundation/` (exception: root `package.json` workspace entry) |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Rows 1–2: `npm install && npm run build --workspace=src/portal` exits 0 (workspace discoverable, dev server compiles)
- [ ] Rows 3–4: `npm run typecheck` exits 0; deliberate null assignment confirmed to error
- [ ] Rows 5–6: `npm run lint` and `npx prettier --check .` both exit 0
- [ ] Row 7: `npm run build` exits 0; inspect compiled CSS for at least one Tailwind utility class
- [ ] Rows 8–9: Vitest test output showing `api.ts` env-var tests pass
- [ ] Rows 10–11: Browser DevTools screenshot or Playwright assertion showing font CSS variables on `<html>`; no ToastProvider context error in console
- [ ] Row 12: `npm test --workspace=src/portal` exits 0 with test count > 0
- [ ] Rows 13–14: `globals.css` code review confirming no hardcoded hex outside token declarations; JSDOM dark-class test passes
- [ ] Rows 15–16: Badge colour test passes; code review confirms all 10 status tokens in both `:root` and `:root.dark`
- [ ] Row 17: Browser DevTools `getPropertyValue("--font-display")` returns non-empty string
- [ ] Rows 18–19: StatCard shadow test passes; Tailwind token resolution confirmed in compiled CSS
- [ ] Rows 20–22: All three Badge scenario tests pass
- [ ] Rows 23–26: All four StatCard scenario tests pass
- [ ] Rows 27–30: All four SlideOver scenario tests pass
- [ ] Rows 31–33: All three MiniBar scenario tests pass
- [ ] Rows 34–36: All three SegmentControl scenario tests pass
- [ ] Rows 37–38: Both Spinner scenario tests pass
- [ ] Rows 39–40: Both PlaceholderScreen scenario tests pass
- [ ] Rows 41–42: authFetch pass-through test passes; import path verified stable
- [ ] Rows 43–45: Barrel import type-checks; 7 test files present; all primitive tests pass
- [ ] Rows 46–50: All five `useDarkMode` scenario tests pass
- [ ] Rows 51–56: All six `useToast` scenario tests pass
- [ ] Rows 57–58: Hook barrel type-checks; hook test files present and pass

### Structural Evidence

- [ ] Code review completed — implementation matches all six design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (token naming): Every `var(--...)` in `tailwind.config.ts` has a matching declaration in `globals.css`
- [ ] Risk 2 (dark mode strategy): `tailwind.config.ts` contains `darkMode: "class"`; manual browser toggle confirmed
- [ ] Risk 3 (localStorage key): Same string literal used for all `localStorage` operations in `use-dark-mode.ts`
- [ ] Risk 4 (toast timer cleanup): `clearTimeout` call present in `useEffect` cleanup; no unmounted-component warning under React strict mode
- [ ] Risk 5 (SlideOver focus trap): Manual keyboard test confirms focus does not escape open SlideOver
- [ ] Risk 6 (authFetch signature drift): SP-02 `authFetch` signature byte-for-byte identical to SP-01 baseline
- [ ] Risk 7 (barrel exports): `tsc --noEmit` with full barrel import file exits 0

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** portal-foundation
**Proposal:** `openspec/changes/portal-foundation/proposal.md`
**Spec files reviewed:**
- `openspec/changes/portal-foundation/specs/project-scaffold/spec.md`
- `openspec/changes/portal-foundation/specs/design-tokens/spec.md`
- `openspec/changes/portal-foundation/specs/ui-primitives/spec.md`
- `openspec/changes/portal-foundation/specs/utility-hooks/spec.md`

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
