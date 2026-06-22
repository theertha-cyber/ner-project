## ADDED Requirements

### Requirement: Multi-Token Drag Span Creation

The annotation workspace SHALL support click-and-drag span creation across multiple tokens. When an entity type is armed, pressing the mouse button down on a token and releasing it on a different token SHALL create a span covering all tokens in the range (inclusive). The span's `char_start` SHALL be the `charStart` of the first token in the range and `char_end` SHALL be the `charEnd` of the last token. During the drag, all tokens in the current drag range SHALL show a live preview highlight using the armed entity type's color. A single mousedown-and-mouseup on the same token SHALL continue to behave as a single-token click (existing single-token span creation and inspector-open behaviors are preserved).

#### Scenario: Drag across tokens creates a multi-token span

- **GIVEN** the entity type "PER" is armed and the document text is "John Smith works here"
- **WHEN** the user presses the mouse button down on the token "John" and releases on the token "Smith"
- **THEN** a `POST /documents/{id}/spans` request SHALL be sent with `{entity_type: "PER", char_start: 0, char_end: 10, text: "John Smith"}`
- **AND** on success, tokens "John" and "Smith" SHALL be highlighted with the PER color (confirmed)

#### Scenario: Drag preview highlights range during drag

- **GIVEN** the entity type "ORG" is armed
- **WHEN** the user holds the mouse button down on token "Acme" and drags over token "Corp" without releasing
- **THEN** both "Acme" and "Corp" tokens SHALL show a drag-preview highlight in the ORG color
- **AND** no API request SHALL be sent until mouseup

#### Scenario: Single-click (same token mousedown and mouseup) still creates a single-token span

- **GIVEN** the entity type "ORG" is armed and the document token "Acme" is not yet spanned
- **WHEN** the user clicks the token "Acme" (mousedown and mouseup on the same token)
- **THEN** a `POST /documents/{id}/spans` request SHALL be sent with the single token's char range
- **AND** the behavior SHALL be identical to the pre-drag single-click span creation

#### Scenario: Drag while unarmed does not create a span

- **GIVEN** no entity type is armed
- **WHEN** the user drags across any tokens
- **THEN** no span creation request SHALL be sent
- **AND** no drag-preview highlight SHALL appear

#### Scenario: Drag ending on an already-confirmed token is blocked

- **GIVEN** the entity type "PER" is armed and the token "John" is already covered by a confirmed span
- **WHEN** the user drags a range that includes the token "John"
- **THEN** no span creation request SHALL be sent for that range
- **AND** the drag-preview highlight SHALL not apply to already-confirmed tokens

#### Scenario: Drag direction is agnostic (right-to-left = left-to-right)

- **GIVEN** the entity type "LOC" is armed
- **WHEN** the user presses down on token index 5 and releases on token index 2
- **THEN** the span SHALL cover tokens 2 through 5 (min-to-max, not start-to-end)
- **AND** `char_start` SHALL be the charStart of token 2 and `char_end` SHALL be the charEnd of token 5
