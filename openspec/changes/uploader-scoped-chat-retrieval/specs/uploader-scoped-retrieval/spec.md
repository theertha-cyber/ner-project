## ADDED Requirements

### Requirement: Uploader visibility is one rule, stated once

The system SHALL define exactly one uploader-visibility rule and SHALL apply it identically in document listing and in every chat answer channel: a document is visible to a requesting user when its ingesting actor is not a human, or when its ingesting actor is that user. A user whose role is `tenant_admin` SHALL be unscoped by this rule. The rule SHALL be expressed in one named place and referenced by each channel, never restated per channel, so that a channel added later cannot silently diverge.

#### Scenario: The rule admits the user's own human-ingested document

- **GIVEN** a `purpose='query'` document ingested by a human who is the requesting user
- **WHEN** the uploader-visibility rule is evaluated for that user
- **THEN** the document SHALL be visible

#### Scenario: The rule denies another user's human-ingested document

- **GIVEN** a `purpose='query'` document ingested by a human other than the requesting user
- **WHEN** the uploader-visibility rule is evaluated for that non-administrative user
- **THEN** the document SHALL NOT be visible

#### Scenario: The rule admits source-system content to every user

- **GIVEN** a `purpose='query'` document whose ingesting actor is a source system
- **WHEN** the uploader-visibility rule is evaluated for any non-administrative user of that tenant
- **THEN** the document SHALL be visible

#### Scenario: Administrators are unscoped

- **GIVEN** a requesting user whose role is `tenant_admin` and a document ingested by a different human
- **WHEN** the uploader-visibility rule is evaluated
- **THEN** the document SHALL be visible

#### Scenario: The rule has a single definition

- **GIVEN** the source of the document listing path and of every chat answer channel
- **WHEN** their uploader-visibility predicates are inspected
- **THEN** each SHALL derive from one shared definition
- **AND** no channel SHALL restate the predicate's literal condition independently

### Requirement: The requesting user is derived from authenticated state, never from input

The system SHALL derive the requesting user's identity and role for this rule from authenticated request state, and SHALL carry them to each answer channel as caller-supplied context. No LLM-generated argument, user-supplied tool argument, generated SQL statement, retrieval `metadata_filter`, or caller-supplied `scope` SHALL be able to name, widen, or disable the rule. A narrowing supplied by a caller MAY further restrict what is already visible.

#### Scenario: Tool argument schemas cannot name the requesting user

- **GIVEN** every tool in the retrieval tool registry
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** none SHALL name the requesting user, the uploading user, or the ingesting actor

#### Scenario: A tool argument cannot widen the rule

- **GIVEN** a tenant schema holding one document ingested by user A and one by user B, both matching a query
- **WHEN** a retrieval tool is invoked for user A with any argument values, including arguments naming user B's document
- **THEN** no result SHALL originate from user B's document

#### Scenario: A question phrased to request another user's documents does not widen the rule

- **GIVEN** a tenant schema holding a document ingested by another human
- **WHEN** a non-administrative user asks a question whose text names that document, its filename, or its content
- **THEN** the answer SHALL NOT draw on that document

### Requirement: Every chat answer channel enforces the rule

The system SHALL apply the uploader-visibility rule to every channel that can place a document's content, an entity extracted from it, or a count derived from it into a chat answer. This SHALL include semantic retrieval, the relational answer channel over the platform's own tenant schema, and entity resolution. A channel that cannot express the rule SHALL NOT answer from platform document data.

#### Scenario: Semantic retrieval is scoped

- **GIVEN** two non-administrative users in one tenant, each having uploaded a `purpose='query'` document matching the same query
- **WHEN** the first user asks that query
- **THEN** every returned chunk SHALL come from the first user's document
- **AND** no chunk SHALL come from the second user's document

#### Scenario: An aggregate over the relational channel is scoped

- **GIVEN** a tenant in which the requesting user ingested two documents and another human ingested three
- **WHEN** the requesting user asks a question answered by a `COUNT` over the platform's extracted-entity tables
- **THEN** the count SHALL reflect only the requesting user's documents and any source-system documents
- **AND** the restriction SHALL hold despite aggregation, `GROUP BY`, and any row limit

#### Scenario: Entity resolution is scoped

