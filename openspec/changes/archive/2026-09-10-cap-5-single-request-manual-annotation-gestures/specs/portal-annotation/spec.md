## MODIFIED Requirements

### Requirement: Token-Click Span Creation

When an entity type is armed, clicking any document token SHALL create a single-token confirmed span via `POST /api/v1/documents/{id}/spans`. The span's `char_start` and `char_end` SHALL be derived from the token's position in the document text using whitespace-split tokenization. Span creation SHALL be optimistic — the token SHALL highlight immediately without waiting for the API response. If the API returns an error, the optimistic highlight SHALL be reverted and a toast SHALL display the error. A token click followed by the document mouseup event for the same gesture SHALL still issue at most one create-span request.

#### Scenario: Clicking a token while armed creates a span

- **GIVEN** the entity type "ORG" is armed and the document text is "Acme Corp hired John"
- **WHEN** the user clicks the token "Acme" and the document mouseup for that click is dispatched
- **THEN** the "Acme" token SHALL immediately highlight with the ORG color (optimistic)
- **AND** exactly one `POST /documents/{id}/spans` request SHALL be sent with `{entity_type: "ORG", char_start: 0, char_end: 4, text: "Acme"}`
- **AND** on success (201), the span ID from the response SHALL replace the optimistic placeholder

#### Scenario: Clicking an already-spanned token while armed does nothing

- **GIVEN** the entity type "PER" is armed and the token "John" is already covered by a confirmed "ORG" span
- **WHEN** the user clicks "John"
- **THEN** no span creation request SHALL be sent
- **AND** the token color SHALL remain the existing ORG color

#### Scenario: API error reverts optimistic span

- **GIVEN** "ORG" is armed and the user clicks a token
- **WHEN** the `POST /documents/{id}/spans` request returns a 4xx or 5xx error
- **THEN** the optimistic token highlight SHALL be removed
- **AND** a toast SHALL display the error message

#### Scenario: Clicking a token while no type is armed opens the span inspector

- **GIVEN** no entity type is armed and the user clicks a token that belongs to a confirmed span
- **WHEN** the token is clicked
- **THEN** the span inspector SHALL open for that span
