## Why

The login page features a visually rich animated gradient background (four orbs in orange, amber, and slate that track the cursor), but the transition to the dashboard is an abrupt hard cut. Adding a thematically connected burst transition bridges the two screens so the sign-in moment feels intentional rather than jarring.

## What Changes

- On successful login, before `router.replace("/dashboard")` fires, a full-screen radial gradient overlay expands from the form area, echoing the orb colours (`#c2410c`, `#ea580c`, `#f59e0b`), covering the viewport.
- After the burst animation completes (~550 ms), navigation proceeds to `/dashboard`.
- The dashboard layout fades in from transparent to fully visible, so the landing feels like the burst settles into content.
- No changes to login form layout, fields, demo chips, or `AnimatedBackground` behaviour.

## Capabilities

### New Capabilities

- `login-dashboard-transition`: Full-screen radial-burst overlay triggered on successful sign-in, thematically consistent with the animated gradient orb background. Includes a complementary fade-in on the dashboard entry point.

### Modified Capabilities

*(none — no existing spec requirements change)*

## Impact

- **`src/portal/src/app/login/page.tsx`** — add `isTransitioning` state; delay `router.replace` until burst animation ends; render burst overlay div.
- **`src/portal/src/app/globals.css`** — add `@keyframes orbBurst` and `@keyframes dashFadeIn` keyframes.
- **`src/portal/src/app/(auth)/layout.tsx`** — apply `dashFadeIn` animation to the auth layout wrapper so every entry into the `(auth)` segment fades in (including dashboard).
- No API, backend, or auth-flow changes.

## Open Questions

- Should the burst origin be fixed at the right-centre of the viewport (where the form card sits), or should it track the exact pointer position at the moment of button click? Fixed centre-right is simpler and avoids layout-dependent coordinate math.
- Should the dashboard fade-in only fire on navigation from login (session-storage flag), or always on entering the `(auth)` segment? Always-on is simpler; once-on-login requires a flag.
