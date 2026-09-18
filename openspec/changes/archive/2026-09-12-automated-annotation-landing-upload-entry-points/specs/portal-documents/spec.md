## MODIFIED Requirements

### Requirement: Upload deep link

The Documents page SHALL recognize an `upload=1` query parameter on arrival and SHALL open the
upload dialog automatically, so a link from elsewhere in the portal (e.g. the Manual annotation
landing page's "Upload documents" workflow step, or the Automated landing page's own upload
entry points) lands the user on an open uploader rather than only the document list. An arrival
with no `upload` parameter, or any other value, SHALL leave the dialog closed.

Alongside `upload=1`, the page SHALL recognize an optional `purpose` parameter (`training` or
`qa_pair`) selecting which uploader opens, and an optional `mode` parameter (`manual` or
`automated`) seeding the annotation-mode selector's initial selection when `purpose=training`.
Omitting either parameter SHALL leave the corresponding setting at its existing default
(`training` purpose, Manual mode).

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

#### Scenario: purpose=qa_pair opens the Q&A-pair uploader

- **GIVEN** a Tenant Admin navigates to `/documents?upload=1&purpose=qa_pair`
- **WHEN** the page loads
- **THEN** the upload dialog SHALL be open in Q&A-pair mode

#### Scenario: mode=automated seeds the annotation-mode selector

- **GIVEN** a Tenant Admin navigates to `/documents?upload=1&purpose=training&mode=automated`
- **WHEN** the page loads
- **THEN** the upload dialog SHALL be open with "Automated" selected in the annotation-mode
  selector
