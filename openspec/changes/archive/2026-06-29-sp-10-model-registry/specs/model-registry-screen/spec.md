## ADDED Requirements

### Requirement: Model Versions List Page

The system SHALL render a model registry page at `/models` that displays all model versions for the tenant in a list, ordered by version number descending, with a detail panel showing evaluation metrics, artifact path, MLflow run link, and role-gated action buttons.

#### Scenario: Page renders header and card list for tenant admin

- **GIVEN** an authenticated tenant_admin user with 3 model versions (v1 archived, v2 promoted, v3 completed)
- **WHEN** the user navigates to `/models`
- **THEN** the "Model Registry" h1, `/api/v1/models` moniker, version count summary, and a list of model version cards are visible

#### Scenario: Card list shows skeleton while fetching

- **GIVEN** the API call is pending
- **WHEN** the page first mounts
- **THEN** 3 skeleton placeholder cards are visible

#### Scenario: Empty state when no model versions exist

- **GIVEN** the API returns an empty array
- **WHEN** the page renders
- **THEN** an empty-state message appears indicating no models have been trained yet

### Requirement: Model Version Card

The system SHALL render each model version as a card in the list showing version number, status badge (training/completed/promoted/archived), F1 score (when available), and creation date.

#### Scenario: Card displays all fields for a completed model version

- **GIVEN** model version v3 with status "completed", F1=0.89, created_at="2026-06-20"
- **WHEN** the card renders
- **THEN** "v3", "Completed" badge, "F1 0.89", and the creation date are visible

#### Scenario: Promoted card has distinct visual treatment

- **GIVEN** model version v2 is in "promoted" status
- **WHEN** the card renders
- **THEN** a "Promoted" badge with primary color is visible

#### Scenario: Card for training version shows F1 as pending

- **GIVEN** model version v3 in "training" status with no metrics yet
- **WHEN** the card renders
- **THEN** "F1 —" (pending indicator) is shown

### Requirement: Model Detail Panel

The system SHALL display a detail panel when a model version card is selected, showing evaluation metrics grid (F1, precision, recall, loss), artifact path, MLflow run link, training job lineage, per-entity metrics (collapsible), and role-gated action buttons.

#### Scenario: Detail panel shows metrics for a completed model

- **GIVEN** a completed model version v3 with metrics `{"eval_f1": 0.89, "eval_precision": 0.91, "eval_recall": 0.87, "eval_loss": 0.12}`
- **WHEN** a user clicks the v3 card
- **THEN** the detail panel shows F1 0.89, Precision 0.91, Recall 0.87, and Loss 0.12

#### Scenario: Detail panel shows MLflow run link

- **GIVEN** a completed model version with `mlflow_run_url: "http://mlflow:5000/#/experiments/1/runs/abc123"`
- **WHEN** the detail panel renders
- **THEN** an MLflow link with `target="_blank"` is visible pointing to the run URL

#### Scenario: Detail panel shows artifact path

- **GIVEN** a completed model version with `artifact_path: "tenants/acme-corp/models/v3"`
- **WHEN** the detail panel renders
- **THEN** the artifact path is displayed in monospace

#### Scenario: Detail panel shows per-entity metrics in collapsible section

- **GIVEN** a model version with per-entity F1 scores like `{"vendor_name_f1": 0.92, "invoice_date_f1": 0.85}`
- **WHEN** the detail panel renders
- **THEN** a "Per-Entity Metrics" collapsible section shows each entity type and its F1 score

#### Scenario: No model selected shows empty state

- **GIVEN** the page has loaded with model versions
- **WHEN** no card is selected
- **THEN** the detail panel shows "Select a model version to view details"

### Requirement: Promote Model Version

The system SHALL allow a tenant_admin to promote a "completed" model version. On success, the previously promoted version's badge SHALL change to "archived" and the newly promoted version SHALL show "promoted".

#### Scenario: Promote a completed model

