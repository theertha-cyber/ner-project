## ADDED Requirements

### Requirement: Analytics Dashboard Page

The portal SHALL provide an analytics dashboard page at `/tenants/{tenant_id}/analytics` that displays the four pre-built widgets from the dashboard API.

#### Scenario: Dashboard page loads widgets

- **GIVEN** a logged-in tenant user with permission to view analytics
- **WHEN** they navigate to `/tenants/{tenant_id}/analytics`
- **THEN** the page SHALL display the entity coverage, confidence distribution, extraction volume, and per-document entity counts widgets
- **AND** each widget SHALL show data fetched from the dashboard API

#### Scenario: Dashboard page handles empty data gracefully

- **GIVEN** a tenant with no extracted entities
- **WHEN** they navigate to the analytics page
- **THEN** the widgets SHALL display empty state messages (e.g., "No extraction data yet")
- **AND** no errors SHALL be shown to the user

### Requirement: Dashboard Page Loading State

The analytics page SHALL show a loading skeleton or spinner while data is being fetched.

#### Scenario: Loading state displayed during fetch

- **GIVEN** the dashboard API has not yet responded
- **WHEN** the analytics page is loading
- **THEN** a loading indicator SHALL be visible for each widget area

### Requirement: Ad-Hoc Query Controls

The analytics page SHALL include filter controls (entity type dropdown, date range picker, confidence slider) that allow the user to run ad-hoc queries against the query API.

#### Scenario: Filter controls execute query

- **GIVEN** a user on the analytics page
- **WHEN** they select entity types, set a date range, and click "Query"
- **THEN** a results table SHALL display below the controls showing matching entities
- **AND** pagination controls SHALL be shown if results exceed one page

#### Scenario: Query with no results shows empty state

- **GIVEN** filters that return zero results
- **WHEN** the user clicks "Query"
- **THEN** a message "No matching entities found" SHALL be displayed

### Requirement: Export Button

The analytics page SHALL include export buttons (CSV and JSON) that trigger the export API and download the resulting file.

#### Scenario: CSV export downloads file

- **GIVEN** the user has applied filters
- **WHEN** they click "Export CSV"
- **THEN** a CSV file SHALL be downloaded with the filtered entity data

#### Scenario: JSON export downloads file

- **GIVEN** the user has applied filters
- **WHEN** they click "Export JSON"
- **THEN** a JSON file SHALL be downloaded with the filtered entity data

### Requirement: Error State Handling

The analytics page SHALL display user-friendly error messages if the dashboard or query API returns a non-2xx response.

#### Scenario: API error shows error banner

- **GIVEN** the dashboard API returns HTTP 500
- **WHEN** the page loads
- **THEN** an error banner SHALL be displayed with message "Unable to load analytics data"
- **AND** a retry button SHALL be available
