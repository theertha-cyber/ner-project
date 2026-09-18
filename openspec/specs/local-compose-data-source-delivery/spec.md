# local-compose-data-source-delivery Specification

## Purpose
TBD - created by archiving change cap-6-local-compose-delivery-migration-and-operational-evidence. Update Purpose after archive.
## Requirements
### Requirement: Compatible local rolling delivery

The system SHALL deploy changed services and workers sequentially in local Docker Compose only after compatible additive migrations and readiness checks, retaining the prior compatible component until its replacement is healthy.

#### Scenario: Local rolling deployment succeeds

- **GIVEN** the approved dev Compose stack with data-source revisions 040, 041, and 042 applied in chain order behind a single head
- **WHEN** the approved dev deployment is performed
- **THEN** migrations SHALL complete before dependent services/workers are replaced and each replacement SHALL report ready before the next replacement starts.

#### Scenario: Additive migration compatibility holds

- **GIVEN** Alembic revisions 040 (connection control plane), 041 (Blob sync ledger), and 042 (schema contracts) in a single linear chain
- **WHEN** the migration chain is inspected
- **THEN** no revision SHALL drop or destructively alter a table or column created by an earlier revision, and `db-init` SHALL complete `alembic upgrade head` idempotently on an initialized database.

### Requirement: Safe operational verification and recovery

The system SHALL provide local health/readiness and declared safe aggregate telemetry for connection, sync, drift-block, and external-query terminal outcomes, and SHALL document a compatible roll-back or roll-forward recovery path.

#### Scenario: Local recovery is exercised

- **GIVEN** the documented compatible rollback or corrective roll-forward procedure
- **WHEN** a failed local deployment is restored using that procedure
- **THEN** the Compose stack SHALL return to a runnable, health-checked state within 30 minutes without assuming destructive database rollback.

#### Scenario: Operational telemetry is safe and declared

- **GIVEN** the running dev stack after local delivery
- **WHEN** connection, sync, drift-block, and external-query terminal outcomes are emitted
- **THEN** every such outcome SHALL be recorded with declared finite metric labels and structured correlation metadata only, with no tenant content, credentials, SQL, prompts, answers, provider errors, or raw exceptions in logs, spans, metric labels, or audit payloads.

