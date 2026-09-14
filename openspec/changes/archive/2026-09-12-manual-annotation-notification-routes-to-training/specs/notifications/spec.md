## MODIFIED Requirements

### Requirement: Notification Bell

The portal topbar SHALL render a notification bell for the `tenant_admin` and `annotator`
roles showing the unread count as a badge and, on open, a list of recent notifications with
title, body, and relative time. Opening a notification SHALL mark it read; a "Mark all
read" action SHALL call `POST /api/v1/notifications/read-all`. The list SHALL be persistent
(server-backed), not a transient toast, and SHALL refresh periodically.

Clicking a notification whose `resource_type` is `annotation_task` (a manual annotation task
completed and is training-eligible) SHALL navigate the Tenant Admin to
`/training-jobs?source=manual` — the same destination the Manual landing page's own "Train
model" action uses, so the notification and the button agree on where "train on this" leads. A
notification whose `resource_type` is `prelabel_batch` (an automated batch's outcome) SHALL send
an `annotator` to that batch's review screen and a `tenant_admin` to the Automated flow's
retraining/promotion evidence page.

#### Scenario: Unread badge reflects the unread count

- **GIVEN** the caller has 3 unread notifications
- **WHEN** the topbar renders for a `tenant_admin`
- **THEN** the bell SHALL show a badge reading `3`

#### Scenario: The bell is absent for a business user

- **GIVEN** an authenticated `business_user`
- **WHEN** the topbar renders
- **THEN** no notification bell SHALL be present

#### Scenario: A completed manual annotation task notification routes to Models & Training scoped to manual

- **GIVEN** a `tenant_admin` has an unread notification with `resource_type: "annotation_task"`
- **WHEN** the notification is clicked
- **THEN** navigation SHALL go to `/training-jobs?source=manual`
- **AND** the notification SHALL be marked read

#### Scenario: An automated batch notification routes a tenant_admin to the retraining evidence page

- **GIVEN** a `tenant_admin` has an unread notification with `resource_type: "prelabel_batch"`
- **WHEN** the notification is clicked
- **THEN** navigation SHALL go to `/annotate/automated/retrain`

#### Scenario: An automated batch notification routes an annotator to that batch's review screen

- **GIVEN** an `annotator` has an unread notification with `resource_type: "prelabel_batch"` and
  a `resource_id`
- **WHEN** the notification is clicked
- **THEN** navigation SHALL go to `/annotate/review-batch/{resource_id}`
