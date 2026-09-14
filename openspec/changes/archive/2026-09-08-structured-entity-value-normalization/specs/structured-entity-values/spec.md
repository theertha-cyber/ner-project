## ADDED Requirements

### Requirement: Semantic normalization is distinct from lexical normalization

The system SHALL treat semantic normalization and lexical normalization as separate operations. Lexical normalization SHALL map a value's surface form onto a canonical **string** (`normalized_value`) and SHALL remain type-agnostic. Semantic normalization SHALL map a value's text onto a **typed value** in a declared canonical unit, SHALL be dispatched by the entity type's declared value kind, and SHALL be implemented in a module separate from the lexical normalizer. Semantic normalization SHALL NOT alter `entity_value` or `normalized_value`.

#### Scenario: Lexical and semantic normalization produce independent outputs

- **GIVEN** an entity of type `YEARS_OF_EXP` with `entity_value` `"Two and a Half Years"` and a declared value kind of `duration` in `years`
- **WHEN** the pipeline normalizes the entity
- **THEN** `normalized_value` SHALL be `two and a half years`
- **AND** `value_number` SHALL be `2.5`
- **AND** `entity_value` SHALL remain `"Two and a Half Years"`

#### Scenario: Lexical normalization is unchanged for types with no value kind

- **GIVEN** an entity of type `SKILL` with `entity_value` `"ReactJS"` and no declared value kind
- **WHEN** the pipeline normalizes the entity
- **THEN** `normalized_value` SHALL be `react`
- **AND** every semantic value column SHALL be NULL

### Requirement: Value kind vocabulary

The system SHALL support a bounded, code-owned set of value kinds: `text`, `number`, `duration`, `money`, `date`, and `boolean`. `text` SHALL be the default and SHALL mean no semantic normalization is applied. Each non-`text` kind SHALL have exactly one registered parser. A value kind outside the supported set SHALL be rejected at configuration time rather than at extraction time.

#### Scenario: Supported kind is accepted

- **GIVEN** an entity type configured with value kind `duration`
- **WHEN** the pipeline normalizes an entity of that type
- **THEN** the `duration` parser SHALL be invoked

#### Scenario: Unsupported kind is rejected at configuration time

- **GIVEN** an attempt to configure an entity type with value kind `geo`
- **WHEN** the configuration is saved
- **THEN** the request SHALL be rejected
- **AND** no extraction run SHALL fail as a result

#### Scenario: Default kind preserves current behaviour

- **GIVEN** an entity type with no value kind configured
- **WHEN** entities of that type are extracted and persisted
- **THEN** the persisted rows SHALL be identical to those produced before semantic normalization existed, except that the semantic value columns exist and are NULL

### Requirement: Parser registry is extensible without pipeline changes

The system SHALL dispatch semantic normalization through a registry keyed by value kind. Each parser SHALL be a pure function taking the raw entity text and the declared canonical unit, and returning either a structured value or a "not parseable" result. Adding support for a new value kind SHALL require registering one parser and SHALL NOT require changes to the extraction worker, the persistence layer, the database schema, or the SQL whitelist.

#### Scenario: Registering a new kind requires no pipeline change

- **GIVEN** a new parser is registered for a new value kind
- **WHEN** an entity type is configured with that kind and a document is extracted
- **THEN** the typed values SHALL be persisted
- **AND** no change SHALL have been made to the worker, the entity store, or the SQL whitelist

#### Scenario: Parsers are pure and offline

- **GIVEN** any registered parser
- **WHEN** it normalizes a value
- **THEN** it SHALL NOT call an LLM, a network service, or a database
- **AND** repeated calls with the same input SHALL return the same output

### Requirement: Numeric and duration normalization

The system SHALL normalize numeric and duration expressions into `value_number` expressed in the entity type's declared canonical unit. Parsing SHALL handle spelled-out numerals, fractional phrasing, decimal and thousands-separated digits, unit suffixes, and magnitude suffixes. When the source expression names a unit different from the declared canonical unit, the parser SHALL convert to the canonical unit.

