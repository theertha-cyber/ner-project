## ADDED Requirements

### Requirement: Entity resolution precedes retrieval execution

The system SHALL resolve person-entity references in a chat message against the tenant's `document_entities` store before any retrieval capability is executed, and SHALL return a structured resolution outcome rather than performing retrieval itself. Resolution SHALL run after the retrieval plan is produced and before the plan is executed, so that the plan can be rewritten with a resolved document scope. Resolution SHALL be scoped to the requesting tenant's schema, taken from authenticated request state and never from a model-supplied argument.

#### Scenario: Resolution runs before any tool invocation

- **GIVEN** entity resolution is enabled and a message referencing a person present in `document_entities`
- **WHEN** the chat turn runs
- **THEN** the resolver SHALL query `document_entities` before `semantic_retrieval` or `structured_retrieval` is invoked
- **AND** the resolution outcome SHALL be recorded in graph state

#### Scenario: Resolution queries are tenant-scoped

- **GIVEN** two tenant schemas each containing a person entity with the same normalized value
- **WHEN** a user of tenant A asks about that person
- **THEN** every resolver query SHALL be issued against tenant A's schema
- **AND** no candidate from tenant B's schema SHALL appear in the outcome

### Requirement: Deterministic mention extraction and matching

The resolver SHALL extract candidate mentions from the user message by generating contiguous 1-word, 2-word, and 3-word n-grams, canonicalizing each with the same canonicalization used when `document_entities.normalized_value` was written, and matching them against `normalized_value` for person-typed entities only. Matching SHALL be exact on the canonicalized form; no fuzzy, phonetic, or edit-distance matching SHALL be performed. When several overlapping n-grams match, the longest matching n-gram SHALL be used. Mention extraction SHALL NOT issue an LLM call.

#### Scenario: Name is matched through shared canonicalization

- **GIVEN** a `document_entities` row with `normalized_value` produced by canonicalizing "Sreelakshmi R"
- **WHEN** a user asks "Tell me about  SREELAKSHMI  R."
- **THEN** the mention SHALL match that row

#### Scenario: Longest matching mention wins

- **GIVEN** person entities normalized as "sreelakshmi" in one document and "sreelakshmi r" in another
- **WHEN** a user asks "Tell me about Sreelakshmi R"
- **THEN** the resolver SHALL use the "sreelakshmi r" mention
- **AND** SHALL NOT additionally resolve the shorter overlapping mention

#### Scenario: Non-person entity types are not matched

- **GIVEN** an organization entity whose normalized value equals a word in the user's message
- **WHEN** mention extraction runs
- **THEN** that entity SHALL NOT produce a candidate

#### Scenario: Extraction makes no LLM call

- **GIVEN** a message containing a person reference
- **WHEN** mention extraction and matching run
- **THEN** no chat-completion request SHALL be issued by the resolver during extraction or matching

### Requirement: Zero, one, and many resolution outcomes

The resolver SHALL group matched entity rows by `document_id` and SHALL classify the outcome by the number of distinct documents: zero documents is `unresolved`, exactly one document is `unique`, and two or more documents is `ambiguous`. Multiple matching rows within a single document SHALL collapse into one candidate.

#### Scenario: No match leaves the existing strategy untouched

- **GIVEN** a message whose mentions match no person entity
- **WHEN** the resolver runs
- **THEN** the outcome SHALL be `unresolved`
- **AND** the retrieval plan SHALL be executed unmodified
- **AND** the reply SHALL be produced exactly as it is with entity resolution disabled

#### Scenario: Single match proceeds directly into scoped retrieval

- **GIVEN** a message whose mention matches person entities in exactly one document
- **WHEN** the resolver runs
- **THEN** the outcome SHALL be `unique`
- **AND** retrieval SHALL execute in the same turn constrained to that document
- **AND** no clarification SHALL be requested

#### Scenario: Repeated name within one document is one candidate

- **GIVEN** a single resume containing eleven rows for the same person name
- **WHEN** the resolver runs
- **THEN** the outcome SHALL be `unique`

#### Scenario: Multiple documents produce an ambiguous outcome

