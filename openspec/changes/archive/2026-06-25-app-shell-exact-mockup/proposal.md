## Why

The app shell (sidebar + topbar) was implemented against a v1 mockup and then partially updated by the `app-shell-v2` change. A pixel-level comparison against `docs/NER Platform.html` reveals approximately ten visual gaps — background treatments, border radii, layout decisions, and component styling — that cause the live app to look noticeably different from the reference design. This change closes every remaining gap so the running app matches the mockup exactly.

## What Changes

- **Sidebar background**: Remove glass/blur effect; use solid `var(--surface-2)` as in the mockup.
- **Logo block**: Resize from 34×34px → 30×30px, adjust `font-weight` 700 → 800 for the `n` glyph; update wordmark to 16px/weight-700.
- **Tenant pill**: Add `background: var(--surface-3)` container fill and `border-radius: 12px`; change avatar background from full primary (`#c2410c`) to `var(--primary-soft)` with `color: var(--primary-2)`.
- **User strip trigger button**: Add `border-radius: 11px`; reduce padding to `7px 8px`.
- **User strip chevron**: Wrap `▾` in a framed 24×24px box (`background: var(--surface-2); border: 1px solid var(--line); border-radius: 7px`) to match mockup.
- **Logout button color**: Apply `color: var(--bad)` and `hover background: var(--bad-soft)` to the Logout menu item.
- **Topbar background**: Remove glass/blur; use solid `var(--surface-2)`.
- **Topbar title + path layout**: Change from stacked (column) to side-by-side (`align-items: baseline`, horizontal row).
- **Role-switcher container**: Wrap `AS` label + role chips in a single bordered pill (`background: var(--surface-3); border: 1px solid var(--line); border-radius: 10px; padding: 3px`).
- **Topbar element border radii**: Unify search bar, dark mode toggle, and avatar to `border-radius: 10px` (from 7px).
- **Widget Keys screen**: Add a new `/widget-keys` screen (tenant_admin only) for managing embeddable widget API keys, matching the mockup's WIDGET KEYS section.
- **Page enter animation**: Add a `fadeUp` CSS animation (`translateY(8px) → 0, opacity 0→1, 0.35s ease`) applied to each screen's root wrapper.

## Capabilities

### New Capabilities

- `widget-keys-screen`: UI for tenant admins to view, create, revoke, and copy embeddable widget API keys. Corresponds to the mockup's `/widget-keys` screen backed by `/api/v1/tenants/{slug}/widget-keys`.

### Modified Capabilities

- `app-shell`: Visual design requirements change for sidebar (background, logo, tenant pill, user strip, chevron) and topbar (background, title layout, role-switcher container, border radii). All changes are in `src/portal/src/components/app-shell/`.
- `design-tokens`: `fadeUp` keyframe animation must be added to `globals.css`. No token variable changes required.

## Impact

- `src/portal/src/components/app-shell/Sidebar.tsx` — majority of sidebar changes
- `src/portal/src/components/app-shell/Topbar.tsx` — topbar layout and container changes
- `src/portal/src/app/globals.css` — `fadeUp` keyframe addition
- `src/portal/src/app/(auth)/widget-keys/page.tsx` — new screen (created)
- `src/portal/src/lib/nav-config.ts` — add widget-keys nav item for `tenant_admin`
- No backend, auth, or API changes required; widget-keys screen is read-only in this change (displays existing embeddable widget keys from the existing API endpoint).

## Open Questions

- Does the `embeddable-widget` backend already expose `GET /api/v1/tenants/{slug}/widget-keys`? If not, the widget-keys screen will need a stub/placeholder state until the endpoint is available.
- Should `fadeUp` be applied at the `<main>` level in `AppShell` (one place) or at each page's root element (per-page)? The mockup applies it per-screen; AppShell-level is simpler but re-animates on tab switch rather than initial mount.
- The `glass` effect on sidebar/topbar was likely a deliberate aesthetic enhancement over the mockup — confirm with design that reverting to solid `var(--surface-2)` is the right call before implementing.
