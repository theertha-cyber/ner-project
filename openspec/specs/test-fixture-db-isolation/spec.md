# Test Fixture DB Isolation

## Purpose

<!-- TBD: This spec covers the guard that prevents test-fixture setup scripts (e.g. scripts/setup_test_db.py) from creating or mutating schema objects in a non-test database. -->

## Requirements

### Requirement: Fixture setup scripts refuse non-test databases

Scripts under `scripts/` that create or mutate schema objects for test fixtures — currently `scripts/setup_test_db.py` — SHALL resolve their target database name from the connection URL and SHALL refuse to execute any DDL or DML unless that name identifies a test database. A recognised test database name is one ending in `_test`. The script SHALL exit non-zero with a message naming the rejected database, and SHALL make no schema or data change before exiting.

#### Scenario: Script refuses to run against the development database

- **GIVEN** `NER_DATABASE_URL` points at the `ner_dev` database
- **WHEN** `python scripts/setup_test_db.py` is run
- **THEN** the script SHALL exit non-zero
- **AND** the message SHALL name `ner_dev` as the rejected target
- **AND** no table SHALL be created and no row SHALL be inserted in `ner_dev`

#### Scenario: Script runs against a test database

- **GIVEN** `NER_DATABASE_URL` points at the `ner_test` database
- **WHEN** `python scripts/setup_test_db.py` is run
- **THEN** the script SHALL create its fixture schemas, tables, and tenant rows as it does today
- **AND** it SHALL exit with code 0

#### Scenario: The guard reads the URL actually used, not the default

- **GIVEN** the script's hardcoded default URL points at a test database
- **AND** `NER_DATABASE_URL` is set to a non-test database
- **WHEN** the script is run
- **THEN** the guard SHALL evaluate the database named by `NER_DATABASE_URL`
- **AND** the script SHALL refuse to run

### Requirement: Explicit opt-in override for the fixture guard

The guard SHALL be overridable by an explicit environment variable set to an affirmative value, so that a deliberately non-standard test database name remains usable. The override SHALL be opt-in only — its absence SHALL never weaken the guard — and using it SHALL emit a warning naming the target database.

#### Scenario: Override permits a non-standard test database name

- **GIVEN** `NER_DATABASE_URL` points at a database named `ner_ci_scratch`
- **AND** the override environment variable is set to an affirmative value
- **WHEN** the script is run
- **THEN** the script SHALL proceed
- **AND** it SHALL emit a warning naming `ner_ci_scratch`

#### Scenario: Unset override leaves the guard in force

- **GIVEN** `NER_DATABASE_URL` points at `ner_dev`
- **AND** the override environment variable is unset
- **WHEN** the script is run
- **THEN** the script SHALL refuse to run
