# context-assembly

## ADDED Requirements

### Requirement: Structured evidence degrades by truncation, never by silent omission

The structured-evidence block SHALL be admitted into the prompt in truncated form when it does not fit the remaining token budget, rather than being omitted whole. Any truncation SHALL be stated explicitly in the rendered block. The assembler SHALL NOT produce a prompt in which structured rows were retrieved but no trace of them appears.

#### Scenario: Oversized structured result is truncated, not dropped

- **GIVEN** a structured result whose rendered form costs more tokens than the remaining budget
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL contain a structured-evidence block
- **AND** the block SHALL contain as many complete rows as the budget admits
- **AND** the block SHALL state that it was truncated

#### Scenario: Fitting structured result is admitted whole

- **GIVEN** a structured result that fits the remaining budget
- **WHEN** the prompt is assembled
- **THEN** every row SHALL appear in the block
- **AND** the block SHALL NOT state that it was truncated

#### Scenario: Structured evidence retains budget ahead of chunks

- **GIVEN** a turn carrying both structured rows and retrieved chunks
- **AND** a budget insufficient for both in full
- **WHEN** the prompt is assembled
- **THEN** at least one structured row SHALL be admitted
- **AND** the assembler SHALL NOT admit chunks while omitting the structured block entirely

### Requirement: Exhaustiveness claims match what was admitted

The prompt's instruction to treat structured evidence as complete SHALL apply only when the evidence is complete. When the underlying query was truncated by its row limit, or when the assembler truncated the block, the prompt SHALL state that the list is partial and SHALL NOT instruct the model to present it as exhaustive.

#### Scenario: Row-limit truncation suppresses the exhaustiveness claim

- **GIVEN** a structured result reporting 100 rows returned of 142 matched
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL state that the listing is partial and give the matched total
- **AND** the prompt SHALL NOT instruct the model to report every value as the complete set

#### Scenario: Complete result retains the exhaustiveness instruction

- **GIVEN** a structured result reporting 12 rows returned of 12 matched
- **AND** admitted into the prompt without assembler truncation
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL instruct the model to report every distinct value in the block

#### Scenario: Assembler truncation also suppresses the claim

- **GIVEN** a complete query result that the assembler truncated for budget
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL state that the listing is partial

### Requirement: Duplicate structured values are collapsed before rendering

Exact duplicate rendered rows SHALL be collapsed before the structured block is rendered, so the row budget carries more distinct information. Rows that differ in any rendered field, including their source document, SHALL NOT be collapsed together.

#### Scenario: Identical rows from the same document collapse

- **GIVEN** four structured rows identical in every rendered field
- **WHEN** the block is rendered
- **THEN** the block SHALL contain one such row

#### Scenario: Same value from different documents does not collapse

- **GIVEN** two rows carrying the same entity value but different source documents
- **WHEN** the block is rendered
- **THEN** both rows SHALL appear
- **AND** each SHALL retain its own source document

#### Scenario: Collapse is reflected in the completeness statement

- **GIVEN** a result whose rows collapse from 100 rendered rows to fewer distinct ones
- **WHEN** the block is rendered
- **THEN** the completeness statement SHALL describe the matched total, not the post-collapse count, as the basis for whether the listing is partial

### Requirement: Citations are derived from admitted evidence

The citations returned with a turn SHALL be derived from the evidence actually admitted into the generation prompt. A citation SHALL NOT be returned for evidence that prompt assembly omitted, and admitted evidence SHALL NOT be left uncited because a separate, unrelated cap applied.

#### Scenario: Omitted structured evidence yields no structured citation

- **GIVEN** a turn whose structured block was omitted or truncated away entirely
- **WHEN** citations are produced
- **THEN** no citation SHALL claim structured evidence that the prompt did not contain

#### Scenario: Every admitted chunk is citable

- **GIVEN** a turn in which the prompt admitted five chunks
- **WHEN** citations are produced
- **THEN** the citation set SHALL cover those five chunks
- **AND** the count SHALL NOT be reduced by a cap unrelated to prompt admission

#### Scenario: Structured citation reflects the admitted rows

- **GIVEN** a turn whose structured block was truncated to a subset of rows
- **WHEN** the structured citation is produced
- **THEN** it SHALL represent the admitted subset
- **AND** it SHALL indicate that the underlying result was larger

### Requirement: Retrieval status is rendered into the prompt

The assembler SHALL accept the turn's per-capability retrieval status and render it into the generation prompt whenever any capability reported `failed`, was skipped, or the plan degraded. The rendered statement SHALL name the affected capability.

#### Scenario: Failure statement is rendered

- **GIVEN** a turn whose structured capability reported `failed`
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL contain a retrieval-status statement naming the structured capability as failed

#### Scenario: Skipped recovery is rendered

- **GIVEN** a turn whose semantic recovery was skipped for insufficient budget
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL state that a recovery step was skipped

#### Scenario: Clean turn renders no status block

- **GIVEN** a turn in which every capability reported `ok` or `empty` and planning did not degrade
- **WHEN** the prompt is assembled
- **THEN** the prompt SHALL contain no retrieval-status block

#### Scenario: Status block does not displace evidence

- **GIVEN** a turn carrying a status block and retrievable evidence
- **WHEN** the prompt is assembled
- **THEN** the status block's token cost SHALL be accounted for in the budget
- **AND** the evidence admitted SHALL still respect the total budget

### Requirement: Chunk caps are independently configurable

The number of chunks retrieved per invocation, the number retained after cross-invocation merge, the number admitted into the prompt, and the number cited SHALL each be governed by its own named setting. One setting SHALL NOT implicitly determine several of these, and no cap SHALL be hardcoded at a call site.

#### Scenario: Prompt chunk cap is set independently of retrieval top-k

- **GIVEN** a configuration whose retrieval top-k and prompt chunk cap differ
- **WHEN** a turn is assembled
- **THEN** the number of chunks admitted SHALL follow the prompt chunk cap
- **AND** the number retrieved per invocation SHALL follow retrieval top-k

#### Scenario: Citation cap is not hardcoded

- **GIVEN** the source-assembly stage
- **WHEN** it selects chunk citations
- **THEN** the count SHALL be governed by a named setting
- **AND** it SHALL NOT be a literal embedded in the call site

#### Scenario: Defaults preserve existing behaviour where unchanged

- **GIVEN** a deployment that sets none of the new settings
- **WHEN** a turn is assembled
- **THEN** each setting SHALL take a documented default
- **AND** the defaults SHALL be recorded in the change's design document
