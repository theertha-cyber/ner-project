# Entity Configuration

## Purpose

Tenant-scoped entity type management. Allows Tenant Admins to define, version, and manage the entity types used for NER annotation and extraction.

---

## Requirements

### Requirement: Entity Type Definition

The system SHALL allow a Tenant Admin to define entity types within their tenant scope. Each entity type SHALL have: `name`, `description`, `examples` (JSON array of example strings), `qa_examples` (optional JSON array of question/answer pair objects, each with `question` and `answer` string fields), `validation_rule` (optional regex or type constraint), `target_table` (optional target DB table name for extraction), `required_flag` (boolean), and `is_active` (boolean). Entity types SHALL be versioned — each update increments the version number. The `qa_examples` field SHALL be used exclusively as few-shot prompt context for LLM pre-labeling (see the `llm-prelabeling` capability); it SHALL NOT be used as a literal label source for any specific document, and it SHALL NOT be required for an entity type to be eligible for LLM pre-labeling extraction.

#### Scenario: Tenant Admin creates an entity type

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "customer_name", "description": "Full name of a customer", "examples": ["John Smith", "Acme Corp"], "validation_rule": null, "required_flag": true}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain an `entity_type` object with `name: "customer_name"`, `version: 1`, `is_active: true`

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

### Requirement: Base Label Mapping

The system SHALL allow each entity type to define a `base_label_mapping` field: a JSON object mapping base model CoNLL class names (PER, ORG, LOC, MISC) to this entity type. If an entity type has no mapping, it will not receive pre-labels during annotation. The system SHALL validate that all keys in the mapping are one of PER, ORG, LOC, or MISC.

#### Scenario: Entity type with valid label mapping

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "vendor_name", "base_label_mapping": {"ORG": ["vendor_name"]}}`
- **THEN** the response SHALL have status 201
- **AND** the entity type SHALL have `base_label_mapping: {"ORG": ["vendor_name"]}`

#### Scenario: Entity type with invalid base model label

- **GIVEN** an authenticated Tenant Admin
- **WHEN** they POST to `/api/v1/tenants/acme-corp/entity-types` with `{"name": "custom_type", "base_label_mapping": {"INVALID_LABEL": ["custom_type"]}}`
- **THEN** the response SHALL have status 422
- **AND** the error message SHALL indicate `INVALID_LABEL` is not a valid base model label

### Requirement: Entity Type Listing and Query

The system SHALL allow listing all active entity types for a tenant with optional filters by `is_active` status. The system SHALL return entity type details by ID or name. The system SHALL allow soft-deleting an entity type by setting `is_active: false`.

#### Scenario: Tenant Admin lists entity types

- **GIVEN** tenant "acme-corp" has 5 entity types (3 active, 2 inactive)
- **WHEN** the Tenant Admin GETs `/api/v1/tenants/acme-corp/entity-types`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an array of 5 entity type objects
- **AND** each object SHALL include `is_active` field

#### Scenario: Tenant Admin filters active entity types only

- **GIVEN** tenant "acme-corp" has 5 entity types (3 active, 2 inactive)
- **WHEN** the Tenant Admin GETs `/api/v1/tenants/acme-corp/entity-types?is_active=true`
- **THEN** the response SHALL contain exactly 3 entity type objects
- **AND** all returned objects SHALL have `is_active: true`
