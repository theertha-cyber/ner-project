## MODIFIED Requirements

### Requirement: Entity Type Definition

The system SHALL allow a Tenant Admin to define entity types within their tenant scope. Each entity type SHALL have: `name`, `description`, `examples` (JSON array of example strings), `qa_examples` (optional JSON array of question/answer pair objects, each with `question` and `answer` string fields), `validation_rule` (optional regex or type constraint), `target_table` (optional target DB table name for extraction), `value_kind` (optional semantic value kind, one of `text`, `number`, `duration`, `money`, `date`, `boolean`, defaulting to `text`), `value_unit` (optional canonical unit for the declared kind, e.g. `years`, `days`, `INR`), `sensitivity` (one of `open`, `pattern`, `local_only`, defaulting to `open` — see Entity Type Sensitivity Classification), `required_flag` (boolean), and `is_active` (boolean). Entity types SHALL be versioned — each update increments the version number. The system SHALL reject a `value_kind` outside the supported set. The `qa_examples` field SHALL be used exclusively as few-shot prompt context for LLM pre-labeling (see the `llm-prelabeling` capability); it SHALL NOT be used as a literal label source for any specific document, and it SHALL NOT be required for an entity type to be eligible for LLM pre-labeling extraction.

#### Scenario: Tenant Admin creates an entity type

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "customer_name", "description": "Full name of a customer", "examples": ["John Smith", "Acme Corp"], "validation_rule": null, "required_flag": true}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain an `entity_type` object with `name: "customer_name"`, `version: 1`, `is_active: true`
- **AND** `value_kind` SHALL default to `text`
- **AND** `sensitivity` SHALL default to `open`

#### Scenario: Tenant Admin updates an entity type

- **GIVEN** entity type "customer_name" exists with `version: 1`
- **WHEN** the Tenant Admin PUTs to `/api/v1/tenants/acme-corp/entity-types/customer_name` with `{"description": "Updated description"}`
- **THEN** the response SHALL have status 200
- **AND** `version` SHALL be `2`
- **AND** `description` SHALL be `"Updated description"`

#### Scenario: Tenant Admin adds QA pairs to an entity type

- **GIVEN** entity type "years_experience" exists with no `qa_examples` set
- **WHEN** the Tenant Admin PUTs to `/api/v1/tenants/acme-corp/entity-types/years_experience` with `{"qa_examples": [{"question": "How many years of experience does X have?", "answer": "X has 10 years of experience"}]}`
- **THEN** the response SHALL have status 200
- **AND** `qa_examples` SHALL contain the submitted question/answer pair
- **AND** `version` SHALL be incremented

#### Scenario: Entity type with no QA pairs remains valid

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "person_name", "description": "A person's full name", "examples": ["John Smith"]}` and no `qa_examples` field
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain an `entity_type` object with `qa_examples: []` or `qa_examples: null`

#### Scenario: Tenant Admin declares a structured value kind

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "YEARS_OF_EXP", "value_kind": "duration", "value_unit": "years"}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `value_kind: "duration"` and `value_unit: "years"`

#### Scenario: Unsupported value kind is rejected

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST an entity type with `{"name": "office_location", "value_kind": "geo"}`
- **THEN** the response SHALL have status 422
- **AND** no entity type SHALL be created

#### Scenario: Existing entity types keep working

- **GIVEN** entity types created before `value_kind` existed
- **WHEN** they are read through the entity types API
- **THEN** each SHALL report `value_kind: "text"` and `value_unit: null`
- **AND** extraction for those types SHALL behave exactly as before

#### Scenario: An entity type predating the view layer defaults to multi

- **GIVEN** an entity type row created before the view-layer metadata existed
- **WHEN** the `037` migration is applied
- **THEN** its `cardinality` SHALL be `multi`
- **AND** its `sql_identifier` SHALL be a valid identifier derived from its `name`

#### Scenario: Cardinality is constrained to the two known values

- **GIVEN** the `public.entity_definitions` table after migration `037`
- **WHEN** a row is written with `cardinality = 'many'`
- **THEN** the write SHALL be rejected by a CHECK constraint

#### Scenario: Two tenants may share an sql_identifier

- **GIVEN** tenant A has an entity type with `sql_identifier = 'e_skill'`
- **WHEN** tenant B creates an entity type that also slugs to `e_skill`
- **THEN** the write SHALL succeed
- **AND** a second row for tenant A with `sql_identifier = 'e_skill'` SHALL be rejected by the partial unique index on `(tenant_id, sql_identifier)`

#### Scenario: An entity type predating sensitivity classification defaults to open

- **GIVEN** an entity type row created before the `sensitivity` column existed
- **WHEN** the `049` migration is applied
- **THEN** its `sensitivity` SHALL be `open`
- **AND** its treatment by LLM pre-labeling SHALL be unchanged

## ADDED Requirements

### Requirement: Entity Type Sensitivity Classification

The system SHALL allow a Tenant Admin to classify each entity type with a `sensitivity` of `open`, `pattern`, or `local_only`, defaulting to `open`. `open` SHALL mean the entity type's real values may be included in a prompt sent to an external LLM provider. `pattern` SHALL mean the entity type's values follow a fixed, regex-matchable shape (e.g. SSN, phone number, email) and SHALL require a non-empty `validation_rule` on the same entity type; the system SHALL reject a create or update that sets `sensitivity: "pattern"` with no `validation_rule` present, with status 422. `local_only` SHALL mean the entity type's values are free text that cannot be reliably matched by a fixed pattern (e.g. a person's name, a home address) and SHALL require no additional configuration. `sensitivity` SHALL be mutable on an existing entity type and SHALL follow the same versioning behavior as any other field update — unlike `provenance`, it carries no immutability constraint. This requirement governs classification only; how (or whether) a consuming pipeline acts on `sensitivity` is defined by that pipeline's own capability.

#### Scenario: Tenant Admin classifies a type as pattern with a validation rule

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "ssn", "sensitivity": "pattern", "validation_rule": "^\\d{3}-\\d{2}-\\d{4}$"}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `sensitivity: "pattern"`

#### Scenario: A pattern-sensitivity type without a validation rule is rejected

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "ssn", "sensitivity": "pattern"}` and no `validation_rule`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate `pattern` sensitivity requires a `validation_rule`
- **AND** no entity type SHALL be created

#### Scenario: Tenant Admin classifies a type as local_only with no extra configuration

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "child_name", "sensitivity": "local_only"}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `sensitivity: "local_only"`

#### Scenario: An unsupported sensitivity value is rejected

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST an entity type with `{"name": "custom_type", "sensitivity": "confidential"}`
- **THEN** the response SHALL have status 422
- **AND** no entity type SHALL be created

#### Scenario: Sensitivity can be changed on an existing entity type

- **GIVEN** entity type "case_number" exists with `sensitivity: "open"` at `version: 1`
- **WHEN** the Tenant Admin PUTs to `/api/v1/tenants/acme-corp/entity-types/case_number` with `{"sensitivity": "local_only"}`
- **THEN** the response SHALL have status 200
- **AND** `sensitivity` SHALL be `"local_only"`
- **AND** `version` SHALL be incremented

#### Scenario: New entity types default to open

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST an entity type with no `sensitivity` field
- **THEN** the created entity type SHALL have `sensitivity: "open"`
