## MODIFIED Requirements

### Requirement: Post-processing confidence filtering

The system SHALL apply a configurable confidence threshold during extraction. Entities below the threshold SHALL be excluded from business-facing extraction results. The default threshold SHALL be 0.50.

The system SHALL retain predictions that fall below the threshold, together with their entity type, value, confidence, character offsets, and the model version that produced them, so they are available for confidence-based review routing.

Retained predictions SHALL be held in a routing store separate from the extraction store. No business-facing surface — extraction results, entity queries, the entity projection, analytics, or chat retrieval — SHALL read the routing store. Retaining a prediction SHALL NOT change what any business-facing surface returns for a document.

#### Scenario: Low-confidence entities are filtered out

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that entity SHALL NOT appear in the results

#### Scenario: Low-confidence entities are retained for routing

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that prediction SHALL be retained with its entity type, value, confidence, character offsets, and model version
- **AND** it SHALL be available to confidence-based review routing

#### Scenario: Retaining predictions does not change what business consumers see

- **GIVEN** an extraction run over a document, executed once with routing disabled and once with routing enabled
- **WHEN** a business consumer queries extracted entities for that document
- **THEN** both runs SHALL return the same entities
- **AND** no record from the routing store SHALL appear in either response
