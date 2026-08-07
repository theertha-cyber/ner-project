## ADDED Requirements

### Requirement: Continue-Work Card Payload

The dashboard summary response for role `annotator` SHALL include a top-level optional field `continueWork` carrying the task the annotator should return to. When present it SHALL contain: `taskId` (string), `documentId` (string), `documentName` (string — the document's filename, or a truncated task identifier when the filename is absent), `status` (string — the task's current status), `spanCount` (integer — confirmed spans already recorded on that document), and `mode` (string — one of `"resume"`, `"start"`, `"review"`).

Selection SHALL follow this precedence:

1. The most recently worked task with status `in-progress` → `mode: "resume"`
2. Otherwise the oldest not-started task → `mode: "start"`
3. Otherwise the most recently worked task with status `completed` → `mode: "review"`
4. Otherwise `null`

"Most recently worked" SHALL be ordered by `COALESCE(annotation_tasks.updated_at, the maximum span `updated_at` on the task's document, annotation_tasks.created_at)` — `updated_at` on the task is not maintained by any writer and is NULL in practice, so the ordering SHALL NOT depend on it alone.

"Not started" SHALL match any of the status values `unannotated`, `open`, or `pending`. All three vocabularies exist across the migrations, the annotation service, and the seed data, and a task carrying any of them has not been begun.

When the annotator has no task at all, `continueWork` SHALL be `null`. The field SHALL be omitted or `null` for all non-annotator roles.

`continueWork` SHALL be computed independently of the other annotator fields: a failure while computing it SHALL set it to `null` and SHALL NOT fail the request or blank any other card.

#### Scenario: in-progress task is returned for resume

- **GIVEN** the caller has role `annotator` and has a task with status `in-progress` on document `resume_01.pdf` carrying 12 confirmed spans
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.mode` is `"resume"`
- **AND** `continueWork.documentName` is `"resume_01.pdf"`
- **AND** `continueWork.spanCount` is `12`
- **AND** `continueWork.taskId` identifies that task

#### Scenario: most recently worked task wins when several are in progress

- **GIVEN** the caller has role `annotator` with two tasks in status `in-progress`
- **AND** the second task's document carries the more recent span activity
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.taskId` identifies the second task

#### Scenario: ordering falls back when updated_at is unmaintained

- **GIVEN** the caller has role `annotator` with in-progress tasks whose `annotation_tasks.updated_at` is `NULL`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the selected task is the one whose document has the most recent span `updated_at`
- **AND** when no spans exist on any candidate document, the task with the most recent `created_at` is selected

#### Scenario: unstarted task is offered when nothing is in progress

- **GIVEN** the caller has role `annotator` with no `in-progress` task and two tasks in status `unannotated`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.mode` is `"start"`
- **AND** `continueWork.taskId` identifies the older of the two unannotated tasks

#### Scenario: every not-started vocabulary is recognised

- **GIVEN** the caller has role `annotator` with no `in-progress` task
- **AND** their only remaining task carries status `pending`, `unannotated`, or `open`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.mode` is `"start"`
- **AND** `continueWork.taskId` identifies that task

#### Scenario: unstarted work outranks finished work

- **GIVEN** the caller has role `annotator` with no `in-progress` task
- **AND** they have both a `completed` task worked on today and a `pending` task never touched
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.mode` is `"start"`
- **AND** `continueWork.taskId` identifies the `pending` task

#### Scenario: completed task is offered for review when nothing else remains

- **GIVEN** the caller has role `annotator` and every assigned task has status `completed`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork.mode` is `"review"`
- **AND** `continueWork.taskId` identifies the most recently worked completed task

#### Scenario: caught-up state when no tasks are assigned at all

- **GIVEN** the caller has role `annotator` with no assigned tasks
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** `continueWork` is `null`

#### Scenario: query failure degrades only this card

- **GIVEN** the caller has role `annotator` and the continue-work query raises an error
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response status is `200`
- **AND** `continueWork` is `null`
- **AND** the `stats` array and readiness panel still carry their real values

### Requirement: Continue-Work Card Rendering

The annotator dashboard SHALL render a `ContinueWorkCard` as the first cell of the stat row, ahead of the `StatCard` components. The card SHALL display the document name, the span count already recorded, and a call-to-action linking to `/annotation?task=<taskId>`.

The call-to-action label SHALL reflect `mode`: "Resume" when `mode` is `"resume"`, "Start" when `mode` is `"start"`, "Review" when `mode` is `"review"`. A `"review"` card SHALL NOT present itself as outstanding work — it describes a task already submitted. When `continueWork` is `null` the card SHALL render a caught-up state with no link. While the dashboard query is in flight the card SHALL render a skeleton placeholder consistent with the adjacent stat cards.

Because the card shares a three-column row, the document name SHALL be constrained to a single line with ellipsis truncation, and the untruncated name SHALL remain available via the element's `title` attribute.

#### Scenario: resume card links into the workspace

- **GIVEN** `continueWork` is present with `mode: "resume"`, `documentName: "resume_01.pdf"`, and `taskId: "abc123"`
- **WHEN** the annotator dashboard renders
- **THEN** the card shows `"resume_01.pdf"` and a "Resume" action
- **AND** the action links to `/annotation?task=abc123`

#### Scenario: start card is shown for an unstarted task

- **GIVEN** `continueWork` is present with `mode: "start"`
- **WHEN** the annotator dashboard renders
- **THEN** the call-to-action reads "Start"

#### Scenario: review card does not present finished work as outstanding

- **GIVEN** `continueWork` is present with `mode: "review"`
- **WHEN** the annotator dashboard renders
- **THEN** the call-to-action reads "Review"
- **AND** the card does not describe the task as in progress or outstanding

#### Scenario: caught-up state renders without a link

- **GIVEN** `continueWork` is `null` for an annotator
- **WHEN** the annotator dashboard renders
- **THEN** the card renders a caught-up message
- **AND** no navigation link is present

#### Scenario: long document name is truncated but recoverable

- **GIVEN** `continueWork.documentName` is longer than the card's available width
- **WHEN** the card renders
- **THEN** the name is clipped to a single line with an ellipsis
- **AND** the element's `title` attribute carries the full name

#### Scenario: card is not rendered for other roles

- **GIVEN** the authenticated user has role `tenant_admin`, `system_admin`, or `business_user`
- **WHEN** the dashboard renders
- **THEN** no continue-work card is present
