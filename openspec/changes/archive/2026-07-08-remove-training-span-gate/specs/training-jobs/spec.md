## ADDED Requirements

### Requirement: Submit form span preflight is informational only

The Training Queue's submit job form SHALL display the tenant's current confirmed span count when opened, for informational purposes only. The client SHALL NOT compute or enforce its own minimum-span threshold. The submit action SHALL be enabled or disabled based solely on hyperparameter form validation (learning rate, epochs, batch size, max sequence length) and submission-in-flight state — never on span count. Enforcement of any minimum annotated-entity threshold remains solely the responsibility of the `POST /api/v1/training-jobs` endpoint; if the backend rejects a submission for insufficient entities, that error SHALL be surfaced to the user through the existing submission error display.

#### Scenario: Submit enabled with span count below the legacy 500 threshold

- **GIVEN** a tenant with fewer than 500 confirmed spans
- **AND** the submit form's hyperparameter fields all contain valid values
- **WHEN** the Tenant Admin opens the Submit Training Job form
- **THEN** the Submit button SHALL be enabled
- **AND** the preflight display SHALL show the confirmed span count without any pass/fail language or threshold comparison

#### Scenario: Preflight display shows span count while loading and on fetch failure

- **GIVEN** the Tenant Admin opens the Submit Training Job form
- **WHEN** the span count request is in flight
- **THEN** the preflight display SHALL show a loading state
- **WHEN** the span count request fails
- **THEN** the preflight display SHALL indicate the count is unavailable
- **AND** the Submit button's enabled state SHALL NOT be affected by the span count fetch succeeding, failing, or being unavailable

#### Scenario: Backend rejection for insufficient entities is surfaced after submit

- **GIVEN** a tenant whose annotated entity count is below the backend's configured minimum
- **WHEN** the Tenant Admin submits the Submit Training Job form
- **AND** `POST /api/v1/training-jobs` responds with a 422 indicating insufficient annotated entities
- **THEN** the form SHALL display the backend's error message to the user
- **AND** the form SHALL remain open with the entered hyperparameters intact