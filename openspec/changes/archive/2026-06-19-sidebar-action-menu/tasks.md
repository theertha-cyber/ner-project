## 1. Nav Config — Remove Settings Entries

- [x] 1.1 Remove the Settings nav entry (`{ id: "settings", icon: "⚙", label: "Platform Settings", href: "/settings", roles: ["system_admin"] }`) from the `system_admin` array in `src/portal/src/lib/nav-config.ts`
- [x] 1.2 Remove the Settings nav entry from the `tenant_admin` array
- [x] 1.3 Remove the Settings nav entry from the `annotator` array
- [x] 1.4 Remove the Settings nav entry from the `business_user` array
- [x] 1.5 Verify `SCREEN_TITLES` still has the `settings` entry (it's still a valid route)

## 2. Sidebar — Floating Action Menu Implementation

- [x] 2.1 Add `useState`, `useEffect`, `useRef` imports from React to `src/portal/src/components/app-shell/Sidebar.tsx`
- [x] 2.2 Add `menuOpen` state boolean and `menuRef` / `triggerRef` refs near the top of the `Sidebar` component
- [x] 2.3 Add `useEffect` for `mousedown` click-outside detection — close menu when click is outside both `menuRef` and `triggerRef`
- [x] 2.4 Add `useEffect` for `keydown` Escape key handler — close menu on Escape
- [x] 2.5 Add `position: "relative"` to the user strip container style
- [x] 2.6 Replace the `⎋` logout button (lines 268-289) with a `⋮` (U+22EE) trigger button that toggles `setMenuOpen(prev => !prev)`
- [x] 2.7 Add the floating menu JSX positioned upward (`position: "absolute", bottom: "100%"`) with two buttons: Settings (`router.push("/settings")`) and Logout (`await logout(); router.push("/login")`)
- [x] 2.8 Apply fade-in/out styling: `opacity` toggle with `transition: opacity 0.15s ease`, `pointerEvents: "auto"/"none"` gating
- [x] 2.9 Add `aria-haspopup="true"` and `aria-expanded` to the trigger button for accessibility

## 3. Verification — Write Acceptance Tests

- [x] 3.1 Write a unit test for `navFor("system_admin")` returning 5 items (no Settings) — covers verification.md row 10
- [x] 3.2 Write a unit test for `navFor("tenant_admin")` returning 7 items (no Settings) — covers verification.md row 11
- [x] 3.3 Write a unit test for `navFor("annotator")` returning 3 items (no Settings) — covers verification.md row 12
- [x] 3.4 Write a unit test for `navFor("business_user")` returning 4 items (no Settings) — covers verification.md row 13
- [x] 3.5 Write a component test for sidebar rendering with correct nav item count per role — covers verification.md rows 1-4

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass (8/8 new tests pass; 2 pre-existing login failures unrelated)
- [x] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [x] 4.6 Run `openspec validate sidebar-action-menu --type change --strict` and confirm it exits clean before archive