- **GIVEN** three documents each containing a person entity matching the mention
- **WHEN** the resolver runs
- **THEN** the outcome SHALL be `ambiguous`
- **AND** the outcome SHALL carry one candidate per distinct `document_id`

### Requirement: Ambiguity pauses the turn and requests clarification

On an `ambiguous` outcome the system SHALL NOT execute any retrieval capability and SHALL NOT invoke the generation model for that turn. The turn SHALL terminate with a clarification reply that names the ambiguous reference, lists the candidates in a stable order, and asks the user which one was meant. The reply SHALL be assembled deterministically from candidate data and SHALL NOT be produced by an LLM.

#### Scenario: Clarification turn skips retrieval and generation

- **GIVEN** an ambiguous mention
- **WHEN** the chat turn runs
- **THEN** no `semantic_retrieval` or `structured_retrieval` invocation SHALL occur
- **AND** no generation model call SHALL be made
- **AND** the response SHALL have status 200 with an empty `sources` array

#### Scenario: Clarification names the reference and lists candidates

- **GIVEN** three candidates for the mention "Sreelakshmi"
- **WHEN** the clarification reply is assembled
- **THEN** the reply SHALL state that multiple candidates named "Sreelakshmi" were found
- **AND** SHALL list all three candidates with a stable 1-based index

#### Scenario: Candidate count above the cap declines to list

- **GIVEN** more candidates than `entity_resolution_max_candidates`
- **WHEN** the resolver runs
- **THEN** no candidate list SHALL be printed
- **AND** the reply SHALL ask the user to narrow the reference
- **AND** no pending clarification SHALL be stored

### Requirement: Candidate presentation with minimal distinguishing metadata

Each candidate card SHALL be assembled from that candidate document's own `document_entities` rows and SHALL present, in order, the candidate name, current organization, years of experience, and up to three skills. A field with no backing entity row SHALL be omitted rather than rendered empty. When two or more rendered cards in the same set are identical, `documents.filename` SHALL be appended to every card in that set. Card content SHALL be drawn from stored entity values and SHALL NOT be paraphrased or generated by an LLM.

#### Scenario: Card shows only the fields that exist

- **GIVEN** a candidate document with a person entity and an organization entity but no experience or skill entities
- **WHEN** the card is assembled
- **THEN** the card SHALL show the name and the organization
- **AND** SHALL NOT contain an empty experience or skills field

#### Scenario: Skills are capped

- **GIVEN** a candidate document with nine distinct skill entities
- **WHEN** the card is assembled
- **THEN** at most three skills SHALL be shown

#### Scenario: Identical cards fall back to filenames

- **GIVEN** two candidate documents whose cards render identically
- **WHEN** the clarification reply is assembled
- **THEN** the source filename SHALL be appended to both cards

#### Scenario: Card values come from the entity store

- **GIVEN** a candidate whose stored organization value is "SEO Technologies"
- **WHEN** the card is assembled
- **THEN** the card SHALL contain that value verbatim

### Requirement: Pending clarification state is persisted per conversation

When a clarification is requested the system SHALL persist, keyed by conversation, the original user message and the ordered candidate list, in tenant-schema storage. The stored state SHALL be readable by a subsequent request handled by any service replica. At most one pending clarification SHALL exist per conversation; a new clarification SHALL replace any existing one.

#### Scenario: Pending state survives across requests

- **GIVEN** a clarification requested in one HTTP request
- **WHEN** the next message for that conversation is handled by a different process
- **THEN** the pending original message and candidate list SHALL be readable

#### Scenario: Pending state is tenant-scoped

- **GIVEN** a pending clarification in tenant A
- **WHEN** any conversation in tenant B is processed
- **THEN** tenant A's pending state SHALL NOT be visible to it

#### Scenario: A new clarification replaces the previous one

- **GIVEN** a conversation with a pending clarification for one mention
- **WHEN** a second ambiguous mention triggers a new clarification
- **THEN** exactly one pending clarification SHALL remain stored for that conversation

### Requirement: Natural-language selection interpretation

