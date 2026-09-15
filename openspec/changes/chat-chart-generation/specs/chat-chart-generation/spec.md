## ADDED Requirements

### Requirement: Chart eligibility gating

The system SHALL offer the generation model a chart-producing tool only for turns that are both grounded in structured rows and destined to be an ordinary answer. A turn SHALL be chart-eligible only when the structured retrieval path produced a non-empty result set for that turn AND the turn's outcome is an answer. Clarification requests, blocked-question declines, out-of-domain declines, and turns short-circuited before retrieval SHALL NOT be chart-eligible, and SHALL NOT incur the additional model call the tool offer requires.

A turn that is not chart-eligible SHALL follow the pre-existing single-call generation path unchanged, producing a byte-identical reply to the one it would have produced before this capability existed.

#### Scenario: Turn with structured rows is offered the chart tool

- **GIVEN** a chat turn whose structured retrieval returned a non-empty set of rows
- **AND** the turn was not blocked, declined, or short-circuited into a clarification request
- **WHEN** generation runs
- **THEN** the generation model SHALL be offered the `render_chart` tool
- **AND** the model SHALL be free to call it or not

#### Scenario: Turn without structured rows is never offered the chart tool

- **GIVEN** a chat turn answered only from document chunks, with no structured rows
- **WHEN** generation runs
- **THEN** the `render_chart` tool SHALL NOT be offered
- **AND** exactly one generation model call SHALL be made
- **AND** the response SHALL carry no chart

#### Scenario: Clarification turn is never offered the chart tool

- **GIVEN** a turn whose entity reference is ambiguous and which resolves to a clarification request
- **WHEN** the turn completes
- **THEN** no chart tool offer SHALL be made
- **AND** the response SHALL carry no chart

#### Scenario: Blocked question is never offered the chart tool

- **GIVEN** a message matching a blocked question pattern
- **WHEN** the turn completes
- **THEN** the turn SHALL short-circuit as it does today
- **AND** no chart tool offer SHALL be made

### Requirement: Chart tool contract

The system SHALL expose to the generation model a single tool named `render_chart` whose description instructs the model to call it only when the question is answered by a small set of categories or a series over a period, and to use values drawn from the data already supplied to it rather than values it composes itself.

The tool's arguments SHALL be a chart payload consisting of: a `chart_type` restricted to `bar`, `line`, or `pie`; a `title`; optional `x_label` and `y_label`; a `categories` array of strings; and a `series` array where each entry has a `name` and a `data` array of numbers. `chart_type`, `title`, `categories`, and `series` SHALL be required.

The tool SHALL NOT accept a tenant identifier, schema name, or any other tenancy parameter, and SHALL NOT perform retrieval, execute SQL, or produce any side effect. Its only effect SHALL be to return a chart payload for rendering.

A chart payload SHALL be rejected when any series' `data` length differs from the `categories` length, when `categories` is empty, or when `series` is empty.

#### Scenario: Model calls the tool with a well-formed payload

- **GIVEN** a chart-eligible turn whose rows contain a numeric measure across four periods
- **WHEN** the generation model calls `render_chart` with `chart_type` `bar`, four categories, and one series of four numbers
- **THEN** the payload SHALL be accepted as structurally valid

#### Scenario: Payload with mismatched series length is rejected

- **GIVEN** a chart-eligible turn
- **WHEN** the model calls `render_chart` with three categories and a series containing four numbers
- **THEN** the payload SHALL be rejected as structurally invalid
- **AND** the turn SHALL proceed as though no chart had been proposed

#### Scenario: Payload with an unsupported chart type is rejected

- **GIVEN** a chart-eligible turn
- **WHEN** the model calls `render_chart` with a `chart_type` outside `bar`, `line`, and `pie`
- **THEN** the payload SHALL be rejected
- **AND** the turn SHALL proceed as though no chart had been proposed

#### Scenario: Model declines to chart non-chartable data

- **GIVEN** a chart-eligible turn whose rows are a single scalar with no category dimension
- **WHEN** generation runs
- **THEN** the model SHALL be permitted to return an answer without calling `render_chart`
- **AND** the response SHALL carry no chart

### Requirement: Chart numbers are grounded in retrieved rows

The system SHALL validate a proposed chart against the structured rows retrieved for that turn before accepting it. Every numeric value in every series SHALL be matched against a numeric value present in those rows. A chart containing any value that cannot be matched SHALL be rejected.

Matching SHALL be effectively exact. The comparison SHALL admit only the sub-unit discrepancies that arise from representing a database `Decimal` as a float or from truncating trailing precision — a relative tolerance of 1e-6. It SHALL NOT admit restatement of a value as a rounder figure: a row value of 143217 presented as 143000 is a rejection, not a match. The model is transcribing values it was shown, not summarising them, and a bar drawn at a tidied number misstates the data it claims to depict.

Rejection SHALL discard the chart only. The turn's text answer, its sources, and its status SHALL be delivered exactly as they would have been had no chart been proposed. A rejected chart SHALL be logged with the offending value so that grounding failures are observable.

#### Scenario: Chart whose values all appear in the rows is accepted

- **GIVEN** structured rows containing the values 120000, 95000, 143000, and 160000
- **WHEN** the model proposes a chart whose single series is those four values
- **THEN** the chart SHALL be accepted
- **AND** the response SHALL carry the chart

#### Scenario: Chart containing an invented value is rejected

- **GIVEN** structured rows containing the values 120000, 95000, and 143000
- **WHEN** the model proposes a chart whose series contains 250000, a value absent from the rows
- **THEN** the chart SHALL be rejected
- **AND** the response SHALL carry no chart
- **AND** the response's `reply` and `sources` SHALL be unchanged from the no-chart case
- **AND** the rejection SHALL be logged with the unmatched value

#### Scenario: Precision artifact does not reject a valid chart

- **GIVEN** a structured row containing the value 120000.004 returned as a decimal
- **WHEN** the model proposes a chart carrying 120000.0 for that value
- **THEN** the value SHALL be treated as matched within tolerance
- **AND** the chart SHALL be accepted

#### Scenario: Value restated as a rounder figure is rejected

- **GIVEN** a structured row containing the value 143217
- **WHEN** the model proposes a chart carrying 143000 for that value
- **THEN** the value SHALL NOT be treated as matched
- **AND** the chart SHALL be rejected
- **AND** the response SHALL carry no chart

### Requirement: Chart is suppressed when the answer is not trusted

The system SHALL suppress an accepted chart whenever citation enforcement replaces the turn's reply. A chart SHALL never accompany a fallback reply, because the chart is drawn from the same evidence the guardrail judged insufficient to support an answer.

#### Scenario: Empty-sources fallback carries no chart

- **GIVEN** a turn for which the model proposed a chart that passed grounding validation
- **AND** citation enforcement finds the turn has no sources and replaces the reply with a fallback
- **WHEN** the response is returned
- **THEN** the response SHALL carry no chart
- **AND** the `reply` SHALL be the fallback message

#### Scenario: Retrieval-failure fallback carries no chart

- **GIVEN** a turn where at least one retrieval capability reported status `failed` and the reply is replaced with the incomplete-retrieval message
- **WHEN** the response is returned
- **THEN** the response SHALL carry no chart
