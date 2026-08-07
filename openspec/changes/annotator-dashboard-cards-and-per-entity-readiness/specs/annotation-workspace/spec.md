## ADDED Requirements

### Requirement: Pending Tasks Can Be Started

The annotation task status transition endpoint SHALL accept `pending` as a startable status, permitting `pending → in-progress`. `pending` is written by the tenant seed path (`src/gateway/seed.py`) but is absent from the transition table, so every attempt to move such a task currently fails with `422 INVALID_TRANSITION` and the task cannot be worked on by any route.

This addition SHALL NOT alter any other transition. `unannotated → in-progress`, `in-progress → completed`, and `completed → completed` SHALL remain exactly as they are; `completed` SHALL remain terminal; and no transition **into** `pending` SHALL be introduced. The existing precondition that a task SHALL NOT move to `completed` unless its document has at least one confirmed span SHALL continue to apply unchanged.

#### Scenario: pending task can be started

- **GIVEN** an annotation task with status `pending`
- **WHEN** a transition to `in-progress` is requested
- **THEN** the response is successful
- **AND** the task's status becomes `in-progress`

#### Scenario: pending task cannot skip straight to completed

- **GIVEN** an annotation task with status `pending`
- **WHEN** a transition to `completed` is requested
- **THEN** the response is `422` with code `INVALID_TRANSITION`

#### Scenario: existing transitions are unchanged

- **GIVEN** annotation tasks with statuses `unannotated`, `in-progress`, and `completed`
- **WHEN** each is transitioned to `in-progress`, `completed`, and `completed` respectively
- **THEN** each transition is permitted exactly as before this change

#### Scenario: completed remains terminal

- **GIVEN** an annotation task with status `completed`
- **WHEN** a transition to `in-progress` or `pending` is requested
- **THEN** the response is `422` with code `INVALID_TRANSITION`

#### Scenario: span precondition still guards completion

- **GIVEN** an annotation task with status `in-progress` whose document has no confirmed spans
- **WHEN** a transition to `completed` is requested
- **THEN** the response is `422` with code `NO_SPANS`
