## ADDED Requirements

### Requirement: Numeric parsing handles a leading numeral followed by trailing words

The deterministic number reader SHALL parse a value whose leading token is a numeral followed by further words, so surface forms that differ only in trailing prose produce the same typed value. A value SHALL NOT fail to parse merely because descriptive words follow the numeral.

#### Scenario: A numeral followed by prose parses

- **GIVEN** the value `"2 years of experience,"` for an entity type configured with `value_kind = 'duration'` and `value_unit = 'years'`
- **WHEN** semantic normalization runs
- **THEN** `value_kind` SHALL be `duration`
- **AND** `value_number` SHALL be `2.0`
- **AND** `value_unit` SHALL be `years`

#### Scenario: Equivalent surface forms produce equal typed values

- **GIVEN** the values `"2 years of experience"` and `"2+ years of experience"` for the same duration-typed entity type
- **WHEN** semantic normalization runs on both
- **THEN** both SHALL produce `value_number = 2.0`

#### Scenario: A merged multi-token duration parses to its full value

- **GIVEN** the value `"two and a half years"` for a duration-typed entity type with canonical unit `years`
- **WHEN** semantic normalization runs
- **THEN** `value_number` SHALL be `2.5`

#### Scenario: Existing parses are unchanged

- **GIVEN** values already parsing correctly today, including ranges, open bounds, worded numbers, and unit conversions
- **WHEN** semantic normalization runs after this change
- **THEN** their typed values SHALL be identical to the values produced before it

#### Scenario: Genuinely unparseable values still yield no typed value

- **GIVEN** a duration-typed value containing no numeral and no recognized number word
- **WHEN** semantic normalization runs
- **THEN** no typed value SHALL be produced
- **AND** the entity SHALL be counted toward the run's unparseable count
