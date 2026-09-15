# Accessibility -- tenant-self-service-data-sources-20260909-2

Scope: deployed portal http://localhost:3000 against **WCAG 2.1 AA** (this skill's documented default; the requirement document leaves accessibility open and the design names no level). `UI Design: generate` applied, so baseline `uiux.nonOverridable` entries are blocking. Method: axe-core 4.11 via Playwright Chromium — signed-out scan of `/login`, signed-in scan (seeded tenant admin) of `/settings/data-sources` — plus static `ui-ux-governor` verify of the contract. Evidence: `../evidences/tenant-self-service-data-sources-20260909-2/accessibility/axe.json`, `login.png`, `data-sources.png`, `axe-scan.mjs`.

## Results

| Page/Flow | Rule | Impact | Element | Status | Evidence |
|---|---|---|---|---|---|
| Data Sources (SCR-1, tenant admin) | color-contrast (WCAG 1.4.3; baseline `color-contrast-minimum`) | serious | sidebar user-badge caption `button[aria-haspopup] > div > div` — `color: var(--ink-3)` (`#94a3b8`, ~2.9:1 on white) at 10 px, `src/portal/src/components/app-shell/Sidebar.tsx` via `tokens.css:40` | **fail — blocking (A11Y-01)** | axe.json + data-sources.png |
| Data Sources (SCR-1) | document-title | serious | `<html lang="en">` with empty/missing `<title>` (`src/portal/src/app/layout.tsx` exports no metadata) | **fail — blocking (A11Y-02)** | axe.json |
| Data Sources (SCR-1) | rest of WCAG 2.1 AA | — | 22 passes, no other violations | pass | axe.json |
| Login (signed out) | document-title / landmark-one-main / region | serious / moderate / moderate | app shell lacks `<title>`, `<main>`, region names | fail (same root causes as above; login is not a new screen) | axe.json + login.png |
| Static verify (ui-ux-governor) | labels, focus, keyboard, safe-shape, states, form validation, P0 anti-slop, token import | — | pass with notes: 5× `#fff` on-primary literals worth promoting to a token; contract-history shows empty state while loading; 350 ms entrance exceeds 300 ms budget; **no `prefers-reduced-motion` guard anywhere** (Approve, no Block) | pass with advisories | verify verdict in summary |

## Notes

- Both blocking findings sit in **pre-existing shell code** (`Sidebar.tsx`, `layout.tsx`, `tokens.css`) untouched by CAP-2..CAP-6 — but they render on the new critical path, so they block under the baseline all the same. Each is a one-line-class fix (raise `--ink-3` usage to a ≥4.5:1 token for small text; export `metadata.title` from the root layout).
- 11 full-tree P0 `ai-default-indigo` hits are pre-existing annotation/extraction/import screens, out of scope.
- Screenshots show the feature itself rendering correctly: empty state, labelled filters, `New connection` action, `Data Sources` sidebar entry.

## Decision

**Fail on A11Y-01 and A11Y-02** (serious, on the new primary screen, live on dev at http://localhost:3000/settings/data-sources). Everything else in this file passes.
