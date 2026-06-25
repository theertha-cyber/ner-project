## 1. Animation Foundation

- [x] 1.1 Add `@keyframes ner-fade-up { from { transform: translateY(8px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }` to `src/portal/src/app/globals.css` alongside existing `meshDrift`, `popIn`, and `ner-menu-pop` keyframes
- [x] 1.2 Register `animate-fade-up` in `tailwind.config.ts` under `theme.extend.animation` as `'fade-up': 'ner-fade-up 0.35s ease both'`
- [x] 1.3 Verify: confirm `fade-up` entry exists in the animation config (verification row 20)

## 2. Sidebar — Background and Logo

- [x] 2.1 Remove `backdropFilter: "blur(16px)"` and the `rgba` opacity from `Sidebar.tsx` background; replace with `background: "var(--surface-2)"` (solid)
- [x] 2.2 Resize the logo `n` icon from 34×34px to 30×30px; update `font-weight` from 700 to 800 and `font-size` from 18px to 17px
- [x] 2.3 Update wordmark `<span>` from `font-size: 14px / font-weight: 600` to `font-size: 16px / font-weight: 700 / letter-spacing: -0.02em`
- [ ] 2.4 Verify: visual inspection — sidebar background is solid (no blur through it), logo is visibly smaller than before (verification row 1 structural check)

## 3. Sidebar — Tenant Pill

- [x] 3.1 Add `background: "var(--surface-3)"` to the tenant pill container div in `Sidebar.tsx`
- [x] 3.2 Update tenant pill container `border-radius` from 8px to 12px and `padding` from `8px 10px` to `9px 11px`
- [x] 3.3 Update tenant avatar background from `"var(--color-brand-primary, #c2410c)"` to `"var(--primary-soft)"` and text colour to `"var(--primary-2)"`
- [x] 3.4 Update tenant avatar size from 28×28px to 26×26px and `border-radius` from 6px to 7px
- [x] 3.5 Update tenant name font size from 12px to 12.5px and weight from 500 to 600
- [ ] 3.6 Verify: screenshot of tenant pill showing surface-3 background fill and muted-orange avatar (verification row 4)

## 4. Sidebar — User Strip Trigger