- **GIVEN** v3 is "completed" and v2 is currently "promoted"
- **WHEN** a tenant_admin clicks "Promote" on v3
- **THEN** a POST is sent to `/api/v1/models/{v3_id}/promote`, the success toast appears, v3 shows "Promoted", and v2 shows "Archived"

#### Scenario: Promote button is hidden for business_user

- **GIVEN** an authenticated business_user viewing a completed model
- **WHEN** the detail panel renders
- **THEN** no "Promote" button is visible

#### Scenario: Promote button is hidden for non-completed models

- **GIVEN** a model version in "training" status
- **WHEN** the detail panel renders
- **THEN** no "Promote" button is visible

#### Scenario: Promote returns error toast on API failure

- **GIVEN** the API returns 422 or 500
- **WHEN** a tenant_admin clicks "Promote"
- **THEN** an error toast is shown

### Requirement: Demote Model Version

The system SHALL allow a tenant_admin to demote the currently "promoted" model version, returning it to "completed" status. The tenant SHALL then have no promoted model.

#### Scenario: Demote the promoted model

- **GIVEN** v2 is currently "promoted"
- **WHEN** a tenant_admin clicks "Demote" on v2
- **THEN** a POST is sent to `/api/v1/models/{v2_id}/demote`, the success toast appears, and v2 shows "Completed"

#### Scenario: Demote button is hidden when model is not promoted

- **GIVEN** a model version in "completed" status
- **WHEN** the detail panel renders
- **THEN** no "Demote" button is visible

### Requirement: Warmup Model Version

The system SHALL allow a tenant_admin to trigger model-serving cache warmup for any model version.

#### Scenario: Warmup a completed model

- **GIVEN** a completed model version v3
- **WHEN** a tenant_admin clicks "Warmup"
- **THEN** a POST is sent to `/api/v1/models/{v3_id}/warmup`, and a success toast appears

#### Scenario: Warmup button shows loading state during request

- **GIVEN** a model version with warmup in progress
- **WHEN** the warmup request is pending
- **THEN** the "Warmup" button shows a spinner and is disabled

### Requirement: Model Versions API Hooks

The system SHALL provide TanStack Query hooks for listing model versions, fetching the active model, and promoting/demoting/warming up model versions.

#### Scenario: useModelVersions fetches tenant-scoped list

- **GIVEN** user authenticated as "acme-corp"
- **WHEN** `useModelVersions()` is called
- **THEN** it fetches `GET /api/v1/models` with query key `["models", tenantSlug]`

#### Scenario: useModelVersions returns active model separately

- **GIVEN** a tenant with a promoted model
- **WHEN** `useModelVersions()` is called
- **THEN** the hook also fetches `GET /api/v1/models/active` and exposes the active model data

#### Scenario: usePromoteModel invalidates list and active queries on success

- **GIVEN** the mutation is called with a valid model ID
- **WHEN** POST returns 200
- **THEN** both `["models", tenantSlug]` and `["models", "active", tenantSlug]` queries are invalidated

### Requirement: Base Model (Version 0) Entry

Per ADR-008, the system SHALL always show the base model (`dslim/bert-base-NER`, version 0) as a permanent entry at the bottom of the model registry list. Version 0 is a shared singleton with no database row; it is treated as "promoted" when no fine-tuned model is active and as "archived" otherwise.

#### Scenario: Base model card always visible in the list

- **GIVEN** a tenant with no fine-tuned models trained yet
- **WHEN** the user navigates to `/models`
- **THEN** a "Base Model" card with version 0 is visible in the list and is marked as the active model

#### Scenario: Base model card visible alongside fine-tuned models

- **GIVEN** a tenant with fine-tuned models (v1, v2 promoted)
- **WHEN** the user navigates to `/models`
- **THEN** fine-tuned model cards appear above the base model card, which is shown last

#### Scenario: Base model detail panel shows no action buttons

- **GIVEN** the base model (version 0) card is selected
- **WHEN** the detail panel renders
- **THEN** no Promote, Demote, or Warmup buttons are shown (even for tenant_admin), and the model name `dslim/bert-base-NER` is visible
