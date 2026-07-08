# query-error-feedback

## Purpose

Provides user-facing error display and retry behaviour for the analytics query flow, ensuring that API failures are surfaced as readable error banners instead of being silently swallowed.

## ADDED Requirements

### Requirement: Query Error Banner

When the analytics query API returns a non-2xx response or the request fails (network error, timeout, service unavailable), the analytics page SHALL display a user-friendly error banner.

#### Scenario: Query API returns HTTP 500 shows error banner

- **GIVEN** the analytics query API returns HTTP 500
- **WHEN** the user clicks "Query"
- **THEN** an error banner SHALL be displayed with a message indicating the query failed
- **AND** the user SHALL be able to dismiss the banner

#### Scenario: Query API is unreachable shows error banner

- **GIVEN** the analytics service is unavailable
- **WHEN** the user clicks "Query"
- **THEN** an error banner SHALL be displayed indicating the service is unavailable

#### Scenario: Query error banner disappears when user clicks Dismiss

- **GIVEN** a query error banner is visible
- **WHEN** the user clicks "Dismiss" on the banner
- **THEN** the banner SHALL be removed
- **AND** no other side effects SHALL occur

### Requirement: Query retry on error

After a query error, the user SHALL be able to click "Query" again to retry without page reload.

#### Scenario: Re-clicking Query after error retries the request

- **GIVEN** a previous query resulted in an error banner
- **WHEN** the user clicks "Query" again
- **THEN** a new API request SHALL be sent
- **AND** the error banner SHALL be cleared before the new request

### Requirement: Query Loading State

While a query request is in-flight, the Query button SHALL show a loading indicator and SHALL be disabled to prevent duplicate submissions.

#### Scenario: Loading state shown during query

- **GIVEN** a query request is in progress
- **WHEN** the user looks at the Query button
- **THEN** the button SHALL display a spinner
- **AND** the button SHALL be disabled

#### Scenario: Loading state clears on success or failure

- **GIVEN** a query request finishes (success or failure)
- **WHEN** the response is received
- **THEN** the loading indicator SHALL be removed
- **AND** the button SHALL be re-enabled
