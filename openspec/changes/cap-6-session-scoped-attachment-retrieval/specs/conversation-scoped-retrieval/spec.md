## ADDED Requirements

### Requirement: Conversation ownership determines retrieval visibility

Every retrievable chunk SHALL carry the conversation ownership of the document it was derived from. A chunk whose conversation ownership is absent SHALL be treated as tenant-library content and SHALL be retrievable from every conversation in that tenant. A chunk that is owned by a conversation SHALL be retrievable only while answering a turn in that same conversation.

#### Scenario: A conversation attachment is retrievable in its own conversation

- **GIVEN** a user has attached a job description to conversation A and the attachment has been indexed
- **WHEN** the user asks a question in conversation A whose answer depends on that job description
- **THEN** retrieval SHALL return chunks derived from that attachment
- **AND** the answer SHALL be able to cite them

#### Scenario: A conversation attachment is invisible in another conversation

- **GIVEN** a job description attached to conversation A and indexed, and a separate conversation B in the same tenant for the same user
- **WHEN** the user asks a question in conversation B whose text matches the job description's content
- **THEN** retrieval SHALL NOT return any chunk derived from conversation A's attachment
- **AND** the answer SHALL NOT cite that attachment

#### Scenario: Tenant-library documents remain visible in every conversation

- **GIVEN** a tenant library document with no conversation ownership, and two conversations A and B
- **WHEN** a matching question is asked in conversation A and the same question is asked in conversation B
- **THEN** retrieval SHALL return that document's chunks in both conversations

#### Scenario: A conversation attachment is invisible outside any conversation

- **GIVEN** a job description attached to conversation A and indexed
- **WHEN** retrieval runs in a context that names no conversation
- **THEN** retrieval SHALL NOT return any chunk owned by a conversation
- **AND** retrieval SHALL still return tenant-library chunks

### Requirement: Conversation scope is enforced from request context

The conversation used to evaluate retrieval visibility SHALL be taken from the authenticated request's conversation context. It SHALL NOT be derived from the user's message text, from a model-selected tool argument, or from any other caller-supplied retrieval parameter. No caller-supplied or model-supplied scope SHALL be able to widen the set of chunks the visibility rule admits.

#### Scenario: A model-chosen scope cannot widen conversation visibility

- **GIVEN** a job description owned by conversation A, and a turn being answered in conversation B
- **WHEN** the model invokes semantic retrieval with a scope naming conversation A's attachment document id
- **THEN** retrieval SHALL return no chunk from that document
- **AND** the scope argument SHALL narrow results only within what the visibility rule already admits

#### Scenario: User message text cannot widen conversation visibility

- **GIVEN** a job description owned by conversation A, and a turn being answered in conversation B
- **WHEN** the user's message names that job description, its filename, or its contents
- **THEN** retrieval SHALL still return no chunk owned by conversation A

#### Scenario: Conversation scope composes with the existing purpose restriction

- **GIVEN** a conversation-owned document whose chunks carry a purpose other than `query`
- **WHEN** retrieval runs in that same conversation
- **THEN** those chunks SHALL still be excluded by the purpose restriction
- **AND** the conversation visibility rule SHALL NOT weaken any existing retrieval restriction
