## ADDED Requirements

### Requirement: Import Deep Link

The `/imported-documents` page SHALL recognize an `import=1` query parameter on arrival and, for
`tenant_admin`, SHALL open the file picker automatically — the same picker the page's own
"Import file" button opens — so a link from elsewhere in the portal (e.g. the Import annotation
landing page's "1. Import file" workflow step) lands the user ready to pick a file rather than
only the imported-files list. An arrival with no `import` parameter, any other value, or a role
that cannot import SHALL leave the picker closed.

#### Scenario: Arriving with ?import=1 opens the file picker

- **GIVEN** a Tenant Admin navigates to `/imported-documents?import=1`
- **WHEN** the page loads
- **THEN** the file picker SHALL open

#### Scenario: Arriving with no import parameter leaves the picker closed

- **GIVEN** a Tenant Admin navigates to `/imported-documents`
- **WHEN** the page loads
- **THEN** the file picker SHALL NOT open

#### Scenario: A role that cannot import does not get the picker opened for it

- **GIVEN** an `annotator` navigates to `/imported-documents?import=1`
- **WHEN** the page loads
- **THEN** the file picker SHALL NOT open
