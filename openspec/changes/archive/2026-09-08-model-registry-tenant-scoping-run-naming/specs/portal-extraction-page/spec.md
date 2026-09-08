## ADDED Requirements

### Requirement: Base model confirmation gate on extraction runs

Before submitting an extraction run (Playground "Run extraction" or Batch Runs "New batch run"), the system SHALL check the tenant's currently active model (via the existing `/api/v1/models/active` query). If the active model resolves to the base model (`version_number === 0`), the system SHALL show a confirmation dialog stating that a fine-tuned model isn't available yet and asking whether to use the base model for this run, before sending the extraction request. Confirming SHALL proceed with the request exactly as before this change (the existing model-promotion fallback mechanism is unchanged). Declining SHALL cancel the run: no `POST /api/v1/extract` or `POST /api/v1/extract-batch` request SHALL be sent, and no batch run entry SHALL be created. When the active model is a promoted fine-tuned model (`version_number > 0`), no dialog SHALL be shown and the run SHALL proceed immediately, unchanged from current behavior.

#### Scenario: Playground run proceeds without a dialog when a fine-tuned model is promoted

- **GIVEN** the tenant's active model has `version_number: 3`
- **WHEN** the user clicks "Run extraction" in the Playground tab
- **THEN** no confirmation dialog SHALL appear
- **AND** `POST /api/v1/extract` SHALL be sent immediately

#### Scenario: Playground run shows confirmation dialog when only the base model is available

- **GIVEN** the tenant's active model has `version_number: 0`
- **WHEN** the user clicks "Run extraction" in the Playground tab
- **THEN** a confirmation dialog SHALL appear stating a fine-tuned model isn't available yet and asking to use the base model
- **AND** `POST /api/v1/extract` SHALL NOT be sent until the user responds

#### Scenario: Confirming the dialog proceeds with the base-model extraction

- **GIVEN** the confirmation dialog is shown after clicking "Run extraction" with no promoted model
- **WHEN** the user confirms ("Use base model")
- **THEN** `POST /api/v1/extract` SHALL be sent with the entered text
- **AND** the response SHALL be displayed exactly as in the no-dialog case

#### Scenario: Declining the dialog cancels the Playground run

- **GIVEN** the confirmation dialog is shown after clicking "Run extraction" with no promoted model
- **WHEN** the user declines
- **THEN** no `POST /api/v1/extract` request SHALL be sent
- **AND** the results panel SHALL remain unchanged (no spinner, no new results)

#### Scenario: Batch Runs shows confirmation dialog when only the base model is available

- **GIVEN** the tenant's active model has `version_number: 0`
- **WHEN** the user clicks "New batch run" in the Batch Runs tab
- **THEN** a confirmation dialog SHALL appear stating a fine-tuned model isn't available yet and asking to use the base model
- **AND** `POST /api/v1/extract-batch` SHALL NOT be sent until the user responds

#### Scenario: Declining the dialog cancels the batch run

- **GIVEN** the confirmation dialog is shown after clicking "New batch run" with no promoted model
- **WHEN** the user declines
- **THEN** no `POST /api/v1/extract-batch` request SHALL be sent
- **AND** no new run entry SHALL appear in the run list

#### Scenario: Confirming the dialog proceeds with the batch run

- **GIVEN** the confirmation dialog is shown after clicking "New batch run" with no promoted model
- **WHEN** the user confirms ("Use base model")
- **THEN** `POST /api/v1/extract-batch` SHALL be sent
- **AND** the new run SHALL appear at the top of the run list with status "queued", as in the no-dialog case
