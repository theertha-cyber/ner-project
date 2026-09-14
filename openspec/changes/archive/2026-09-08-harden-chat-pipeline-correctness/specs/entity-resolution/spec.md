# entity-resolution

## ADDED Requirements

### Requirement: Multi-subject resolution scopes to every matched document

Entity resolution SHALL evaluate every distinct mention in the message, not only the first mention that matches. When two or more distinct mentions each resolve to one or more documents, the resolution outcome SHALL carry the **union** of those documents, and the retrieval plan SHALL be scoped to that union. Resolution SHALL NOT narrow a multi-subject question to a single document, and SHALL NOT drop a subject because another mention matched first in n-gram ordering.

#### Scenario: Two named subjects both resolve

- **GIVEN** a tenant with a person entity for "Girish" in document D1 and for "Arjun Jayakumar" in document D2
- **WHEN** the user asks "Compare Girish and Arjun Jayakumar"
- **THEN** the resolution outcome SHALL carry both D1 and D2
- **AND** the semantic capability's scope SHALL contain both document identifiers
- **AND** the structured capability's document constraint SHALL contain both document identifiers

#### Scenario: One named subject resolves and another does not

- **GIVEN** a tenant with a person entity for "Girish" in document D1
- **AND** no person entity matching "Hannah"
- **WHEN** the user asks "Compare Hannah and Girish"
- **THEN** the resolution outcome SHALL NOT be treated as a unique single-document match that excludes the unmatched subject
- **AND** retrieval for the turn SHALL still be able to surface evidence for the unmatched subject
- **AND** the turn SHALL NOT produce a prompt containing evidence for only one of the two named subjects

#### Scenario: Single named subject still resolves uniquely

- **GIVEN** a tenant with exactly one person entity matching "Girish", in document D1
- **WHEN** the user asks "Tell me about Girish"
- **THEN** the resolution outcome SHALL carry exactly D1
- **AND** the plan SHALL be scoped to D1
- **AND** the behaviour SHALL be unchanged from the single-subject behaviour that preceded this requirement

#### Scenario: Ambiguity within one mention still requests clarification

- **GIVEN** a tenant with two distinct people whose stored names both match the mention "Girish"
- **WHEN** the user asks "Tell me about Girish"
- **THEN** the system SHALL return the existing clarification reply listing the candidates
- **AND** the turn SHALL terminate without retrieval

#### Scenario: Union above the candidate cap falls back to narrowing

- **GIVEN** a message whose distinct mentions resolve to more documents than `entity_resolution_max_candidates`
- **WHEN** resolution completes
- **THEN** the system SHALL return the existing narrowing reply
- **AND** the turn SHALL NOT be scoped to an arbitrary subset

#### Scenario: Single-character mentions do not contribute to the union

- **GIVEN** a stored person name whose word list contains a single-character token
- **AND** a message containing that single character as a standalone word but naming no person
- **WHEN** resolution evaluates mentions
- **THEN** that mention SHALL NOT contribute a document to the union
- **AND** the resolution outcome SHALL be unresolved if no other mention matches

### Requirement: Plan rewriting preserves every resolved document

Plan rewriting for a resolved turn SHALL accept a set of document identifiers and SHALL apply that whole set to every affected capability entry. Rewriting SHALL NOT accept or silently reduce to a single identifier.

#### Scenario: Semantic scope receives the full set

- **GIVEN** a resolution outcome carrying documents D1 and D2
- **WHEN** the plan is rewritten
- **THEN** every `semantic_retrieval` entry's scope SHALL list both D1 and D2

#### Scenario: Structured constraint receives the full set

- **GIVEN** a resolution outcome carrying documents D1 and D2
- **WHEN** the plan is rewritten
- **THEN** every `structured_retrieval` entry SHALL be constrained to both D1 and D2

#### Scenario: Post-execution row filter respects the full set

- **GIVEN** a resolution outcome carrying documents D1 and D2
- **AND** structured retrieval returned rows from both
- **WHEN** the resolved-document filter is applied to the returned rows
- **THEN** rows from both D1 and D2 SHALL be retained

#### Scenario: Anaphoric follow-up inherits the full bound set

- **GIVEN** a prior turn resolved to documents D1 and D2
- **AND** a follow-up message containing an anaphoric reference and no new mention
- **WHEN** resolution runs for the follow-up
- **THEN** the plan SHALL be scoped to both D1 and D2
