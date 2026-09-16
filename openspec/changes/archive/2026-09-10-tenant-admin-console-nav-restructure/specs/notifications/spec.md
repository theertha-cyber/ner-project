## ADDED Requirements

### Requirement: Notification Storage

The system SHALL store notifications in `public.notifications` with `id`, `tenant_id`,
`recipient_role` (nullable), `recipient_user_id` (nullable), `kind`, `title`, `body`
(nullable), `resource_type` (nullable), `resource_id` (nullable), `read_at` (nullable), and
`created_at`. A notification SHALL be addressed to a role, a specific user, or both.

#### Scenario: A notification row is persisted

- **GIVEN** a service writes a notification for a tenant addressed to `recipient_role = "tenant_admin"`
- **WHEN** the row is inserted
- **THEN** it SHALL be retrievable with its `kind`, `title`, `body`, `resource_type`, `resource_id`, and a null `read_at`

### Requirement: Notification Read API

The system SHALL provide `GET /api/v1/notifications` returning notifications for the
caller's tenant that are addressed either to the caller's role or to the caller
specifically, newest first, with an `unread` count; `POST /api/v1/notifications/{id}/read`
marking one as read; and `POST /api/v1/notifications/read-all` marking all of the caller's
as read. A caller SHALL NOT see a notification for another tenant, nor one addressed only
to a different role.

#### Scenario: A tenant admin sees a tenant-admin-addressed notification

- **GIVEN** a `tenant_admin`-addressed notification exists for the caller's tenant
- **WHEN** an authenticated `tenant_admin` calls `GET /api/v1/notifications`
- **THEN** the notification SHALL appear in the response and count toward `unread`

#### Scenario: A business user does not see annotation notifications

- **GIVEN** a `tenant_admin`-addressed notification exists for the caller's tenant
- **WHEN** an authenticated `business_user` calls `GET /api/v1/notifications`
- **THEN** the notification SHALL NOT appear in the response

#### Scenario: Cross-tenant isolation

- **GIVEN** a notification exists for tenant A
- **WHEN** a `tenant_admin` of tenant B calls `GET /api/v1/notifications`
- **THEN** tenant A's notification SHALL NOT appear

#### Scenario: Marking one notification read

- **GIVEN** an unread notification addressed to the caller's role
- **WHEN** the caller calls `POST /api/v1/notifications/{id}/read`
- **THEN** the notification's `read_at` SHALL be set and it SHALL no longer count toward `unread`

#### Scenario: Marking a notification that is not the caller's

- **GIVEN** a notification for another tenant
- **WHEN** the caller calls `POST /api/v1/notifications/{id}/read` for it
- **THEN** the response SHALL be 404 and the notification SHALL be unchanged

### Requirement: Notification Bell

The portal topbar SHALL render a notification bell for the `tenant_admin` and `annotator`
roles showing the unread count as a badge and, on open, a list of recent notifications with
title, body, and relative time. Opening a notification SHALL mark it read; a "Mark all
read" action SHALL call `POST /api/v1/notifications/read-all`. The list SHALL be persistent
(server-backed), not a transient toast, and SHALL refresh periodically.

#### Scenario: Unread badge reflects the unread count

- **GIVEN** the caller has 3 unread notifications
- **WHEN** the topbar renders for a `tenant_admin`
- **THEN** the bell SHALL show a badge reading `3`

#### Scenario: The bell is absent for a business user

- **GIVEN** an authenticated `business_user`
- **WHEN** the topbar renders
- **THEN** no notification bell SHALL be present
