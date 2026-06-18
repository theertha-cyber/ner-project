# Require Auth

## Purpose

Client-side route guard component that protects authenticated routes by checking session state and redirecting unauthenticated or unauthorised users.

---

## Requirements

### Requirement: RequireAuth Route Guard

The system SHALL provide a `<RequireAuth roles?: AuthUser["role"][]>` component that protects authenticated routes. When rendered, it SHALL immediately check `useAuth().user` on first render — no loading/pending state. If `user` is `null`, the component SHALL redirect to `/login` using `useRouter().replace()` and render `null` (no children, no flash of content). If `user` is not null and no `roles` prop is supplied, the component SHALL render its `children`. If `user` is not null and a `roles` array is supplied, the component SHALL render children only if `user.role` is included in the array; if the role does not match, it SHALL redirect to `/dashboard` (insufficient permissions, not unauthenticated).

#### Scenario: Unauthenticated access redirects to login

- **GIVEN** `useAuth().user` is `null` (no active session)
- **WHEN** a protected route wrapped in `<RequireAuth>` renders
- **THEN** `useRouter().replace("/login")` SHALL be called
- **AND** the children SHALL NOT be rendered

#### Scenario: Authenticated access renders children

- **GIVEN** `useAuth().user` is a valid `AuthUser` object
- **AND** no `roles` prop is provided to `<RequireAuth>`
- **WHEN** the guarded route renders
- **THEN** the children SHALL be rendered
- **AND** no redirect SHALL occur

#### Scenario: Role-restricted access with matching role renders children

- **GIVEN** `useAuth().user.role` is `"system_admin"`
- **WHEN** `<RequireAuth roles={["system_admin"]}>` renders
- **THEN** the children SHALL be rendered

#### Scenario: Role-restricted access with non-matching role redirects to dashboard

- **GIVEN** `useAuth().user.role` is `"annotator"`
- **WHEN** `<RequireAuth roles={["system_admin"]}>` renders
- **THEN** `useRouter().replace("/dashboard")` SHALL be called
- **AND** the children SHALL NOT be rendered
