## REMOVED Requirements

### Requirement: Inline preview truncation and file card, driven by result count

**Reason**: This requirement bundled three independent concerns into one row-count threshold (`PREVIEW_LINE_LIMIT`): whether reply text truncates, whether the export option appears at all, and how the export option is presented (an eager file card). Live testing found this conflation actively wrong — a verbose single-result answer got wrongly truncated, and small-but-legitimate results couldn't be downloaded at all just because they were short. It is replaced by three requirements below that make each concern independent: "Inline preview truncation is independent of export availability", "Export offer appears whenever structured data exists, regardless of result count", and "Export prompt reveals download actions only after the user opts in".

**Migration**: No data migration — this is a pure frontend rendering-logic change. `export.row_count`/`formats` (unchanged on the wire) now drive three independent conditions instead of one combined threshold check.

## RENAMED Requirements

- FROM: `### Requirement: Authenticated download from the file card`
- TO: `### Requirement: Authenticated download from the revealed format actions`

## MODIFIED Requirements

### Requirement: Authenticated download from the revealed format actions

Clicking a download action (once revealed, per the "Export prompt reveals download actions only after the user opts in" requirement below) SHALL fetch the file from the export endpoint using the same Bearer JWT authentication as other chat API calls, and SHALL NOT expose the token in the resulting file URL.

#### Scenario: Clicking download triggers an authenticated fetch

- **GIVEN** a revealed "Download CSV" action for an assistant message
- **WHEN** the user clicks it
- **THEN** a fetch SHALL be sent to `/api/v1/chat/messages/{message_id}/export?format=csv` with an `Authorization: Bearer <token>` header
- **AND** the returned file SHALL be saved via a blob URL, not a direct navigation to a URL containing the token

## ADDED Requirements

### Requirement: Inline preview truncation is independent of export availability

Whether an assistant message's reply text truncates with a "See more" toggle SHALL be determined by whether the rendered reply visually overflows a bounded display height — not by `export.row_count`, not by counting the reply's text lines, and not by any other business-logic proxy for length. This holds regardless of whether the turn has an associated export at all: a long reply with no structured result behind it (`export` absent) truncates on overflow exactly the same as a long reply that does have one.

Truncation and export availability (see the "Export offer" requirement below) are independent conditions evaluated separately. A short reply with a large `export.row_count` does not truncate (nothing overflows). A long reply with `export.row_count = 1` still truncates if it visually overflows, even though it describes only one result.

#### Scenario: A reply that visually overflows truncates with a See more toggle

- **GIVEN** an assistant message whose rendered reply exceeds the bounded display height
- **WHEN** the message thread renders that message
- **THEN** the reply SHALL be visually clipped to the bounded height
- **AND** a "See more" toggle SHALL appear below it

#### Scenario: Clicking See more reveals the full reply

- **GIVEN** a truncated assistant message as above
- **WHEN** the user clicks "See more"
- **THEN** the full reply SHALL render in place
- **AND** the toggle SHALL read "See less"
- **AND** clicking it again SHALL collapse back to the bounded height

#### Scenario: A reply that fits within the bounded height is never truncated, regardless of export.row_count

- **GIVEN** an assistant message whose rendered reply does not exceed the bounded display height, with `export.row_count = 28`
- **WHEN** the message thread renders that message
- **THEN** the full reply SHALL be shown
- **AND** no "See more" toggle SHALL appear

#### Scenario: A long reply with no structured result behind it still truncates on overflow

- **GIVEN** an assistant message whose `export` field is absent and whose rendered reply exceeds the bounded display height
- **WHEN** the message thread renders that message
- **THEN** the reply SHALL be visually clipped to the bounded height
- **AND** a "See more" toggle SHALL appear below it, exactly as it would for a message with an export

#### Scenario: Truncation is suppressed while a message is still streaming

- **GIVEN** an assistant message that is still `isThinking` or `isStreaming`
- **WHEN** the message thread renders that message
- **THEN** no truncation or "See more" toggle SHALL appear until the message finishes (matching the existing suppression of citation chips and the rating control while streaming)

### Requirement: Export offer appears whenever structured data exists, regardless of result count

When an assistant message's `export` field is present (`export.row_count >= 1`), the message thread SHALL show an export prompt below the reply, regardless of how many results that is and regardless of whether the reply's own text happens to be truncated. There is no row-count threshold gating whether the prompt appears — offering the option costs nothing and a small result is exactly as legitimately downloadable as a large one.

The prompt SHALL state the actual result count (e.g. "This includes 45 results — want a downloadable version?"), so the user is not opting in blind.

When a message's `export` field is absent, no export prompt SHALL appear.

#### Scenario: A small result still gets an export prompt

- **GIVEN** an assistant message with `export.row_count = 1`
- **WHEN** the message thread renders that message
- **THEN** an export prompt SHALL appear below the reply, stating "1 result"
- **AND** this holds even though the reply itself is not truncated (per the truncation requirement above)

#### Scenario: A large result gets an export prompt stating the count

- **GIVEN** an assistant message with `export.row_count = 45`
- **WHEN** the message thread renders that message
- **THEN** an export prompt SHALL appear below the reply, stating "45 results"

#### Scenario: No export prompt when there is no structured result

- **GIVEN** an assistant message whose `export` field is absent
- **WHEN** the message thread renders that message
- **THEN** no export prompt SHALL appear

#### Scenario: The export prompt is suppressed while a message is still streaming

- **GIVEN** an assistant message that is still `isThinking` or `isStreaming`, with `export.row_count = 8`
- **WHEN** the message thread renders that message
- **THEN** no export prompt SHALL appear until the message finishes

### Requirement: Export prompt reveals download actions only after the user opts in

The export prompt SHALL NOT render "Download CSV"/"Download XLSX" actions immediately. It SHALL first render as a lightweight, low-visual-weight question stating the result count. Only after the user responds affirmatively (clicks the prompt) SHALL the CSV and XLSX download actions render.

#### Scenario: The prompt does not show download actions before the user responds

- **GIVEN** an assistant message with `export.row_count = 12`
- **WHEN** the message thread renders that message
- **THEN** an export prompt stating "12 results" SHALL appear
- **AND** no "Download CSV" or "Download XLSX" action SHALL be visible yet

#### Scenario: Responding to the prompt reveals the format actions

- **GIVEN** a rendered export prompt as above
- **WHEN** the user clicks the prompt
- **THEN** "Download CSV" and "Download XLSX" actions SHALL appear in its place