- **GIVEN** a person entity extracted only from a document another human ingested
- **WHEN** a non-administrative user's message mentions that person by name and entity resolution runs
- **THEN** no candidate SHALL be produced from that document
- **AND** the person's name SHALL NOT be presented to the user as a resolvable candidate

#### Scenario: Citations name only visible documents

- **GIVEN** a non-administrative user and a tenant containing documents ingested by another human
- **WHEN** an answer is produced and its citations are assembled
- **THEN** every citation SHALL name a document visible to that user under the rule

### Requirement: Listing and every answer channel agree in both directions

The system SHALL keep document listing and chat answering in agreement about what a user may see, in both directions. A document a user may list SHALL be answerable from; a document a user may not list SHALL NOT be citable, countable, or nameable in that user's answers.

#### Scenario: A listable document is answerable

- **GIVEN** a `purpose='query'` document whose ingesting actor is a source system, and a non-administrative user
- **WHEN** that user asks a question whose answer would cite that document
- **THEN** the document SHALL be citable
- **AND** the document SHALL also be listable by that user

#### Scenario: An unlistable document is unanswerable

- **GIVEN** a `purpose='query'` document ingested by a human other than the requesting non-administrative user
- **WHEN** that user asks a question whose content matches that document
- **THEN** the document SHALL NOT appear in the answer, its citations, or any count behind the answer
- **AND** the document SHALL also not be listable by that user

### Requirement: Conversation-owned attachments remain visible to their own uploader

The system SHALL continue to admit a conversation-owned chat attachment to the conversation it belongs to, for the user who attached it. The uploader-visibility rule SHALL compose with the conversation-visibility rule as a conjunction: both SHALL hold, and neither SHALL relax the other.

#### Scenario: A user's own attachment stays retrievable in its conversation

- **GIVEN** a non-administrative user who attached a file to a conversation and that file's chunks
- **WHEN** that user asks a question in that same conversation answerable from the attachment
- **THEN** the attachment's content SHALL be retrievable

#### Scenario: An attachment stays out of other conversations

- **GIVEN** the attachment from the preceding scenario
- **WHEN** the same user asks the same question in a different conversation
- **THEN** the attachment's content SHALL NOT be retrievable

### Requirement: An answer with no requesting user sees source-system content only

The system SHALL treat an answer produced without an authenticated end user — the embeddable widget channel, which answers under a tenant service identity — as having no requesting user, and SHALL admit only documents whose ingesting actor is not a human. Absence of a requesting user SHALL NOT be treated as an administrative identity and SHALL NOT disable the rule.

#### Scenario: The widget cannot answer from a human upload

- **GIVEN** a tenant whose only matching content is a `purpose='query'` document a human uploaded
- **WHEN** a question is asked through the embeddable widget channel
- **THEN** the answer SHALL NOT draw on that document
- **AND** the answer SHALL state that it has no supporting source rather than answering unsourced

#### Scenario: The widget answers from source-system content

- **GIVEN** a tenant holding a `purpose='query'` document whose ingesting actor is a source system
- **WHEN** a matching question is asked through the embeddable widget channel
- **THEN** the answer MAY draw on that document

#### Scenario: A missing requesting user does not widen the rule

- **GIVEN** an answer channel invoked with no requesting user identity
- **WHEN** the uploader-visibility rule is evaluated
- **THEN** every human-ingested document SHALL be excluded
- **AND** the evaluation SHALL NOT fall back to unscoped behaviour

### Requirement: Narrowing is observable without recording tenant content

The system SHALL record that an answer channel applied the uploader-visibility rule, using enumerated outcomes and counts only. No log record, span attribute, or metric label SHALL carry a user identifier as a metric label, a filename, a document's content, an entity value, or a generated statement.

#### Scenario: Narrowing is recorded as shape

- **GIVEN** a chat answer for a non-administrative user in a tenant holding other users' documents
- **WHEN** the answer is produced
- **THEN** the emitted telemetry SHALL identify the channel and an enumerated scoping outcome
- **AND** it SHALL NOT contain a filename, an entity value, a chunk of document text, or a generated SQL statement

#### Scenario: Metric labels are declared and finite

- **GIVEN** the metric family recording uploader scoping
- **WHEN** its declared label keys and value sets are inspected
- **THEN** each label's value set SHALL be finite and enumerated at declaration
- **AND** no label SHALL be a user identifier or a tenant identifier