#### Scenario: Spelled-out fractional duration

- **GIVEN** an entity of kind `duration` in `years` with text `"two and a half years"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `2.5`
- **AND** `value_unit` SHALL be `years`

#### Scenario: Digit form with a unit suffix

- **GIVEN** an entity of kind `duration` in `years` with text `"5 yrs"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `5.0`

#### Scenario: Source unit differs from canonical unit

- **GIVEN** an entity of kind `duration` in `days` with text `"2 months"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `60.0`
- **AND** `value_unit` SHALL be `days`

#### Scenario: Thousands separators and magnitude suffixes

- **GIVEN** entities of kind `money` in `INR` with texts `"1,200,000"` and `"12 lakh"`
- **WHEN** they are normalized
- **THEN** both SHALL have `value_number` equal to `1200000.0`
- **AND** both SHALL have `value_unit` equal to `INR`

### Requirement: Open bounds and closed ranges

The system SHALL represent an open lower bound (`5+ years`, `more than three years`) as `value_number` set to the stated bound with `value_number_high` NULL, so that a `>=` filter on the bound matches. The system SHALL represent a closed range (`3-5 years`) as `value_number` set to the low end and `value_number_high` set to the high end. Date kinds SHALL use `value_date` and `value_date_high` with the same semantics.

#### Scenario: Open lower bound

- **GIVEN** an entity of kind `duration` in `years` with text `"5+ years"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `5.0`
- **AND** `value_number_high` SHALL be NULL

#### Scenario: Phrased open bound

