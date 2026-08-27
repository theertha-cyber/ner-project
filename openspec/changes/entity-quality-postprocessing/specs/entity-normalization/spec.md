## ADDED Requirements

### Requirement: Canonicalization removes Unicode format characters and folds typographic punctuation

`canonicalize()` SHALL remove characters in Unicode general category `Cf` — including U+200B ZERO WIDTH SPACE and U+FEFF — and SHALL fold typographic punctuation to its ASCII equivalent (U+2018/U+2019 to `'`, U+201C/U+201D to `"`, U+2013/U+2014 to `-`) before casefolding and whitespace collapse. A canonical value SHALL contain no character that makes it unreachable by an equality comparison against the visually identical ASCII literal.

#### Scenario: Zero-width space does not defeat equality matching

- **GIVEN** an extracted value `"​Software Engineer"`
- **WHEN** it is canonicalized
- **THEN** the result SHALL equal `"software engineer"`
- **AND** a SQL predicate `normalized_value = 'software engineer'` SHALL match the persisted row

#### Scenario: Curly apostrophe folds to ASCII

- **GIVEN** an extracted value `"St.Xavier’s College"`
- **WHEN** it is canonicalized
- **THEN** the result SHALL contain an ASCII apostrophe and no U+2019

#### Scenario: En dash and em dash fold to hyphen

- **GIVEN** an extracted value containing U+2013 or U+2014
- **WHEN** it is canonicalized
- **THEN** those characters SHALL be replaced by `-`

#### Scenario: Canonicalization remains a pure function

- **GIVEN** any input value
- **WHEN** it is canonicalized
- **THEN** no network, database, or model call SHALL be made
- **AND** repeated calls with the same input SHALL return the same output

### Requirement: BIO reconstruction tolerates a bounded same-page gap in a continuation

Reconstruction SHALL extend an open entity with a following `I-<TYPE>` prediction of the same type when the two words are on the same page and their word indices differ by no more than `max_entity_word_gap`, rather than requiring strictly consecutive indices. Predictions separated by more than the gap bound, or on different pages, SHALL still close the open entity.

#### Scenario: A two-word gap inside a sentence does not split an entity

- **GIVEN** the source text `"Having two and a half years of experience"` and predictions `B-YEARS_OF_EXP two`, `I-YEARS_OF_EXP half`, `I-YEARS_OF_EXP years`, where `and` and `a` were labelled `O` and filtered out
- **WHEN** entities are reconstructed
- **THEN** exactly one `YEARS_OF_EXP` entity SHALL be produced
- **AND** its value SHALL span from `two` through `years`

#### Scenario: A gap wider than the bound still splits

- **GIVEN** two same-type predictions whose word indices differ by more than `max_entity_word_gap`
- **WHEN** entities are reconstructed
- **THEN** two separate entities SHALL be produced

#### Scenario: Cross-page continuation is never stitched

- **GIVEN** two same-type predictions whose `page_number` values differ, with any word-index gap
- **WHEN** entities are reconstructed
- **THEN** two separate entities SHALL be produced
- **AND** neither entity's character range SHALL span both pages

#### Scenario: Predictions without word alignment keep the existing behaviour

- **GIVEN** predictions carrying no `word_index`, from the base-model pipeline path
- **WHEN** entities are reconstructed
- **THEN** adjacency SHALL be treated as it is today, without the gap bound

### Requirement: Entity spans are punctuation-trimmed with offsets adjusted

Reconstructed entity values SHALL have leading and trailing punctuation removed, and `char_start` / `char_end` SHALL be adjusted by the number of characters removed, so the recorded offsets continue to delimit exactly the text the stored value names. `entity_value` SHALL NOT retain trailing punctuation introduced by whitespace tokenization.

#### Scenario: Trailing comma is removed and the end offset moves

- **GIVEN** a reconstructed entity with value `"Centizen Inc.,"` spanning characters 100 through 114
- **WHEN** trimming is applied
- **THEN** `entity_value` SHALL be `"Centizen Inc."`
- **AND** `char_end` SHALL be 113

#### Scenario: Orphaned opening bracket is removed

- **GIVEN** a reconstructed entity with value `"(CSE)"` 
- **WHEN** trimming is applied
- **THEN** the stored value SHALL contain no unmatched enclosing punctuation

#### Scenario: Interior punctuation is preserved

- **GIVEN** a reconstructed entity with value `"Uniqlo Co., Ltd."`
- **WHEN** trimming is applied
- **THEN** the interior comma and period SHALL be preserved
- **AND** only the trailing period SHALL be removed

#### Scenario: Offsets still delimit the stored value

- **GIVEN** any persisted entity with non-null `char_start` and `char_end`
- **WHEN** the source document text is sliced by those offsets
- **THEN** the slice SHALL equal `entity_value`

### Requirement: Invalid entities are rejected before persistence

The system SHALL NOT persist an entity whose canonical value is empty, consists only of punctuation or format characters, or is shorter than the minimum length configured for its entity type. Rejected entities SHALL be counted and reported on the extraction run.

#### Scenario: A punctuation-only entity is not persisted

- **GIVEN** a reconstructed entity whose `entity_value` is `","`
- **WHEN** persistence is attempted
- **THEN** no row SHALL be written
- **AND** the rejection SHALL be counted on the run

#### Scenario: An entity canonicalizing to an empty string is not persisted

- **GIVEN** a reconstructed entity whose canonical value is the empty string
- **WHEN** persistence is attempted
- **THEN** no row SHALL be written

#### Scenario: A legitimate short value of a configured short-code type is persisted

- **GIVEN** an entity type configured to permit short values, and an entity with value `"C"`
- **WHEN** persistence is attempted
- **THEN** the row SHALL be written

#### Scenario: Rejections are reported

- **GIVEN** a document producing rejected entities
- **WHEN** the run completes
- **THEN** the number of rejected entities SHALL be recorded for that run
