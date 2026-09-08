## MODIFIED Requirements

### Requirement: Base Model (Version 0) Entry

Per ADR-008, the system SHALL show the base model (`dslim/bert-base-NER`, version 0) as a permanent entry at the bottom of the model registry list, but ONLY to users with the `system_admin` role. For `tenant_admin`, `business_user`, and `annotator` roles, the base model card SHALL be omitted from the list entirely — these roles SHALL still see the `/models` page and their tenant's real (non-synthetic) model versions. Version 0 remains a shared singleton with no database row and no run name; it is treated as "promoted" when no fine-tuned model is active and as "archived" otherwise.

#### Scenario: Base model card visible to system_admin with no fine-tuned models trained yet

- **GIVEN** an authenticated `system_admin` user viewing a tenant with no fine-tuned models trained yet
- **WHEN** the user navigates to `/models`
- **THEN** a "Base Model" card with version 0 is visible in the list and is marked as the active model

#### Scenario: Base model card visible to system_admin alongside fine-tuned models

- **GIVEN** an authenticated `system_admin` user viewing a tenant with fine-tuned models (two promoted/archived versions)
- **WHEN** the user navigates to `/models`
- **THEN** fine-tuned model cards appear above the base model card, which is shown last

#### Scenario: Base model detail panel shows no action buttons

- **GIVEN** the base model (version 0) card is selected by a `system_admin`
- **WHEN** the detail panel renders
- **THEN** no Promote, Demote, or Warmup buttons are shown, and the model name `dslim/bert-base-NER` is visible

#### Scenario: Base model card hidden for tenant_admin

- **GIVEN** an authenticated `tenant_admin` user viewing a tenant with no fine-tuned models trained yet
- **WHEN** the user navigates to `/models`
- **THEN** no "Base Model" card is visible in the list
- **AND** the page still renders (no redirect, no error state)

#### Scenario: Base model card hidden for business_user and annotator

- **GIVEN** an authenticated `business_user` or `annotator` user viewing any tenant
- **WHEN** the user navigates to `/models`
- **THEN** no "Base Model" card is visible in the list

#### Scenario: Base model card hidden even when it is the tenant's only active model

- **GIVEN** an authenticated `tenant_admin` user whose tenant has no promoted fine-tuned model (base model is the de facto active model for extraction)
- **WHEN** the user navigates to `/models`
- **THEN** the model list SHALL NOT include a base model card
- **AND** an empty-state message indicating no models have been trained yet SHALL be shown if there are no fine-tuned models either

### Requirement: Model Version Card

The system SHALL render each fine-tuned model version as a card in the list showing its run name (`run-{NNN}-{YYYYMMDD}`), status badge (training/completed/promoted/archived), F1 score (when available), and creation date. For legacy model versions created before run-name tracking existed (`run_name` is absent), the card SHALL fall back to displaying `v{version_number}`.

#### Scenario: Card displays run name for a completed model version

- **GIVEN** a model version with `run_name: "run-003-20260729"`, status "completed", F1=0.89, created_at="2026-07-29"
- **WHEN** the card renders
- **THEN** "run-003-20260729", "Completed" badge, "F1 0.89", and the creation date are visible

#### Scenario: Promoted card has distinct visual treatment

- **GIVEN** a model version with `run_name: "run-002-20260715"` is in "promoted" status
- **WHEN** the card renders
- **THEN** a "Promoted" badge with primary color is visible alongside the "run-002-20260715" label

#### Scenario: Card for training version shows F1 as pending

- **GIVEN** a model version with `run_name: "run-004-20260729"` in "training" status with no metrics yet
- **WHEN** the card renders
- **THEN** "F1 —" (pending indicator) is shown

#### Scenario: Legacy model version without a run name falls back to version-number display

- **GIVEN** a model version with `run_name: null` and `version_number: 1`
- **WHEN** the card renders
- **THEN** "v1" is shown in place of a run name
