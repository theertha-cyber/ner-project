## ADDED Requirements

### Requirement: The requesting user reaches every answer channel as execution state

The chat API SHALL pass the authenticated user's identity and role from request state into the orchestration flow as per-request execution state, and SHALL make them available to semantic retrieval, the relational answer channel, and entity resolution. They SHALL NOT be stored on a shared service instance, consistent with "Per-request authorization context isolation". Both the JSON and the streaming chat routes SHALL supply them.

#### Scenario: The streaming route scopes identically to the JSON route

- **GIVEN** a tenant holding a `purpose='query'` document ingested by a human other than the requesting user
- **WHEN** the same question is asked once through the JSON chat route and once through the streaming route
- **THEN** neither answer SHALL draw on that document

#### Scenario: Interleaved users do not leak scope

- **GIVEN** requests from two non-administrative users of one tenant executing concurrently in one process
- **WHEN** each request reaches retrieval
- **THEN** each SHALL apply the uploader-visibility rule for its own user
- **AND** no orchestrator attribute SHALL have been assigned either user's identity

### Requirement: The relational answer channel is uploader-scoped

The chat API SHALL constrain every generated statement over the platform's own tenant schema to documents visible to the requesting user under the uploader-visibility rule. The constraint SHALL be applied to every statement, not only to statements the caller asked to scope, and SHALL be applied by rewriting the statement's relation references so that it survives aggregation, `GROUP BY`, sub-selects and any row limit. The constraint SHALL be applied in addition to, and SHALL NOT replace, the conversation scope. A whitelisted relation the constraint cannot reach SHALL be treated as a defect rather than answered tenant-wide.

#### Scenario: A row-returning statement excludes another user's documents

- **GIVEN** a tenant in which the requesting user and another human have each ingested documents with extracted entities matching a question
- **WHEN** the relational channel answers that question for the requesting user
- **THEN** every returned row SHALL derive from the requesting user's documents or from source-system documents

#### Scenario: An aggregate is scoped before aggregation

- **GIVEN** the tenant from the preceding scenario
- **WHEN** the generated statement is a `COUNT` with no projected document identifier
- **THEN** the count SHALL exclude the other human's documents
- **AND** the exclusion SHALL NOT depend on filtering rows after execution

#### Scenario: A row limit does not defeat the scope

- **GIVEN** a tenant whose other-user documents would rank ahead of the requesting user's under the generated ordering
- **WHEN** the statement carries a trailing row limit
- **THEN** the limited result SHALL still contain only visible rows
- **AND** the result SHALL NOT be empty merely because invisible rows consumed the limit

#### Scenario: Every scopeable relation is reached

- **GIVEN** the set of relations the generator may reference over the platform's own tenant schema
- **WHEN** the uploader scope is applied to a statement referencing each of them
- **THEN** every such reference SHALL be rewritten
- **AND** a relation the scope cannot reach SHALL cause the statement to be rejected rather than executed

#### Scenario: Uploader and conversation scopes compose

- **GIVEN** a statement over a relation reachable by both scopes
- **WHEN** the statement is prepared for execution
- **THEN** both constraints SHALL be present
- **AND** neither SHALL have replaced the other

### Requirement: Entity resolution is uploader-scoped

The chat API SHALL restrict the extracted-entity reads behind person-entity resolution to documents visible to the requesting user under the uploader-visibility rule, so that a name extracted only from another user's document is never offered as a candidate, presented in a disambiguation prompt, or persisted as a resolved selection.

#### Scenario: Another user's person is not a candidate

- **GIVEN** a person entity extracted only from a document another human ingested
- **WHEN** a non-administrative user's message mentions that person by name
- **THEN** resolution SHALL produce no candidate for that person

#### Scenario: A disambiguation prompt names only visible people

- **GIVEN** two people sharing a first name, one extracted from the requesting user's document and one from another human's
- **WHEN** the requesting user's message mentions that shared first name
- **THEN** any disambiguation offered SHALL name only the person from the requesting user's document

#### Scenario: The user's own people still resolve

- **GIVEN** a person entity extracted from a document the requesting user ingested
- **WHEN** that user's message mentions that person by name
- **THEN** resolution SHALL produce that candidate as it did before this change

### Requirement: Entity resolution is conversation-scoped

The chat API SHALL additionally restrict the extracted-entity reads behind person-entity resolution to content the current conversation may see, applying ADR-014's conversation-visibility rule conjoined with the uploader rule so that neither relaxes the other. This path reads `document_entities` outside both the `Retriever` implementations and the generated-SQL scope rewrite, and was therefore not covered by ADR-014's channel enumeration.

#### Scenario: An attachment's person resolves inside its own conversation

- **GIVEN** a person entity extracted from a file attached to one conversation
- **WHEN** the user who attached it mentions that person in that same conversation
- **THEN** resolution SHALL produce that candidate

#### Scenario: An attachment's person does not resolve in another conversation

- **GIVEN** the person from the preceding scenario
- **WHEN** the same user mentions that person in a different conversation
- **THEN** resolution SHALL produce no candidate from the attached document

#### Scenario: Tenant-library people stay resolvable from inside a conversation

- **GIVEN** a person entity extracted from a document owned by no conversation
- **WHEN** that document's uploader mentions the person from inside any conversation
- **THEN** resolution SHALL produce that candidate

#### Scenario: Both rules apply together

- **GIVEN** a conversation whose user has an attachment, a library document of their own, a source-system document, and a colleague's library document, each holding a person sharing one first name
- **WHEN** that user mentions the shared first name inside that conversation
- **THEN** resolution SHALL produce candidates from their own attachment, their own library document, and the source-system document
- **AND** SHALL produce no candidate from the colleague's document
