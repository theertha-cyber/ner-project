# Infrastructure

## Purpose

Defines behaviors of development/operations tooling — such as database seed and initialization scripts — that support running the platform's services reliably, independent of any single service's own spec.

---

## Requirements

### Requirement: Seed script idempotent for promoted model

The seed script SHALL skip inserting a promoted model version for `demo-tenant` if a row with `status = 'promoted'` already exists for that tenant.

#### Scenario: Re-run seed script skips existing promoted model

- **GIVEN** a database that already has a `model_versions` row with `status = 'promoted'` for `demo-tenant`
- **WHEN** the seed script runs again
- **THEN** the script does NOT insert a duplicate promoted model row
- **AND** the script exits 0 without raising an IntegrityError

#### Scenario: First run inserts promoted model

- **GIVEN** a database with no promoted model for `demo-tenant`
- **WHEN** the seed script runs
- **THEN** a row with `status = 'promoted'` is inserted for `demo-tenant`
