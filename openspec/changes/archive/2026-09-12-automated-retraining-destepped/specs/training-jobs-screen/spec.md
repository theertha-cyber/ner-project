## ADDED Requirements

### Requirement: Retraining Evidence Link

The Model Versions view of the Training Jobs screen SHALL show a "Retraining & promotion
evidence" link for `tenant_admin`, navigating to `/annotate/automated/retrain`. This is the
retraining decision surface's primary entry point: retraining is a decision made in the context
of the model registry, not a step in the Automated annotation pipeline, so it is reached from
here rather than from a numbered stepper. The link SHALL NOT be shown in the Training Jobs view,
and SHALL NOT be shown to `system_admin`.

#### Scenario: Tenant admin sees the link in the Model Versions view

- **GIVEN** a `tenant_admin` views the Training Jobs screen with the Model Versions view selected
- **WHEN** the header renders
- **THEN** a "Retraining & promotion evidence" link SHALL be visible
- **AND** activating it SHALL navigate to `/annotate/automated/retrain`

#### Scenario: The link is absent from the Training Jobs view

- **GIVEN** a `tenant_admin` views the Training Jobs screen with the Training Jobs view selected
- **WHEN** the header renders
- **THEN** no "Retraining & promotion evidence" link SHALL be shown
- **AND** the "+ Submit job" action SHALL be shown instead

#### Scenario: The link is not shown to system_admin

- **GIVEN** a `system_admin` views the Training Jobs screen with the Model Versions view selected
- **WHEN** the header renders
- **THEN** no "Retraining & promotion evidence" link SHALL be shown
