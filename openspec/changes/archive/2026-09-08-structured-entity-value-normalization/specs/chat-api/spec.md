## ADDED Requirements

### Requirement: Structured entity value columns are queryable through the SQL path

The system SHALL include the `document_entities` semantic value columns — `value_kind`, `value_number`, `value_number_high`, `value_unit`, `value_date`, and `value_date_high` — in the SQL generation whitelist so that generated queries MAY filter, compare, sort, and aggregate on them. The schema description supplied to the SQL generator SHALL state that comparison and range predicates belong on the typed columns and that equality matching on entity text belongs on `normalized_value`. All existing validation rules — SELECT only, whitelisted tables, enforced LIMIT, no UNION, no non-whitelisted subqueries or JOINs, read-only transaction, 10-second timeout — SHALL remain unchanged.

#### Scenario: Numeric comparison query passes validation

- **GIVEN** a natural language question asking for candidates with more than two years of experience
- **WHEN** the SQL generation produces `SELECT d.filename AS document_name, e.value_number FROM document_entities e JOIN documents d ON d.id = e.document_id WHERE e.entity_type = 'YEARS_OF_EXP' AND e.value_number > 2 LIMIT 100`
- **THEN** the validation layer SHALL pass the query
- **AND** the query SHALL be executed in a read-only transaction

#### Scenario: Date comparison query passes validation

- **GIVEN** a question asking which certifications have expired
- **WHEN** the SQL generation produces a query filtering `entity_type = 'CERTIFICATION_EXPIRY' AND value_date < CURRENT_DATE`
- **THEN** the validation layer SHALL pass the query

#### Scenario: Non-whitelisted column is still rejected

- **GIVEN** a generated query referencing a `document_entities` column that is not in the whitelist
- **WHEN** the validation layer inspects the query
- **THEN** the validation SHALL reject the query

#### Scenario: Text-only queries continue to work

- **GIVEN** a question asking which documents mention AWS
- **WHEN** the SQL generation produces a query filtering `normalized_value = 'aws'`
- **THEN** the validation layer SHALL pass the query
- **AND** the behaviour SHALL be identical to before this change
