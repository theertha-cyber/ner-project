## ADDED Requirements

### Requirement: Inline preview truncation and file card, driven by result count

**Revised twice during implementation** (see design.md Decision 3 for the full history). The final behavior: when an assistant message's `export.row_count` exceeds a configurable preview limit (default: 5 results) — not the reply text's line count — the message thread SHALL render only the first `PREVIEW_LINE_LIMIT` non-empty lines of the reply by default, followed by a file card offering CSV and XLSX downloads, followed by a "See more" toggle that reveals the rest of the reply in place.

The trigger is deliberately the *result count*, not how many lines the reply happens to render as. A detailed answer about a single result (e.g. "give me one candidate," with job title, experience, and education each on their own line) is still one result and SHALL be shown in full, however many lines it spans. A "list every candidate" style answer with more than `PREVIEW_LINE_LIMIT` results SHALL truncate even though each individual line is short. Truncation therefore requires both `export.row_count > PREVIEW_LINE_LIMIT` and the rendered reply actually having more than `PREVIEW_LINE_LIMIT` non-empty lines — a high row count with a short reply (e.g. a one-line summary) does not truncate, since there is nothing to hide.

When a message's `export` field is absent (no structured result behind the reply at all — e.g. an answer drawn from document/semantic sources), the reply SHALL always render in full, regardless of length, since there is no result-count signal to truncate against.

#### Scenario: Large result truncates to a preview, with a file card and a See more toggle

- **GIVEN** an assistant message with `export.row_count = 8` whose reply renders as 8 non-empty lines
- **WHEN** the message thread renders that message
- **THEN** only the first 5 lines of the reply SHALL be shown
- **AND** a file card SHALL appear below the preview, offering a "Download CSV" and a "Download XLSX" action
- **AND** a "See more" toggle SHALL appear below the file card, indicating the count of hidden lines (e.g. "See more (3 more)")

#### Scenario: Clicking See more reveals the full reply

- **GIVEN** a truncated assistant message as above
- **WHEN** the user clicks "See more"
- **THEN** the full reply SHALL render in place
- **AND** the toggle SHALL read "See less"
- **AND** clicking it again SHALL collapse back to the truncated preview

#### Scenario: A detailed single-result answer is never truncated, however many lines it spans

- **GIVEN** an assistant message with `export.row_count = 1` whose reply renders as 8 non-empty lines (e.g. a multi-field breakdown of one candidate: job title, experience, education, skills)
- **WHEN** the message thread renders that message
- **THEN** the full reply SHALL be shown
- **AND** no file card SHALL appear
- **AND** no "See more" toggle SHALL appear

#### Scenario: A high result count with a short reply does not truncate

- **GIVEN** an assistant message with `export.row_count = 28` whose reply renders as a single summary line
- **WHEN** the message thread renders that message
- **THEN** the full (one-line) reply SHALL be shown
- **AND** no file card or "See more" toggle SHALL appear, since there is no hidden content

#### Scenario: A long reply with no structured result behind it is never truncated

- **GIVEN** an assistant message whose `export` field is absent (per the `chat-api` capability, `export` is omitted from the JSON body rather than sent as `null`) and whose reply renders as 8 non-empty lines
- **WHEN** the message thread renders that message
- **THEN** the full reply SHALL be shown
- **AND** no file card or "See more" toggle SHALL appear

#### Scenario: Truncation and the file card are suppressed while a message is still streaming

- **GIVEN** an assistant message that is still `isThinking` or `isStreaming`, with `export.row_count = 8` and a reply that would otherwise truncate once complete
- **WHEN** the message thread renders that message
- **THEN** no truncation, file card, or "See more" toggle SHALL appear until the message finishes (matching the existing suppression of citation chips and the rating control while streaming)

### Requirement: Authenticated download from the file card

Clicking a download action on the file card SHALL fetch the file from the export endpoint using the same Bearer JWT authentication as other chat API calls, and SHALL NOT expose the token in the resulting file URL.

#### Scenario: Clicking download triggers an authenticated fetch

- **GIVEN** a rendered file card for an assistant message
- **WHEN** the user clicks "Download CSV"
- **THEN** a fetch SHALL be sent to `/api/v1/chat/messages/{message_id}/export?format=csv` with an `Authorization: Bearer <token>` header
- **AND** the returned file SHALL be saved via a blob URL, not a direct navigation to a URL containing the token
