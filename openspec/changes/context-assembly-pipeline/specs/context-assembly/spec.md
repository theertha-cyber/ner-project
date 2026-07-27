## ADDED Requirements

### Requirement: Token-budgeted context assembly

The system SHALL assemble LLM prompt context under an explicit token budget measured with the same tokenizer encoding used to produce chunks at ingestion time. Retrieved chunks SHALL be admitted whole, in the order received, while they fit within the remaining budget; a chunk that does not fit SHALL be skipped rather than truncated. The system SHALL NOT truncate chunk text by character count.

#### Scenario: A full chunk reaches the prompt intact

- **GIVEN** a retrieved chunk of 512 tokens and a token budget that accommodates it
- **WHEN** context is assembled for the LLM
- **THEN** the assembled context SHALL contain the chunk's complete text
- **AND** the chunk's text SHALL NOT be cut at a fixed character count

#### Scenario: Chunks are admitted until the budget is consumed

- **GIVEN** five retrieved chunks whose combined token count exceeds the configured token budget
- **WHEN** context is assembled
- **THEN** chunks SHALL be admitted in the order received until the next chunk would exceed the budget
- **AND** the total token count of the assembled context SHALL NOT exceed the budget

#### Scenario: A chunk that does not fit is skipped, not cut

- **GIVEN** a chunk that would exceed the remaining budget, followed by a smaller chunk that fits
- **WHEN** context is assembled
- **THEN** the oversized chunk SHALL be omitted entirely
- **AND** no partial fragment of the oversized chunk SHALL appear in the assembled context

#### Scenario: An oversized first chunk is truncated on a token boundary

- **GIVEN** the highest-ranked chunk alone exceeds the entire token budget
- **WHEN** context is assembled
- **THEN** that chunk SHALL be truncated on a token boundary to fit the budget
- **AND** the assembled context SHALL NOT be empty

#### Scenario: Budget accounting includes SQL and NER content

- **GIVEN** SQL results and NER entities that together render to a large amount of text, alongside retrieved chunks
- **WHEN** context is assembled
- **THEN** the token count of the SQL and NER content SHALL count against the same budget as the chunks
- **AND** the total assembled context SHALL NOT exceed the budget

### Requirement: Overlapping chunk deduplication

The system SHALL remove duplicated text arising from the deterministic chunk overlap produced at ingestion. Where two admitted chunks share the same `document_id` and have adjacent `chunk_index` values, the overlapping text SHALL appear only once in the assembled context. Deduplication SHALL NOT alter the retrieved chunk objects or the citation snippets derived from them.

#### Scenario: Adjacent chunks from the same document are deduplicated

- **GIVEN** two admitted chunks from the same `document_id` with adjacent `chunk_index` values that share overlapping text
- **WHEN** context is assembled
- **THEN** the overlapping text SHALL appear exactly once in the assembled context

#### Scenario: Adjacency is detected regardless of relevance ordering

- **GIVEN** two chunks with adjacent `chunk_index` values that arrive non-consecutively because reranking reordered them by relevance
- **WHEN** context is assembled
- **THEN** their overlapping text SHALL still be deduplicated

#### Scenario: Genuinely repeated text in non-adjacent chunks is preserved

- **GIVEN** two chunks from the same document with non-adjacent `chunk_index` values that happen to contain similar text
- **WHEN** context is assembled
- **THEN** both chunks' text SHALL be preserved without trimming

#### Scenario: Deduplication does not mutate citation snippets

- **GIVEN** chunks whose overlapping text is trimmed during assembly
- **WHEN** the API response citations are produced from those same chunks
- **THEN** each citation's context snippet SHALL contain the untrimmed retrieved chunk text

### Requirement: Provenance-labeled context

The system SHALL label each document chunk in the assembled prompt with its resolved document filename and, when available, its page number, rather than with the document's identifier alone. When a filename cannot be resolved the system SHALL fall back to the document identifier; when a page number is unavailable the page reference SHALL be omitted.

#### Scenario: Chunk is labeled with filename and page number

- **GIVEN** a retrieved chunk whose document filename resolves to `report.pdf` and whose `page_number` is 3
- **WHEN** context is assembled
- **THEN** the chunk's label in the assembled context SHALL include `report.pdf`
- **AND** the label SHALL indicate page 3
- **AND** the label SHALL NOT present the raw document identifier as the document's name

#### Scenario: Chunk without a page number omits the page reference

- **GIVEN** a retrieved chunk whose filename resolves but whose `page_number` is `None`
- **WHEN** context is assembled
- **THEN** the label SHALL include the filename
- **AND** the label SHALL contain no page reference

#### Scenario: Unresolvable filename falls back to the document identifier

- **GIVEN** a retrieved chunk whose document filename cannot be resolved
- **WHEN** context is assembled
- **THEN** the label SHALL fall back to the document identifier
- **AND** assembly SHALL NOT raise an error

### Requirement: Single shared assembly implementation

The system SHALL implement prompt context assembly, including the chat system prompt and all context budget constants, in exactly one module used by every chat execution path.

#### Scenario: Both execution paths produce context via the shared assembler

- **GIVEN** the graph-based execution path and the legacy execution path
- **WHEN** each assembles prompt context for the same inputs
- **THEN** both SHALL delegate to the same assembler implementation
- **AND** the resulting prompt messages SHALL be equivalent

#### Scenario: The system prompt is defined in exactly one place

- **GIVEN** the codebase after this change
- **WHEN** searching for the chat system prompt text
- **THEN** exactly one definition SHALL exist

### Requirement: Context assembly configuration

The system SHALL source the context token budget, maximum admitted chunk count, and conversation history turn count from the shared configuration object.

#### Scenario: Context assembly defaults are applied

- **GIVEN** no context-assembly environment variables are set
- **WHEN** the application loads configuration
- **THEN** the context token budget SHALL be 6000
- **AND** the conversation history turn count SHALL be 5

#### Scenario: Token budget is overridable via environment variable

- **GIVEN** the environment variable `NER_CONTEXT_TOKEN_BUDGET` is set to `2000`
- **WHEN** context is assembled
- **THEN** the assembled context SHALL NOT exceed 2000 tokens
