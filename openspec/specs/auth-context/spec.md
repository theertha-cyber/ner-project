# Auth Context

## Purpose

React context provider and hook for managing authenticated user state in the portal. Stores access tokens exclusively in memory (useRef) and exposes user identity to the component tree.

---

## Requirements

### Requirement: Auth Context Provider

The system SHALL provide an `AuthProvider` React component and `useAuth()` hook that manage authenticated user state. The provider SHALL store the access token exclusively in a `useRef` (never in `localStorage`, `sessionStorage`, or any cookie). The provider SHALL expose a `user: AuthUser | null` state value (in `useState`) that reflects the current authentication state and triggers re-renders when it changes. On mount, the provider SHALL call `POST /api/v1/auth/refresh` to silently restore an active session from the `httpOnly` cookie if one is present; if the refresh fails, `user` SHALL remain `null`. The `useAuth()` hook SHALL throw `"useAuth must be used within AuthProvider"` when called outside the provider.

The `AuthUser` interface SHALL contain: `userId: string`, `tenantId: string`, `role: "system_admin" | "tenant_admin" | "annotator" | "business_user"`, `email: string`, `tenantSlug: string | null` (null for system_admin).

#### Scenario: Successful login sets user and stores token in memory

- **GIVEN** no user is authenticated
- **WHEN** `login("user@acme.com", "password")` is called and the API returns a 200 with `access_token`, `refresh_token`, and user claims
- **THEN** `useAuth().user` SHALL be set to the decoded `AuthUser` object
- **AND** the access token SHALL be accessible to `authFetch` via the context ref
- **AND** neither the access token nor the refresh token SHALL appear in `localStorage`, `sessionStorage`, or any readable cookie

#### Scenario: Logout clears user and calls logout endpoint

- **GIVEN** a user is authenticated with a valid access token
- **WHEN** `logout()` is called
- **THEN** `POST /api/v1/auth/logout` SHALL be called with the `Authorization: Bearer <token>` header
- **AND** `useAuth().user` SHALL be set to `null`
- **AND** the access token ref SHALL be cleared

#### Scenario: On-mount refresh restores session from cookie

- **GIVEN** the browser holds a valid `refresh_token` httpOnly cookie from a previous session
- **WHEN** `AuthProvider` mounts (e.g. on page reload)
- **THEN** `POST /api/v1/auth/refresh` SHALL be called automatically (no user action)
- **AND** on success, `useAuth().user` SHALL be populated with the refreshed user claims
- **AND** the new access token SHALL be stored in the context ref

#### Scenario: On-mount refresh failure leaves user as null

- **GIVEN** no valid `refresh_token` cookie exists (expired or absent)
- **WHEN** `AuthProvider` mounts
- **THEN** the `POST /api/v1/auth/refresh` call SHALL receive a 401
- **AND** `useAuth().user` SHALL remain `null` after the failed attempt

#### Scenario: useAuth throws when called outside AuthProvider

- **GIVEN** a React component that calls `useAuth()` without being wrapped in `AuthProvider`
- **WHEN** the component renders
- **THEN** an error SHALL be thrown with message `"useAuth must be used within AuthProvider"`

### Requirement: Auth Context Access Token Exposure

The `AuthProvider` SHALL expose a `getAccessToken(): string | null` function (or equivalent ref-based accessor) that `authFetch` can call synchronously to read the current access token without triggering a context re-render. The provider SHALL also expose a `setAccessToken(token: string)` callback so `authFetch` can update the token after a silent refresh without routing through `setState`.

#### Scenario: authFetch reads token synchronously without re-render

- **GIVEN** a user is authenticated with a valid access token
- **WHEN** `authFetch` constructs the `Authorization: Bearer` header
- **THEN** it SHALL read the token via `getAccessToken()` synchronously
- **AND** the read SHALL not trigger a React re-render in any component

#### Scenario: authFetch updates token after silent refresh

- **GIVEN** a silent refresh returns a new `access_token`
- **WHEN** `authFetch` resolves the refresh
- **THEN** `setAccessToken(newToken)` SHALL be called
- **AND** subsequent `authFetch` calls SHALL use the new token value
