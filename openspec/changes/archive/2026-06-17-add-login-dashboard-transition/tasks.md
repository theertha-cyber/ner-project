## 1. CSS Keyframes

- [x] 1.1 Add `@keyframes orbBurst` to `src/portal/src/app/globals.css` — expands `clip-path: circle(0% at 75% 50%)` to `clip-path: circle(150% at 75% 50%)` over 550 ms with `ease-in` timing, using a radial gradient background of `#c2410c` → `#ea580c` → `#f59e0b`
- [x] 1.2 Add `@keyframes dashFadeIn` to `src/portal/src/app/globals.css` — transitions `opacity: 0` to `opacity: 1` over 400 ms

## 2. Login Page — Burst Overlay

- [x] 2.1 Add `isTransitioning` boolean state (default `false`) to `LoginPage` in `src/portal/src/app/login/page.tsx`
- [x] 2.2 In `handleSubmit`, move `router.replace("/dashboard")` out of the `try` block; instead call `setIsTransitioning(true)` after `await login()` succeeds (the navigation will fire from the overlay's `onAnimationEnd`)
- [x] 2.3 Add a burst overlay `<div>` that renders conditionally when `isTransitioning` is `true` — fixed position, `inset: 0`, `z-index: 50`, background `radial-gradient(circle at 30% 40%, #f59e0b, #ea580c 40%, #c2410c 70%)`, `animation: orbBurst 0.55s ease-in both`, `onAnimationEnd={() => router.replace("/dashboard")}`
- [x] 2.4 Confirm the burst overlay renders above the form card and `AnimatedBackground` but does not unmount or hide them

## 3. Auth Layout — Dashboard Fade-in

- [x] 3.1 In `src/portal/src/app/(auth)/layout.tsx`, apply `animation: dashFadeIn 0.4s ease both` to the outermost wrapper `<div>` (or add one if the layout currently returns children directly)

## 4. Smoke Testing

- [ ] 4.1 Start the Next.js dev server (`npm run dev` in `src/portal/`) and navigate to the login page
- [ ] 4.2 Log in with valid credentials — visually confirm the orb-burst overlay fires from the right-centre and covers the screen before navigating
- [ ] 4.3 Attempt login with invalid credentials — confirm no burst overlay appears and the error message renders as before
- [ ] 4.4 After burst + navigation, confirm the dashboard content fades in smoothly over ~400 ms
- [ ] 4.5 Inspect DevTools during burst — confirm form DOM nodes and animated background orbs are still present beneath the overlay

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 5.6 Run `openspec validate add-login-dashboard-transition --type change --strict` and confirm it exits clean before archive.