When a pending clarification exists, the next user message SHALL be interpreted as a selection. An ordinal or index reference SHALL be resolved deterministically without an LLM call. Any other answer SHALL be resolved by a single LLM call whose input is limited to the candidate cards and the user's answer, and whose output SHALL be either a candidate index or an explicit "no match" value. A returned index SHALL be validated against the candidate count before use; an out-of-range index SHALL be treated as "no match". The selection step SHALL NOT be able to select a document that is not in the stored candidate list.

#### Scenario: Ordinal answer resolves without an LLM call

- **GIVEN** a pending clarification with three candidates
- **WHEN** the user replies "Candidate 2"
- **THEN** the second candidate SHALL be selected
- **AND** no selection LLM call SHALL be made

#### Scenario: Descriptive answer resolves through the constrained call

- **GIVEN** a pending clarification whose second candidate lists ReactJS
- **WHEN** the user replies "The React developer"
- **THEN** the second candidate SHALL be selected

#### Scenario: Attribute answer resolves through the constrained call

- **GIVEN** a pending clarification whose first candidate's organization is "SEO Technologies"
- **WHEN** the user replies "The one from SEO Technologies"
- **THEN** the first candidate SHALL be selected

#### Scenario: Out-of-range index is rejected

- **GIVEN** a pending clarification with three candidates and a selection call returning index 7
- **WHEN** the selection is interpreted
- **THEN** no candidate SHALL be selected
- **AND** the turn SHALL be treated as a failed selection

### Requirement: Bounded clarification retry

An answer that resolves to no candidate SHALL cause the clarification to be asked once more. A second consecutive failure SHALL clear the pending state and process the user's message through the unconstrained retrieval path used when no entity is resolved. The system SHALL NOT ask for clarification of the same reference more than twice in a row.

#### Scenario: First unresolvable answer re-asks

- **GIVEN** a pending clarification
- **WHEN** the user replies with something that matches no candidate
- **THEN** the clarification SHALL be asked again
- **AND** the pending state SHALL be retained

#### Scenario: Second unresolvable answer abandons clarification

- **GIVEN** a pending clarification that has already been re-asked once
- **WHEN** the user again replies with something that matches no candidate
- **THEN** the pending state SHALL be cleared
- **AND** that message SHALL be answered through ordinary tenant-wide retrieval

### Requirement: Original intent is replayed after selection

On a successful selection the system SHALL retrieve and answer the stored original message, constrained to the selected document, without requiring the user to restate it. The generated answer SHALL address the original request, not the selection utterance.

#### Scenario: Original request resumes automatically

- **GIVEN** a pending clarification stored for the original message "Tell me about Sreelakshmi"
- **WHEN** the user replies "The React developer"
- **THEN** retrieval SHALL run for the original message
- **AND** the reply SHALL answer that original request
- **AND** the user SHALL NOT be asked to repeat it

#### Scenario: Pending state is cleared once resumed

- **GIVEN** a successful selection
- **WHEN** the resumed turn completes
- **THEN** no pending clarification SHALL remain for that conversation

### Requirement: Retrieval is constrained to the resolved document

Once a document is resolved for a turn, every `semantic_retrieval` entry in that turn's plan SHALL carry a document scope naming the resolved document, overriding any scope the planner chose. Structured retrieval SHALL also operate over the resolved scope: the resolved document SHALL be stated in the structured query, and any returned row that carries a `document_id` other than the resolved one SHALL be discarded before the results are used. Rows without a `document_id` value SHALL be retained.

#### Scenario: Semantic scope is overridden with the resolved document

- **GIVEN** a resolved document and a plan whose `semantic_retrieval` entry has a tenant scope
- **WHEN** the plan is executed
- **THEN** that entry SHALL be invoked with a document scope containing only the resolved document id

#### Scenario: Structured rows outside the resolved scope are dropped

- **GIVEN** a resolved document and a structured result set containing rows from two documents
- **WHEN** the results are accumulated
- **THEN** only rows whose `document_id` equals the resolved document SHALL remain

#### Scenario: Aggregate rows without a document id are retained

