# Login Page

## Purpose

Unauthenticated login page for the portal, providing credential entry, form validation, error display, and optional demo-mode role shortcuts.

---

## Requirements

### Requirement: Login Page Layout and Submission

The system SHALL provide a login page at the `/login` route (unauthenticated, outside the auth layout). The page SHALL render a centred glassmorphism card containing an email input, a password input, a "Sign in →" primary CTA button, and a form-level error message area. On successful login, the page SHALL redirect to `/dashboard`. The email and password inputs SHALL both be required; submitting an empty form SHALL not call the API. The "Sign in →" button SHALL be disabled and show a loading indicator while the login request is in-flight.

#### Scenario: Successful login redirects to dashboard

- **GIVEN** a user is on the `/login` page
- **WHEN** they enter valid credentials and click "Sign in →"
- **THEN** `useAuth().login()` SHALL be called with the provided email and password
- **AND** on success, the user SHALL be redirected to `/dashboard`

#### Scenario: Failed login shows form-level error

- **GIVEN** a user is on the `/login` page
- **WHEN** they submit invalid credentials (API returns 401)
- **THEN** the error message from the API response SHALL be displayed in the card
- **AND** the user SHALL remain on `/login`
- **AND** the password field SHALL NOT be cleared automatically

#### Scenario: Submit button is disabled while request is in-flight

- **GIVEN** a user submits the login form
- **WHEN** the `POST /api/v1/auth/login` request is in-flight
- **THEN** the "Sign in →" button SHALL be disabled
- **AND** a loading indicator (spinner or text change) SHALL be visible

#### Scenario: Already-authenticated user is redirected away from login

- **GIVEN** a user is already authenticated (`useAuth().user !== null`)
- **WHEN** they navigate to `/login`
- **THEN** they SHALL be redirected to `/dashboard` without seeing the login form

### Requirement: Demo Role Chips

When the environment variable `NEXT_PUBLIC_DEMO_MODE` is set to `"true"`, the login page SHALL render four clickable role chips below the form: `system_admin`, `tenant_admin`, `annotator`, `business_user`. Clicking a chip SHALL populate the email and password fields with hardcoded development credentials for that role and immediately submit the form. When `NEXT_PUBLIC_DEMO_MODE` is absent or not `"true"`, the chips SHALL NOT be rendered.

#### Scenario: Demo chips are visible when DEMO_MODE is enabled

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE=true` is set
- **WHEN** the login page renders
- **THEN** four role chips SHALL be visible: `system_admin`, `tenant_admin`, `annotator`, `business_user`

#### Scenario: Clicking a demo chip fills and submits credentials

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE=true` and the login page is rendered
- **WHEN** the user clicks the `tenant_admin` chip
- **THEN** the email and password fields SHALL be populated with the hardcoded `tenant_admin` credentials
- **AND** the login form SHALL be submitted automatically

#### Scenario: Demo chips are absent in production mode

- **GIVEN** `NEXT_PUBLIC_DEMO_MODE` is unset or set to a value other than `"true"`
- **WHEN** the login page renders
- **THEN** no role chip elements SHALL be present in the DOM
