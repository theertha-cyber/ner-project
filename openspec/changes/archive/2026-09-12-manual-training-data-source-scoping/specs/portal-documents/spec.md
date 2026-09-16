## ADDED Requirements

### Requirement: Upload deep link

The Documents page SHALL recognize an `upload=1` query parameter on arrival and SHALL open the
upload dialog automatically, so a link from elsewhere in the portal (e.g. the Manual annotation
landing page's "Upload documents" workflow step) lands the user on an open uploader rather than
only the document list. An arrival with no `upload` parameter, or any other value, SHALL leave
the dialog closed.

#### Scenario: Arriving with ?upload=1 opens the uploader

- **GIVEN** a Tenant Admin navigates to `/documents?upload=1`
- **WHEN** the page loads
- **THEN** the upload dialog SHALL be open

#### Scenario: Arriving with no upload parameter leaves the uploader closed

- **GIVEN** a Tenant Admin navigates to `/documents`
- **WHEN** the page loads
- **THEN** the upload dialog SHALL NOT be open

#### Scenario: An unrelated query parameter does not open the uploader

- **GIVEN** a Tenant Admin navigates to `/documents?status=processed`
- **WHEN** the page loads
- **THEN** the upload dialog SHALL NOT be open