- **GIVEN** a resolved document and a structured result set of rows with no `document_id` column
- **WHEN** the results are accumulated
- **THEN** those rows SHALL be retained

#### Scenario: Answer cites only the resolved document

- **GIVEN** three same-name candidates and a resolved selection
- **WHEN** the resumed turn produces its reply
- **THEN** every citation SHALL reference the resolved document

### Requirement: Conversation-scoped binding for follow-up turns

After a document is resolved, the system SHALL persist that binding for the conversation and SHALL apply it to subsequent turns whose message contains no person mention of its own. A subsequent mention resolving to a different document SHALL replace the binding. A turn that contains no person mention and no reference to the bound entity, and whose plan is tenant-wide, SHALL clear the binding. While a binding is active for a mention, that mention SHALL NOT trigger a further clarification.

#### Scenario: Follow-up without a name inherits the binding

- **GIVEN** a conversation bound to a resolved candidate
- **WHEN** the user asks "What technologies has she worked with?"
- **THEN** retrieval SHALL be constrained to the bound document
- **AND** no clarification SHALL be requested

#### Scenario: Several follow-ups keep the same binding

- **GIVEN** a conversation bound to a resolved candidate
- **WHEN** the user asks three successive questions containing no person mention
- **THEN** all three SHALL be constrained to the bound document

#### Scenario: A different person replaces the binding

- **GIVEN** a conversation bound to one candidate
- **WHEN** the user asks about a different, unambiguous person
- **THEN** the binding SHALL be replaced with that person's document

#### Scenario: Corpus-wide question clears the binding

- **GIVEN** a conversation bound to a resolved candidate
- **WHEN** the user asks a question with no person mention and no reference to the bound entity, planned tenant-wide
- **THEN** the binding SHALL be cleared
- **AND** retrieval SHALL run across the tenant corpus

#### Scenario: Bound mention is not re-clarified

- **GIVEN** a conversation bound to one of three same-name candidates
- **WHEN** the user names that same ambiguous mention again
- **THEN** no clarification SHALL be requested
- **AND** the bound document SHALL be used

### Requirement: Feature flag and flag-off equivalence

Entity resolution SHALL be controlled by a configuration flag. When the flag is off, no resolver query SHALL be issued, no clarification SHALL ever be returned, the compiled chat graph SHALL be identical to the pre-change topology, and responses SHALL be identical to pre-change responses for the same inputs. The state table SHALL be created by migration regardless of the flag, so enabling the flag requires no migration.

#### Scenario: Flag off issues no resolver query

- **GIVEN** the flag is off and a message referencing an ambiguous person
- **WHEN** the turn runs
- **THEN** no `document_entities` resolver query SHALL be issued
- **AND** the reply SHALL be produced by tenant-wide retrieval as before

#### Scenario: Flag off leaves the graph topology unchanged

- **GIVEN** the flag is off
- **WHEN** the chat graph is compiled
- **THEN** it SHALL contain the same nodes and edges as before this change

#### Scenario: Existing chat tests pass unmodified with the flag off

- **GIVEN** the existing chat test suite with no edits
- **WHEN** it runs with the flag off
- **THEN** every test SHALL pass

#### Scenario: Stale state is inert when the flag is off

- **GIVEN** a conversation with a stored binding and the flag subsequently turned off
- **WHEN** the next turn runs
- **THEN** the stored state SHALL NOT affect retrieval scope

### Requirement: Resolution outcome is observable

Each resolution SHALL emit one structured log record carrying the tenant id, the resolution outcome, the number of mentions matched, the number of distinct candidate documents, and whether the turn used an inherited binding. Mentions that match zero entities SHALL be logged so that extraction recall gaps are visible. Log records SHALL NOT contain the full user message.

#### Scenario: Ambiguous turn is logged with its candidate count

- **GIVEN** an ambiguous mention with three candidates
- **WHEN** the resolver runs
- **THEN** one log record SHALL report the ambiguous outcome and a candidate count of 3

#### Scenario: Zero-match mention is logged

- **GIVEN** a message whose mentions match no person entity
- **WHEN** the resolver runs
- **THEN** one log record SHALL report the unresolved outcome