- **GIVEN** an entity of kind `duration` in `years` with text `"more than three years"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `3.0`

#### Scenario: Closed range

- **GIVEN** an entity of kind `duration` in `years` with text `"3-5 years"`
- **WHEN** it is normalized
- **THEN** `value_number` SHALL be `3.0`
- **AND** `value_number_high` SHALL be `5.0`

### Requirement: Date normalization

The system SHALL normalize date expressions of kind `date` into `value_date` as a calendar date. Expressions naming only a month and year SHALL resolve to the first day of that month. Expressions that cannot be resolved to an unambiguous calendar date SHALL yield NULL rather than a guessed date.

#### Scenario: Full date

- **GIVEN** an entity of kind `date` with text `"15 March 2027"`
- **WHEN** it is normalized
- **THEN** `value_date` SHALL be `2027-03-15`

#### Scenario: Month and year only

- **GIVEN** an entity of kind `date` with text `"March 2027"`
- **WHEN** it is normalized
- **THEN** `value_date` SHALL be `2027-03-01`

#### Scenario: Unresolvable date yields NULL

- **GIVEN** an entity of kind `date` with text `"next spring"`
- **WHEN** it is normalized
- **THEN** `value_date` SHALL be NULL
- **AND** the entity SHALL still be persisted

### Requirement: Unparseable values degrade to NULL, never to failure

The system SHALL persist an entity whose value cannot be semantically normalized with NULL in every semantic value column and with `entity_value` and `normalized_value` unchanged. A parse failure SHALL NOT raise, SHALL NOT fail the document, and SHALL NOT fail the extraction run. The system SHALL record a per-run count of entities whose declared kind was non-`text` but which produced no typed value.

#### Scenario: Junk value in a structured type

- **GIVEN** an entity of type `YEARS_OF_EXP` declared as `duration` with text `"several"`
- **WHEN** it is normalized and persisted
- **THEN** `value_number` SHALL be NULL
- **AND** the row SHALL be persisted with its original `entity_value` and `normalized_value`
- **AND** the extraction run SHALL complete successfully

#### Scenario: Unparseable rows are excluded from numeric filters

- **GIVEN** `document_entities` contains a `YEARS_OF_EXP` row with `value_number = 5.0` and another with `value_number` NULL
- **WHEN** a query filters `entity_type = 'YEARS_OF_EXP' AND value_number > 2`
- **THEN** only the row with `value_number = 5.0` SHALL be returned

### Requirement: Typed value persistence

The system SHALL persist semantic values in dedicated, nullable, typed columns on `document_entities`: `value_kind` (text), `value_number` (double precision), `value_number_high` (double precision), `value_unit` (text), `value_date` (date), and `value_date_high` (date). The existing `entity_value`, `normalized_value`, `confidence`, and location columns SHALL be unchanged in type and in write behaviour. The table SHALL carry indexes supporting filtering by `entity_type` together with `value_number`, and by `entity_type` together with `value_date`.

#### Scenario: Typed columns are written alongside text columns

- **GIVEN** a document containing a `YEARS_OF_EXP` entity reading `"5+ years"` for a type declared as `duration` in `years`
- **WHEN** extraction persists the document's entities
- **THEN** the row SHALL have `entity_value = '5+ years'`, `value_kind = 'duration'`, `value_number = 5.0`, and `value_unit = 'years'`

#### Scenario: Existing text-only queries are unaffected

- **GIVEN** documents extracted before semantic normalization was enabled
- **WHEN** a query filters on `normalized_value`
- **THEN** the same rows SHALL be returned as before this change

### Requirement: Deterministic structured queries

The system SHALL make comparison, range, and sort operations over semantically normalized entity values expressible as SQL predicates evaluated by the database, without LLM interpretation of the entity text.

#### Scenario: Numeric comparison

- **GIVEN** `YEARS_OF_EXP` entities normalized to `value_number` values `1.0`, `2.5`, and `5.0`
- **WHEN** a query filters `entity_type = 'YEARS_OF_EXP' AND value_number > 2`
- **THEN** exactly the rows with `2.5` and `5.0` SHALL be returned

#### Scenario: Inclusive comparison

- **GIVEN** `YEARS_OF_EXP` entities normalized to `value_number` values `4.0` and `5.0`
- **WHEN** a query filters `value_number >= 5`
- **THEN** only the row with `5.0` SHALL be returned

#### Scenario: Date comparison against the current date

- **GIVEN** `CERTIFICATION_EXPIRY` entities normalized to `value_date` values in the past and in the future
- **WHEN** a query filters `value_date < CURRENT_DATE`
- **THEN** only the past-dated rows SHALL be returned

#### Scenario: Range filter

- **GIVEN** entities of kind `date` with `value_date` values spread across several years
- **WHEN** a query filters `value_date BETWEEN '2026-01-01' AND '2026-12-31'`
- **THEN** only rows whose `value_date` falls inside that interval SHALL be returned

### Requirement: Backfill of semantic values without re-inference

The system SHALL provide a backfill mode that populates semantic value columns for existing `document_entities` rows by normalizing their stored `entity_value` text against the current entity type configuration. This mode SHALL NOT re-run model inference, SHALL NOT modify `entity_value`, `normalized_value`, `confidence`, or the location columns, and SHALL be idempotent per document.

#### Scenario: Backfill populates typed values from stored text

- **GIVEN** a document with `document_entities` rows whose semantic value columns are NULL, for a type now declared as `duration`
- **WHEN** the semantic backfill runs for that document
- **THEN** the parseable rows SHALL have their typed columns populated
- **AND** no model inference SHALL have been invoked

#### Scenario: Backfill is idempotent

- **GIVEN** a document whose semantic values have already been backfilled
- **WHEN** the backfill runs again for that document
- **THEN** the row count SHALL be unchanged
- **AND** the typed values SHALL be unchanged

#### Scenario: Backfill leaves text columns untouched

- **GIVEN** a document with existing `document_entities` rows
- **WHEN** the semantic backfill runs
- **THEN** every row's `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, and `char_end` SHALL be unchanged