- [x] 4.1 Add `border-radius: 11px` to the user strip trigger `<button>` in `Sidebar.tsx`
- [x] 4.2 Update trigger button `padding` from `"12px"` to `"7px 8px"`
- [x] 4.3 Update trigger button outer `<div>` (border-top wrapper) to add `padding: "12px"` so the button doesn't touch the edges — align with mockup's `padding: 12px` on the outer container
- [x] 4.4 Update avatar inside the user strip from `border-radius: 6` to `border-radius: 9px` (to match mockup's `border-radius:9px` on the 32×32 avatar)

## 5. Sidebar — Chevron Framed Box

- [x] 5.1 Replace the plain `▾` `<span>` at the end of the user strip trigger with a framed container: `<span style={{ width: 24, height: 24, borderRadius: 7, background: "var(--surface-2)", border: "1px solid var(--line)", display: "grid", placeItems: "center", color: "var(--ink-2)", fontSize: 9, flexShrink: 0, transition: "transform 0.18s ease", transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>`
- [x] 5.2 Remove the separate `display: "inline-block"` wrapper that was on the old plain `▾`
- [ ] 5.3 Verify: visual inspection — the chevron is enclosed in a visible bordered box (verification row 5)

## 6. Sidebar — Logout Danger Colour

- [x] 6.1 In the floating menu panel inside `Sidebar.tsx`, update the Logout `<button>` text colour from `"var(--color-text-primary, #0f172a)"` to `"var(--bad)"`
- [x] 6.2 Update the Logout button `onMouseEnter` background from `"rgba(0,0,0,0.05)"` to `"var(--bad-soft)"`
- [x] 6.3 Update the Logout button `onMouseLeave` background back to `"transparent"`
- [ ] 6.4 Verify: open the user menu — Logout label is visibly red; hover shows red-tinted background (verification row 9)

## 7. Topbar — Background and Title Layout

- [x] 7.1 Remove `backdropFilter: "blur(16px)"` and the `rgba` opacity from `Topbar.tsx` background; replace with `background: "var(--surface-2)"` (solid)
- [x] 7.2 Change the screen title + path wrapper from `flexDirection: "column"` to a row with `alignItems: "baseline"` and `gap: 9`
- [x] 7.3 Update title font-size from 15px to 16px
- [ ] 7.4 Verify: screenshot of topbar showing title and path in the same horizontal row (verification row 13)

## 8. Topbar — Role-Switcher Pill Container

- [x] 8.1 In `Topbar.tsx`, wrap the existing demo-mode block (`AS` label + four role chip buttons) in a new outer `<div>` with `display: "flex", alignItems: "center", gap: 3, background: "var(--surface-3)", border: "1px solid var(--line)", borderRadius: 10, padding: 3`
- [x] 8.2 Remove any pre-existing gap or margin from the existing chips flex container that would conflict with the new wrapper's `padding: 3`
- [x] 8.3 Update the `AS` label to use `padding: "0 6px"` inside the pill wrapper
- [ ] 8.4 Verify: in demo mode, the AS label and all four chips appear inside a visibly bordered pill container (verification row 15)

## 9. Topbar — Border Radii

- [x] 9.1 Update search bar `<div>` `border-radius` from 7px to 10px in `Topbar.tsx`
- [x] 9.2 Update dark mode toggle `<button>` `border-radius` from 7px to 10px in `Topbar.tsx`
- [x] 9.3 Update user avatar `<div>` `border-radius` from 7px to 10px in `Topbar.tsx`
- [ ] 9.4 Verify: DevTools inspection confirms all three topbar elements have 10px border-radius (verification rows 16, 17)

## 10. Page Enter Animations

- [x] 10.1 Add `className="animate-fade-up"` to the root `<div>` wrapper in `src/portal/src/app/(auth)/dashboard/page.tsx`
- [x] 10.2 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/documents/page.tsx`
- [x] 10.3 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/annotation/page.tsx`
- [x] 10.4 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/analytics/page.tsx`
- [x] 10.5 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/audit/page.tsx`
- [x] 10.6 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/chat/page.tsx`
- [x] 10.7 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/entity-types/page.tsx`
- [x] 10.8 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/extractions/page.tsx`
- [x] 10.9 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/models/page.tsx`
- [x] 10.10 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/settings/page.tsx`
- [x] 10.11 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/training-jobs/page.tsx`
- [x] 10.12 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/users/page.tsx`
- [x] 10.13 Add `className="animate-fade-up"` to the root wrapper in `src/portal/src/app/(auth)/admin/page.tsx` and each admin sub-page
- [ ] 10.14 Verify: navigate between at least two screens — confirm the fadeUp animation fires on each arrival (verification row 22)

## 11. Widget Keys Screen

- [x] 11.1 Add `"widget-keys"` to `SCREEN_TITLES` in `src/portal/src/lib/nav-config.ts`: `"widget-keys": ["Widget Keys", "/widget-keys"]`
- [x] 11.2 Add widget-keys nav item to `navFor("tenant_admin")` in `nav-config.ts`: `{ id: "widget-keys", icon: "⊟", label: "Widget Keys", href: "/widget-keys", roles: ["tenant_admin"] }`
- [x] 11.3 Create directory `src/portal/src/app/(auth)/widget-keys/` and file `page.tsx`
- [x] 11.4 Implement the page header: JetBrains Mono breadcrumb (`/api/v1/tenants/{slug}/widget-keys · port 8006`) + Hanken Grotesk title "Widget Keys"
- [x] 11.5 Implement the API fetch: call `GET /api/v1/tenants/{slug}/widget-keys` using the authenticated gateway URL (same base URL pattern as other API calls in the portal); store result in local state
- [x] 11.6 Implement the keys table: render a row per key showing name, masked prefix (`key.slice(0,8) + '…'`), creation date, status badge (`active`/`revoked`), and a copy button that calls `navigator.clipboard.writeText(key.value)`
- [x] 11.7 Implement the empty state: render when the API returns an empty array OR a non-2xx response — display a message and a non-functional "Create Key" placeholder button
- [x] 11.8 Apply `animate-fade-up` class to the page's root `<div>`
- [ ] 11.9 Verify: screenshot of tenant_admin sidebar showing Widget Keys nav item (verification row 23)
- [ ] 11.10 Verify: screenshot of Widget Keys page showing breadcrumb, title, and at least the empty state (verification rows 25, 26, 28)
- [ ] 11.11 Verify: confirm Widget Keys nav item is absent for annotator and business_user roles (verification row 24)

## 12. Verification & Evidence

- [ ] 12.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 12.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 12.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register (7 items: glass removal, avatar colour, chevron box, role-switcher container, title baseline, fadeUp on page not layout, logout colour)
- [ ] 12.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (ADR-004 artifacts present; ADR-005 only portal files touched)
- [ ] 12.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 12.6 Run `openspec validate app-shell-exact-mockup --type change --strict` and confirm it exits clean before archive
