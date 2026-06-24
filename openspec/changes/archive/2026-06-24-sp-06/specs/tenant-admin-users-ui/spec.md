## ADDED Requirements

### Requirement: Tenant Admin User List

The system SHALL provide a tenant admin portal page at `/users` that displays a paginated or full list of all users belonging to the authenticated tenant admin's tenant. The page SHALL show each user's email, role, status, and creation date. The page SHALL allow filtering by role. The page SHALL be accessible only to users with role `tenant_admin`.

#### Scenario: Tenant admin views user list

- **GIVEN** an authenticated `tenant_admin` user whose tenant has 3 users
- **WHEN** they navigate to `/users`
- **THEN** the page SHALL display a table with 3 user rows
- **AND** each row SHALL show `email`, `role`, `status`, and `created_at`
- **AND** a "Create User" control SHALL be visible

#### Scenario: Tenant admin filters users by role

- **GIVEN** an authenticated `tenant_admin` whose tenant has 2 annotators and 1 business_user
- **WHEN** they select the `annotator` filter on the `/users` page
- **THEN** only the 2 annotator rows SHALL be visible

#### Scenario: Non-tenant-admin cannot access users page

- **GIVEN** an authenticated `annotator` user
- **WHEN** they navigate to `/users`
- **THEN** the page SHALL NOT be reachable via navigation (not in `navFor("annotator")`)

### Requirement: Tenant Admin User Creation

The system SHALL allow a `tenant_admin` to create a new user from the `/users` page by providing an email address, password, and role. The system SHALL call `POST /api/v1/users` with the provided values. On success, the new user SHALL appear in the list without a full page reload.

#### Scenario: Tenant admin creates a new annotator user

- **GIVEN** an authenticated `tenant_admin` on the `/users` page
- **WHEN** they open the "Create User" form, fill in email, password, and select role `annotator`, and submit
- **THEN** the form SHALL call `POST /api/v1/users`
- **AND** on a 201 response the new user SHALL be appended to the displayed list
- **AND** the form SHALL close/reset

#### Scenario: Tenant admin exceeds user quota on creation

- **GIVEN** an authenticated `tenant_admin` whose tenant has reached `max_users`
- **WHEN** they submit the "Create User" form
- **THEN** the API SHALL return 429
- **AND** the page SHALL display an error message indicating the quota is exceeded

#### Scenario: Duplicate email rejected on creation

- **GIVEN** a user with email `existing@example.com` already exists in the tenant
- **WHEN** a `tenant_admin` submits the "Create User" form with the same email
- **THEN** the API SHALL return 409
- **AND** the page SHALL display an error indicating the email is already taken

### Requirement: Tenant Admin User Role Update

The system SHALL allow a `tenant_admin` to change the role of an existing user in their tenant. The role SHALL be updated via `PUT /api/v1/users/{id}` with the new role value. Allowed roles are `annotator`, `business_user`, and `tenant_admin`.

#### Scenario: Tenant admin changes a user's role

- **GIVEN** an authenticated `tenant_admin` and an existing `annotator` user `user-123`
- **WHEN** the tenant admin selects a new role `business_user` for `user-123` and confirms
- **THEN** the system SHALL call `PUT /api/v1/users/user-123` with `{"role": "business_user"}`
- **AND** the row SHALL reflect the updated role on success

### Requirement: Tenant Admin User Deactivation

The system SHALL allow a `tenant_admin` to deactivate a user in their tenant. Deactivation SHALL call `DELETE /api/v1/users/{id}`. The UI SHALL require explicit confirmation before deactivating. Deactivated users SHALL remain visible in the list with `status: "inactive"`.

#### Scenario: Tenant admin deactivates a user

- **GIVEN** an authenticated `tenant_admin` and an active user `user-123`
- **WHEN** the tenant admin clicks "Deactivate" for `user-123` and confirms the prompt
- **THEN** the system SHALL call `DELETE /api/v1/users/user-123`
- **AND** the row SHALL update to show `status: "inactive"`

#### Scenario: Deactivation is cancelled

- **GIVEN** an authenticated `tenant_admin` clicks "Deactivate" for a user
- **WHEN** they cancel the confirmation prompt
- **THEN** no API call SHALL be made
- **AND** the user's status SHALL remain unchanged
