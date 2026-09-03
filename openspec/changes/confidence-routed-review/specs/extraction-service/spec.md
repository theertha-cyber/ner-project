## MODIFIED Requirements

### Requirement: Post-processing confidence filtering

The system SHALL apply a configurable confidence threshold during extraction. Entities below the threshold SHALL be excluded from business-facing extraction results. The default threshold SHALL be 0.50.

The system SHALL retain predictions that fall below the threshold, together with their entity type, value, confidence, character offsets, and the model version that produced them, so they are available for confidence-based review routing. Retained below-threshold predictions SHALL NOT appear in extraction results returned to business consumers, and SHALL NOT be included in entity queries, the entity projection, analytics, or chat retrieval.

#### Scenario: Low-confidence entities are filtered out

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that entity SHALL NOT appear in the results

#### Scenario: Low-confidence entities are retained for routing

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that prediction SHALL be retained with its entity type, value, confidence, character offsets, and model version
- **AND** it SHALL be available to confidence-based review routing

#### Scenario: Retained low-confidence predictions are not visible to business consumers

- **GIVEN** an extraction run that produced 3 entities above the threshold and 2 below it
- **WHEN** a business consumer queries extracted entities for that document
- **THEN** exactly 3 entities SHALL be returned
- **AND** neither retained below-threshold prediction SHALL appear in the response
