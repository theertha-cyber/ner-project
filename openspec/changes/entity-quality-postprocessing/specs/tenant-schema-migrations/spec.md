## ADDED Requirements

### Requirement: `document_entities` gains provenance columns on the template and every tenant schema

A migration SHALL add provenance columns to `document_entities` — the original BERT value and type, post-processing status, post-processor model, prompt version, processing timestamp, extraction schema version, and occurrence count — applied to `tenant_template` and to every existing tenant schema. All added columns SHALL be nullable or defaulted so no existing row or reader breaks.

#### Scenario: Columns exist on every tenant schema

- **GIVEN** a database with multiple tenant schemas and the template
- **WHEN** the migration is applied
- **THEN** `document_entities` in every tenant schema and in `tenant_template` SHALL contain the provenance columns

#### Scenario: Existing rows survive unchanged

- **GIVEN** tenant schemas holding existing `document_entities` rows
- **WHEN** the migration is applied
- **THEN** no existing `entity_value`, `entity_type`, `normalized_value`, or `confidence` value SHALL be modified
- **AND** the new columns SHALL hold their default or NULL

#### Scenario: A tenant schema missing the table does not abort the migration

- **GIVEN** a tenant schema with no `document_entities` table
- **WHEN** the migration is applied
- **THEN** that schema SHALL be skipped
- **AND** the migration SHALL complete for all other schemas

#### Scenario: Downgrade removes only the added columns

- **GIVEN** the migration has been applied
- **WHEN** it is downgraded
- **THEN** only the added columns SHALL be dropped
- **AND** all pre-existing data SHALL remain intact

### Requirement: `extraction_runs` gains processing-mode columns on the template and every tenant schema

A migration SHALL add `processing_mode`, post-processor model, prompt version, and a degraded indicator to `extraction_runs`, applied to `tenant_template` and every existing tenant schema. `processing_mode` SHALL default to `bert_only` so existing rows describe what actually happened.

#### Scenario: Columns exist on every tenant schema

- **GIVEN** a database with multiple tenant schemas and the template
- **WHEN** the migration is applied
- **THEN** `extraction_runs` in every tenant schema and in `tenant_template` SHALL contain the processing-mode columns

#### Scenario: Existing runs are labelled BERT-only

- **GIVEN** existing `extraction_runs` rows created before this change
- **WHEN** the migration is applied
- **THEN** each SHALL carry `processing_mode = 'bert_only'`

#### Scenario: New tenants provisioned from the template inherit both changes

- **GIVEN** the migrations have been applied to `tenant_template`
- **WHEN** a new tenant is provisioned
- **THEN** its `document_entities` and `extraction_runs` tables SHALL contain the new columns
