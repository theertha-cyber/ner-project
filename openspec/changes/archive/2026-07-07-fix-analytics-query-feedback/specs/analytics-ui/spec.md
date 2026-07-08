# analytics-ui

## MODIFIED Requirements

### Requirement: Ad-Hoc Query Controls

The analytics page SHALL include filter controls (entity type dropdown, date range picker, confidence slider) that allow the user to run ad-hoc queries against the query API.

#### Scenario: Filter controls execute query and show results

- **GIVEN** a user on the analytics page
- **WHEN** they select entity types, set a date range, and click "Query"
- **THEN** a results table SHALL display below the controls showing matching entities
- **AND** a loading indicator SHALL be shown while the query is in flight
- **AND** if the query fails, an error banner SHALL be displayed instead of an empty results section

#### Scenario: Query with no results shows empty state

- **GIVEN** filters that return zero results
- **WHEN** the user clicks "Query"
- **THEN** a message "No matching entities found" SHALL be displayed

### Requirement: Error State Handling

The analytics page SHALL display user-friendly error messages if the dashboard or query API returns a non-2xx response.

#### Scenario: Dashboard API error shows error banner

- **GIVEN** the dashboard API returns HTTP 500
- **WHEN** the page loads
- **THEN** an error banner SHALL be displayed with message "Unable to load analytics data"
- **AND** a retry button SHALL be available

#### Scenario: Query API error shows error banner

- **GIVEN** the query API returns a non-2xx response
- **WHEN** the user clicks "Query"
- **THEN** an error banner SHALL be displayed with a message describing the failure
- **AND** the user SHALL be able to dismiss the banner and retry
