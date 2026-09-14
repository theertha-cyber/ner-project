## MODIFIED Requirements

### Requirement: Guardrail — query complexity limits

The system SHALL assess the number of distinct source lookups a question requires and SHALL log the complexity score for every question. When agentic retrieval is disabled, the system SHALL reject questions requiring more than 3 distinct source lookups, responding with a message asking the user to simplify the question. When agentic retrieval is enabled, the system SHALL NOT decline on complexity alone: the question SHALL be answered through the bounded agentic retrieval loop, and the complexity score SHALL raise the loop's iteration budget. Rejection of blocked question types (classification, content generation, summarization, cross-tenant, PII) is unaffected by this requirement and SHALL continue to short-circuit before any retrieval.

#### Scenario: Overly complex question is simplified when the loop is disabled

- **GIVEN** `chat_agentic_retrieval` is disabled and a multi-hop question requiring 4 source lookups
- **WHEN** the complexity guardrail evaluates it
- **THEN** the response SHALL ask the user to simplify the question
- **AND** the complexity score SHALL be logged

#### Scenario: Overly complex question is answered when the loop is enabled

- **GIVEN** `chat_agentic_retrieval` is enabled and a multi-hop question requiring 4 source lookups
- **WHEN** the complexity guardrail evaluates it
- **THEN** the turn SHALL proceed into the agentic retrieval loop
- **AND** the response SHALL have status 200 with a reply and citations
- **AND** the complexity score SHALL be logged
- **AND** the loop SHALL run under the raised iteration budget

#### Scenario: Blocked question type is still declined with the loop enabled

- **GIVEN** `chat_agentic_retrieval` is enabled and a message matching a blocked question type
- **WHEN** the guardrail evaluates it
- **THEN** the response SHALL contain the existing decline message for that type
- **AND** the response `sources` array SHALL be empty
- **AND** no planner or retrieval call SHALL be made
