## Context

`Sidebar.tsx` and `Topbar.tsx` render the persistent app chrome around every authenticated portal screen. `AppShell.tsx` owns a `demoRole` state that lets a logged-in user locally override their effective role via chips in the Topbar, without a real backend role change — this exists purely for demoing different role views (`NEXT_PUBLIC_DEMO_MODE === "true"`). The Sidebar also renders a wordmark (currently `nerplatform`, no spacing/casing) and a "tenant pill" showing tenant initial/name/slug with no interaction. The Topbar renders a static search box with no wiring. All three of the removed elements were verified in code to have no `onClick`/handler and `cursor: default` — they are visual-only.

## Goals / Non-Goals

**Goals:**
- Fix the wordmark text to read "NER Platform".
- Remove three dead/decorative UI elements: tenant pill (Sidebar), search placeholder (Topbar), role-switcher chip cluster (Topbar).
- Remove the now-unused `demoRole` plumbing (`AppShell.tsx` state, `TopbarProps.demoRole`/`onDemoRoleChange`) so no dead state remains.

**Non-Goals:**
- No change to real role-based access control, navigation, or auth — `effectiveRole` simply becomes `user.role` directly.
- No visual redesign of the remaining Sidebar/Topbar layout beyond removing the specified elements (spacing/flex adjusts naturally as elements are removed).
- No change to dark mode toggle, avatar, logout menu, or nav items.

## Currently-In-Force ADRs

None — all existing ADRs (001–008) cover backend/data/model/training/agent concerns; none constrain presentation-layer app-shell markup.

## Decisions

### Decision 1: Remove `demoRole` state rather than relocating it

**Choice:** Delete `AppShell.tsx`'s `demoRole` state and `Topbar`'s role-switcher chips entirely; `Sidebar` receives `effectiveRole={user.role}` directly.

**Rationale:** The chips were the only UI entry point for `demoRole`. With the chips gone, the state has no producer and is dead code. Keeping it around unused would violate the "no half-finished implementations" principle.

**Alternatives considered:**
- Keep `demoRole` behind a hidden dev-only route/query-param — ruled out, not requested and adds surface area for a feature nobody asked to preserve.

### Decision 2: Wordmark text fix only, no logo/asset changes

**Choice:** Change the literal string `nerplatform` to `NER Platform` in `Sidebar.tsx`; no font/icon changes.

**Rationale:** Matches canonical branding already used in `README.md` and seed data (`docs/NER Platform.html`, `src/gateway/seed.py`). Minimal, scoped fix — user asked only for capitalization/spacing.

**Alternatives considered:**
- Introduce a shared branding constant — ruled out as premature abstraction for a single literal used once.

## Risks / Trade-offs

- [Removing demo role-switcher removes the only way testers/demos flip role view without separate logins] → Acceptable per explicit user request; testers can log in as different role accounts instead.
- [Removing tenant pill drops the only visible tenant-context indicator in the sidebar] → Confirmed decorative-only (static demo data, no real multi-tenant switching behavior existed here); no functional loss.
- [Existing tests/snapshots assert on removed markup or old wordmark text] → Update `sidebar.test.tsx` and any Topbar/AppShell tests referencing `demoRole`, search box, or tenant pill as part of implementation.

## Migration Plan

1. Update `Sidebar.tsx`: wordmark text, remove tenant pill block.
2. Update `Topbar.tsx`: remove search placeholder block, remove role-switcher block and demo-role props from `TopbarProps`.
3. Update `AppShell.tsx`: drop `demoRole` state, pass `user.role` directly to `Sidebar`, drop props passed to `Topbar`.
4. Update `sidebar.test.tsx` (and any Topbar tests) to match trimmed markup/props.
5. No feature flag or staged rollout needed — this is a same-deploy UI simplification with no data migration. Rollback is a plain revert of the commit if needed.

## Open Questions

None.
