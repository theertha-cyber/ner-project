## Why

The app shell (Sidebar + Topbar) has a naming inconsistency and three UI elements — a search box, a role-switcher chip cluster, and a tenant pill — that don't earn their place. The wordmark reads "nerplatform" with no spacing/capitalization instead of the product's actual name, "NER Platform" (used everywhere else: README, seed data, docs). The search box is a static placeholder with no wiring behind it. The tenant pill only ever renders a single-letter tenant name/initial/slug ("I" / "i") sourced from demo data, with no click behavior — it looks like a functional control but does nothing. The role-switcher chips (SA/TA/AN/BU) do work (they flip `demoRole`), but are a demo-only affordance that has no place in the persistent product chrome.

## What Changes

- Sidebar.tsx: change wordmark text from `nerplatform` to `NER Platform`.
- Sidebar.tsx: remove the tenant pill block (tenant initial/name/slug display) — confirmed non-interactive (`cursor: default`, no `onClick`), purely decorative.
- Topbar.tsx: remove the search placeholder (`⌕ search · ⌘K`) — confirmed non-interactive, purely decorative.
- Topbar.tsx: remove the demo role-switcher chip cluster (AS label + SA/TA/AN/BU buttons). **BREAKING** for demo-mode role switching: `TopbarProps.demoRole` / `onDemoRoleChange` and the `NEXT_PUBLIC_DEMO_MODE` branch are removed, so any parent passing those props must be updated to stop passing them.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `app-shell`: sidebar/topbar requirements change — wordmark text, removal of the tenant pill, search placeholder, and demo role-switcher affordance from the persistent chrome.

## Impact

- `src/portal/src/components/app-shell/Sidebar.tsx` — wordmark text, tenant pill removal.
- `src/portal/src/components/app-shell/Topbar.tsx` — search placeholder removal, role-switcher removal, `TopbarProps` shape change.
- `src/portal/src/components/app-shell/AppShell.tsx` — owns the `demoRole` state and passes `demoRole`/`onDemoRoleChange` into `<Topbar>` and derives `effectiveRole` for `<Sidebar>`; once the chips are gone this state is dead and `effectiveRole` collapses to `user.role`.
- Existing tests/snapshots referencing "nerplatform" text, the tenant pill, the search box, or the role-switcher chips need updating.
- No backend, API, or data-model impact — this is presentation-layer only.

## Open Questions

- None — demo role switching had no other UI entry point identified in the app shell; removing it is intentional per this proposal, not an oversight.
