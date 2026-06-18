## ADDED Requirements

### Requirement: Orb-burst overlay on successful sign-in

The login page SHALL display a full-screen radial gradient overlay that expands from the right-centre of the viewport immediately after a successful authentication response is received and before navigating to the dashboard.

The overlay SHALL use colours drawn from the existing animated orb palette: `#c2410c` (brand orange), `#ea580c` (mid-orange), and `#f59e0b` (amber), forming a radial gradient that bursts outward via `clip-path: circle(...)` expansion.

The overlay animation SHALL complete in ≤ 600 ms.

Navigation to `/dashboard` SHALL be deferred until the overlay animation fires its `animationend` event.

#### Scenario: Successful login triggers burst

- **GIVEN** the user is on the login page with the animated orb background visible
- **WHEN** the user submits valid credentials and the sign-in API call succeeds
- **THEN** a full-screen gradient overlay expands from the right-centre of the viewport, covering all page content within 600 ms

#### Scenario: Navigation deferred until burst ends

- **GIVEN** the burst overlay has started animating
- **WHEN** the overlay `animationend` event fires
- **THEN** the browser navigates to `/dashboard`

#### Scenario: Failed login shows no burst

- **GIVEN** the user submits invalid credentials and the sign-in API returns an error
- **WHEN** the error is displayed
- **THEN** no burst overlay is rendered and the login form remains interactive

#### Scenario: Login form unchanged during burst

- **GIVEN** the burst overlay has started
- **WHEN** the overlay is covering the screen
- **THEN** the login form fields and `AnimatedBackground` remain in the DOM beneath the overlay (overlay is z-indexed above them, not a replacement)

---

### Requirement: Dashboard fade-in on entry

The authenticated layout wrapper (`(auth)/layout.tsx`) SHALL apply a CSS fade-in animation (`opacity: 0 → 1`) over 400 ms when the layout segment first mounts, so the dashboard content is revealed gracefully after the burst overlay completes.

#### Scenario: Dashboard fades in after burst

- **GIVEN** the burst overlay animation has ended and navigation to `/dashboard` has been triggered
- **WHEN** the `(auth)` layout mounts and renders the dashboard content
- **THEN** the dashboard content fades from transparent to fully opaque over 400 ms

#### Scenario: Fade-in keyframe defined in global CSS

- **GIVEN** the project's `globals.css` file
- **WHEN** the file is inspected
- **THEN** a `@keyframes dashFadeIn` rule exists that transitions `opacity` from `0` to `1`

---

### Requirement: No regression to login page behaviour

The sign-in page SHALL retain all existing behaviour and visual appearance (form layout, demo chips, animated orb background, error display, loading spinner) when the transition feature is added.

#### Scenario: Login page looks identical before submit

- **GIVEN** the login page is loaded
- **WHEN** no submit action has been taken
- **THEN** the page renders identically to its pre-transition state: animated background, hero copy, and sign-in card all visible

#### Scenario: Error state remains functional

- **GIVEN** a failed login attempt has displayed an error message
- **WHEN** the user corrects credentials and resubmits
- **THEN** the form processes the new attempt normally and the burst fires only on the next successful response
