## MODIFIED Requirements

### Requirement: Playground Tab — Real-time Extraction

The Playground tab SHALL render a two-column grid layout (`grid-template-columns: 1fr 1fr; gap: 18px`). The left column SHALL be a card containing: a "Input text" heading and a "model v{N} · serving" label (where N is the `model_version` from the last response, defaulting to the promoted version), a resizable textarea pre-populated with sample text, and a full-width "Run extraction" button. The right column SHALL be a card with an "Entities" heading and an entity summary label showing "N entities · M types".
When the user clicks "Run extraction", the system SHALL POST to `/api/v1/extract` with `{"text": <textarea value>}` and display the returned entities grouped by type. While the request is in-flight, a spinner SHALL appear inside the "Run extraction" button and an animated spinner SHALL appear in the results panel. The "Run extraction" button SHALL be disabled during the in-flight request. A hint below the button SHALL read "Whitespace-tokenized · POST /internal/v1/infer · mapped to char offsets. Not persisted."

**BIO merge:** The system SHALL merge consecutive B- and I- tagged tokens that share the same base entity type into a single entity. The B-/I- prefix SHALL be stripped from the displayed entity type. The merged entity's value SHALL be the joined token texts (space-separated). The confidence SHALL be the arithmetic mean of the individual token confidences.

**Grouped display:** Entities SHALL be displayed in alphabetical groups by entity type. Within each group, entities SHALL be ordered by ascending `start_offset` (i.e., order of appearance in the source text). Each group SHALL render a heading showing the entity type name (in uppercase), followed by the list of entities in that group.

#### Scenario: Running extraction displays results grouped by type

- **GIVEN** the Playground tab is active and text is entered in the textarea
- **WHEN** the user clicks "Run extraction"
- **THEN** the button SHALL show a spinner and be disabled
- **AND** a `POST /api/v1/extract` request SHALL be sent with `{"text": <textarea content>}`
- **AND** on success (200), entities SHALL be displayed grouped alphabetically by type
- **AND** each entity SHALL show: a colored dot, the cleaned entity type (without B-/I- prefix), the entity value, and the confidence score
- **AND** the entity summary label SHALL update to "N entities · M types"
- **AND** the button SHALL re-enable

#### Scenario: Multi-token entities are merged into a single row

- **GIVEN** the inference response returns `[{"token":"Steve","label":"B-PER","confidence":0.98}, {"token":"Jobs","label":"I-PER","confidence":0.97}]`
- **WHEN** the entities are displayed
- **THEN** a single row SHALL render under the "PERSON" group with value "Steve Jobs" and confidence 0.975

#### Scenario: Groups are ordered alphabetically

- **GIVEN** extracted entities of types "PERSON", "ORGANIZATION", and "LOCATION"
- **WHEN** the results panel renders
- **THEN** the "LOCATION" group SHALL appear first, followed by "ORGANIZATION", then "PERSON"

#### Scenario: Entities within a group are ordered by text position

- **GIVEN** a group contains entities at start_offset 10, 5, and 20
- **WHEN** the group renders
- **THEN** the entities SHALL appear in order: offset 5 → offset 10 → offset 20

#### Scenario: Playground shows spinner in results panel during in-flight request

- **GIVEN** a `POST /api/v1/extract` request is in-flight
- **WHEN** the results panel renders
- **THEN** an animated circular spinner SHALL appear centered in the results panel
- **AND** previous results (if any) SHALL NOT be shown during the in-flight state

#### Scenario: Playground shows model version from response

- **GIVEN** the extraction response includes `model_version: "3"`
- **WHEN** the result is displayed
- **THEN** the label in the input card header SHALL read "model v3 · serving"

#### Scenario: Empty textarea prevents submission

- **GIVEN** the textarea is empty
- **WHEN** the user clicks "Run extraction"
- **THEN** no API request SHALL be sent

### Requirement: Entity Review Tab — Entity Listing and Review

The Entity Review tab SHALL render a filter pill row followed by a grouped display of extracted entities. The filter pills SHALL be: "all", "unreviewed", "confirmed", "corrected", "rejected" — styled as compact labeled buttons. The active filter pill SHALL render with a filled background. Changing the filter SHALL re-fetch `GET /api/v1/entities` with the appropriate `reviewStatus` query parameter (omit for "all"). The entity count SHALL be displayed as "N entities · M types · GET /entities" in JetBrains Mono to the right of the filter pills. Entities SHALL be displayed in alphabetical groups by entity type. Each group SHALL render a heading showing the entity type name (uppercase, with BIO prefix stripped), followed by entity cards. Each entity card SHALL display: the entity value, confidence (colored by threshold — `var(--good)` ≥ 0.90, `var(--warn)` 0.70–0.89, `var(--bad)` < 0.70), review status pill, and confirm/reject action buttons for unreviewed entities.

#### Scenario: Entity Review tab loads entities with default filter

- **GIVEN** the user switches to the Entity Review tab
- **WHEN** the tab mounts
- **THEN** a `GET /api/v1/entities` request SHALL be sent with no `reviewStatus` filter
- **AND** all entities SHALL be displayed in alphabetical groups by type
- **AND** the "all" filter pill SHALL be active

#### Scenario: Changing filter re-fetches entities

- **GIVEN** the Entity Review tab is active showing all entities
- **WHEN** the user clicks the "unreviewed" filter pill
- **THEN** the "unreviewed" pill SHALL become the active filter
- **AND** a `GET /api/v1/entities?reviewStatus=unreviewed` request SHALL be sent
- **AND** the entity display SHALL update to show only unreviewed entities

#### Scenario: BIO prefix is stripped from entity type in display

- **GIVEN** an entity with `entity_id`: "B-ORG" and value "Acme Corp"
- **WHEN** the entity type group renders
- **THEN** the group heading SHALL read "ORG" (without the "B-" prefix)

#### Scenario: Confirming an entity updates its review status optimistically

- **GIVEN** an entity row with review_status "unreviewed"
- **WHEN** the user clicks the confirm button (✓) on that row
- **THEN** a `PATCH /api/v1/entities/{id}` request SHALL be sent with `{"review_status": "confirmed"}`
- **AND** the REVIEW status SHALL immediately update to "confirmed" (optimistic)
- **AND** the confirm and reject buttons SHALL be hidden or disabled for that row after confirmation

#### Scenario: Rejecting an entity updates its review status optimistically

- **GIVEN** an entity row with review_status "unreviewed"
- **WHEN** the user clicks the reject button (✗) on that row
- **THEN** a `PATCH /api/v1/entities/{id}` request SHALL be sent with `{"review_status": "rejected"}`
- **AND** the REVIEW status SHALL immediately update to "rejected" (optimistic)

#### Scenario: Confidence color coding reflects thresholds

- **GIVEN** three entities with confidences 0.94, 0.75, and 0.62
- **WHEN** the entity display renders
- **THEN** confidence 0.94 SHALL render in `var(--good)` (≥ 0.90)
- **AND** confidence 0.75 SHALL render in `var(--warn)` (0.70–0.89)
- **AND** confidence 0.62 SHALL render in `var(--bad)` (< 0.70)

#### Scenario: Empty entity list shows empty state

- **GIVEN** no entities exist for the current filter
- **WHEN** the entity display renders
- **THEN** the display SHALL show an empty state message instead of groups
