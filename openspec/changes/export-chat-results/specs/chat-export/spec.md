## ADDED Requirements

### Requirement: CSV export endpoint

The system SHALL expose `GET /api/v1/chat/messages/{message_id}/export?format=csv` for an authenticated user, returning the structured row snapshot captured for that assistant message as a downloadable CSV file. The endpoint SHALL only return data for messages belonging to a conversation owned by the requesting user within their tenant.

#### Scenario: Export returns valid CSV

- **GIVEN** an assistant message with a persisted row snapshot of 250 rows
- **WHEN** the owning user sends `GET /api/v1/chat/messages/{message_id}/export?format=csv`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL have `Content-Type: text/csv`
- **AND** the response SHALL include a `Content-Disposition` header with a filename
- **AND** the CSV body SHALL contain a header row followed by exactly 250 data rows matching the snapshot

#### Scenario: Export unavailable for a message with no structured result

- **GIVEN** an assistant message whose turn used only document/semantic sources (no structured retrieval)
- **WHEN** the owning user requests `GET /api/v1/chat/messages/{message_id}/export?format=csv`
- **THEN** the response SHALL have status 404

#### Scenario: Export rejects a request from a non-owning user

- **GIVEN** an assistant message in a conversation owned by user A
- **WHEN** user B requests `GET /api/v1/chat/messages/{message_id}/export?format=csv`
- **THEN** the response SHALL have status 404

#### Scenario: Export without authentication returns 401

- **GIVEN** no JWT token
- **WHEN** a GET request is sent to `/api/v1/chat/messages/{message_id}/export?format=csv`
- **THEN** the response SHALL have status 401

### Requirement: XLSX export endpoint

The system SHALL support `format=xlsx` on the same export endpoint, returning the row snapshot as a valid XLSX workbook with a single sheet containing a header row and one row per snapshot entry.

#### Scenario: Export returns valid XLSX

- **GIVEN** an assistant message with a persisted row snapshot of 40 rows
- **WHEN** the owning user sends `GET /api/v1/chat/messages/{message_id}/export?format=xlsx`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL have `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** the response body SHALL be a valid XLSX workbook whose first sheet has a header row and 40 data rows matching the snapshot

### Requirement: Export format validation

The export endpoint SHALL reject any `format` value other than `csv` or `xlsx` with HTTP 422.

#### Scenario: Unsupported format returns 422

- **GIVEN** an assistant message with a persisted row snapshot
- **WHEN** a request is sent with `format=pdf`
- **THEN** the response SHALL have status 422

### Requirement: Row snapshot persisted per structured turn

When a chat turn's structured retrieval source (SQL generation) matches **at least one row**, the system SHALL persist the full result set returned by SQL execution (`ChatState.sql_results`, capped at the SQL generator's 1000-row `LIMIT`) as an export snapshot keyed by the assistant message's `message_id` — not the token-budget-truncated subset (`AdmittedEvidence.rows`) used to build the LLM prompt. A query that ran and validated but matched zero rows (`sql_results == []`) offers nothing worth downloading and SHALL be treated the same as structured retrieval not having been used at all — **found during live testing**: a naive `sql_results is not None` check persists an empty, useless snapshot (and the portal briefly showed a "0 results" export card for it) whenever the SQL generator's LLM targets an empty or wrongly-named relation but still produces a validated, zero-row query; the check is `if sql_results:` (truthy — a non-empty list), not `is not None`.

#### Scenario: Snapshot captures the full SQL result, not the prompt-truncated subset

- **GIVEN** a SQL query that returns 250 rows to `ChatState.sql_results`
- **AND** the token-budget fitting step (`ContextAssembler._fit_rows`) admits only 40 of those rows into the LLM prompt
- **WHEN** the turn is persisted
- **THEN** the export snapshot for that message SHALL contain all 250 rows

#### Scenario: No snapshot is created when structured retrieval wasn't used

- **GIVEN** a chat turn answered entirely from document/semantic sources with no SQL execution
- **WHEN** the turn is persisted
- **THEN** no export snapshot SHALL be created for that message

#### Scenario: No snapshot is created when structured retrieval ran but matched zero rows

- **GIVEN** a chat turn whose SQL generation produced a query that validated and executed successfully, but matched no rows (`sql_results == []`) — e.g. because the query targeted an entity relation with no data for this tenant
- **WHEN** the turn is persisted
- **THEN** no export snapshot SHALL be created for that message
- **AND** the response's `export` field SHALL be omitted, exactly as if structured retrieval had not been used
- **AND** requesting export for that message SHALL return 404 per the CSV/XLSX export scenarios above
