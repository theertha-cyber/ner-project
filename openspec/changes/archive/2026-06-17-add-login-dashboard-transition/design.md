## Context

The login page (`src/portal/src/app/login/page.tsx`) renders a composited animated background of four gradient orbs (colours `#c2410c`, `#ea580c`, `#f59e0b`, `#334155`) that follow cursor movement via `requestAnimationFrame`. Successful login calls `router.replace("/dashboard")` immediately after `await login(...)` resolves — no animation, no visual handoff.

The `(auth)` layout wraps every authenticated route. Dashboard (`src/portal/src/app/(auth)/dashboard/page.tsx`) mounts directly with no entry animation.

All animation today lives in CSS keyframes in `globals.css` (`popIn`, `meshDrift`) and inline `requestAnimationFrame` loops. The project uses Next.js 15 App Router with `"use client"` components. No animation library is currently installed.

## Goals / Non-Goals

**Goals:**

- Trigger a full-screen radial burst overlay when the sign-in button is pressed (on successful auth), visually echoing the orb colour palette.
- Navigate to dashboard only after the burst animation completes, so the transition is perceived as continuous.
- Apply a fast fade-in to the `(auth)` layout wrapper so the dashboard content is revealed gracefully after the burst.
- Keep all changes within the three existing files; introduce no new dependencies.

**Non-Goals:**

- Changing any layout, copy, or behaviour of the login form itself.
- Persisting animation state across hard reloads or SSR (transition is fire-and-forget).
- Animating failed login attempts.
- Supporting reduced-motion (deferred to a future a11y pass — see Risks).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004-openspec-governance | Planning artifacts live in `openspec/` | No constraint on frontend implementation |
| ADR-005-opencode-agent-boundaries | Agent implementation scope rules | No constraint on UI animation |

All other in-force ADRs concern backend topology, model strategy, and training infrastructure — none constrain a frontend CSS transition.

## Decisions

### Decision 1: CSS keyframe expand over GSAP / Framer Motion

**Choice:** Implement the burst as a CSS `@keyframes` animation on a fixed-position `<div>` overlay, driven by a `clip-path: circle(...)` expansion. No animation library.

**Rationale:** The existing animation pattern in the project (see `popIn`, `meshDrift` in `globals.css`, and the RAF loop in `AnimatedBackground`) is pure CSS + DOM. Adding GSAP or Framer Motion for a single one-shot transition would be a disproportionate bundle cost (~30 kB+ min+gz) and a dependency the rest of the project doesn't use.

**Alternatives considered:**
- Framer Motion `AnimatePresence` — elegant API but requires wrapping the router navigation in an exit animation, which conflicts with Next.js App Router's hard navigation model without additional shared state.
- GSAP `timeline` — overkill for one animation; adds a dependency.
- CSS `transition` on opacity — too subtle; doesn't reflect the dynamic energy of the orb background.

### Decision 2: `clip-path: circle(...)` expansion from card-side

**Choice:** Burst origin is fixed at `75% 50%` (right-centre of viewport, where the sign-in card lives) rather than the exact pointer position.

**Rationale:** The card is always in the right half of the viewport at desktop widths. Using a fixed origin avoids reading `getBoundingClientRect` on the button and managing event coordinates across state, keeping the implementation stateless with respect to pointer position.

**Alternatives considered:**
- Track pointer position at click time and pass to the overlay — possible but requires additional ref/state and complicates the `handleSubmit` flow.
- Expand from viewport centre (`50% 50%`) — less directionally linked to the card; the orb origin would feel disconnected.

### Decision 3: Delay navigation until `animationend`, not a fixed `setTimeout`

**Choice:** Attach an `onAnimationEnd` handler to the overlay `<div>` that calls `router.replace("/dashboard")`.

**Rationale:** `animationend` is event-driven and fires exactly when the CSS animation completes, regardless of frame rate or system load. A fixed `setTimeout` can fire too early (skipped frames) or too late (accumulated delay).

**Alternatives considered:**
- `setTimeout(navigate, 550)` — simpler but not strictly synchronised to the visual end of the animation.

### Decision 4: Fade-in applied to the `(auth)` layout, not just the dashboard page

**Choice:** Add `animation: dashFadeIn 0.4s ease both` to the outermost `<div>` in `src/portal/src/app/(auth)/layout.tsx`.

**Rationale:** The `(auth)` layout is the shared entry wrapper for all authenticated routes. Applying the fade there means navigation from login to any first-load authenticated route (dashboard, admin, etc.) is softened consistently. It does not re-fire on client-side navigations within the `(auth)` segment because Next.js only remounts the layout when the segment first mounts.

**Alternatives considered:**
- Apply only to `(auth)/dashboard/page.tsx` — works for the common case but misses direct-link entry to other protected routes.
- Use a session-storage flag to fire only on post-login navigation — correct but adds complexity (write flag before navigate, read and clear in layout) for marginal benefit.

## Risks / Trade-offs

- [No `prefers-reduced-motion` support] → Users with vestibular disorders will see the burst. Mitigation: a follow-up task can wrap the burst overlay in `@media (prefers-reduced-motion: reduce) { display: none }`. Tracked as open question.
- [clip-path animation not supported on IE11] → The project targets modern browsers (Next.js 15); IE11 is not a supported target. No mitigation needed.
- [Auth-layout fade-in fires on all first-entry navigations, not only post-login] → Acceptable; the fade is subtle (0.4 s, opacity 0→1) and improves all entry experiences, not just post-login.
- [If login API is fast (<100 ms), user may see burst begin before conscious button-press feedback registers] → The burst itself starts on `isPending` state change, which is set synchronously in `handleSubmit`, so there is no perceptible gap.

## Migration Plan

1. Add `@keyframes orbBurst` and `@keyframes dashFadeIn` to `globals.css`.
2. Add `isTransitioning` boolean state to `LoginPage`; wrap `router.replace` in the `onAnimationEnd` handler.
3. Render burst overlay `<div>` conditionally on `isTransitioning`.
4. Update `(auth)/layout.tsx` to apply `dashFadeIn` animation on the root wrapper.
5. Smoke-test login flow in browser; verify animation fires and navigation follows.

Rollback: revert the three file edits. No database migrations, no API changes, no feature flags.

## Open Questions

- Should `prefers-reduced-motion` immediately skip the burst and navigate, or show a simple cross-fade instead? (Follow-up a11y task.)
