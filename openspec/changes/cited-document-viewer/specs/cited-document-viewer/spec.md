## ADDED Requirements

### Requirement: A citation chip opens the document it cites

The portal SHALL open a document viewer when a user activates a citation chip that names a document, without navigating away from the conversation. A citation that names no document SHALL retain its existing behaviour of revealing its detail card, and SHALL NOT offer to open a document.

#### Scenario: Activating a chip opens the viewer

- **GIVEN** an assistant message carrying a citation whose document is viewable
- **WHEN** the user activates that chip
- **THEN** the viewer SHALL open showing that document
- **AND** the conversation SHALL remain in view behind it

#### Scenario: A citation without a document does not offer to open one

- **GIVEN** a citation produced from a relational or entity source, carrying no document identifier
- **WHEN** the user activates its chip
- **THEN** the existing detail card SHALL be revealed
- **AND** no viewer SHALL open

#### Scenario: The detail card remains reachable

- **GIVEN** a citation chip that does open a document
- **WHEN** the user looks for the snippet and relevance detail shown before this change
- **THEN** that detail SHALL still be reachable

#### Scenario: One viewer serves many chips

- **GIVEN** a message carrying several citation chips
- **WHEN** the user opens one chip and then another
- **THEN** exactly one viewer SHALL be present at a time
- **AND** it SHALL show the most recently activated document

### Requirement: An attachment chip opens the file it represents

The portal SHALL open the same viewer when a user activates the chip for a file they attached to the conversation.

#### Scenario: Opening an attachment

- **GIVEN** a user message carrying an attachment chip
- **WHEN** the user activates it
- **THEN** the viewer SHALL open showing that attached file

### Requirement: The viewer renders the document, at the cited page

The portal SHALL render a PDF document with a page-faithful renderer and an image document as an image. When the citation identifies a page, the viewer SHALL open at that page rather than at the first.

The viewer SHALL NOT mark or highlight any part of the rendered page. A citation's snippet is frequently most of the document, so matching page text against it marks nearly everything; a highlight that is usually wrong is worse than none, because it directs the reader confidently to the wrong place. The cited page is the locator the viewer provides.

#### Scenario: A PDF opens at the cited page

- **GIVEN** a citation identifying page 4 of a multi-page PDF
- **WHEN** the user opens it
- **THEN** the viewer SHALL display page 4 first

#### Scenario: A citation with no page opens at the beginning

- **GIVEN** a citation carrying no page number
- **WHEN** the user opens it
- **THEN** the viewer SHALL display the document from its first page

#### Scenario: No part of the page is marked

- **GIVEN** a citation carrying a snippet of the document's text
- **WHEN** the viewer displays the page
- **THEN** no part of the rendered page SHALL be highlighted or otherwise marked

#### Scenario: An image document renders as an image

- **GIVEN** a cited document that is a photograph or scan in a browser-renderable image format
- **WHEN** the user opens it
- **THEN** it SHALL be displayed as an image

#### Scenario: A converted document renders like a PDF

- **GIVEN** a cited document whose format required conversion for display
- **WHEN** the user opens it
- **THEN** it SHALL render through the same PDF path as a natively stored PDF
- **AND** a page reference SHALL behave as it does for a stored PDF

### Requirement: The viewer shows the document and its controls, and nothing else

The portal SHALL present the document itself as the panel's content. It SHALL NOT reproduce the citation's snippet, the answer text, or other material already visible in the conversation the chip sits in. Chrome SHALL be limited to identifying the document, navigating its pages, and closing the panel.

#### Scenario: The citation snippet is not reproduced in the panel

- **GIVEN** a citation carrying a snippet, whose chip the user activates
- **WHEN** the viewer opens
- **THEN** the snippet SHALL NOT be displayed within the panel

#### Scenario: Page navigation appears only when there is more than one page

- **GIVEN** a single-page document
- **WHEN** the viewer displays it
- **THEN** no page navigation SHALL be shown

### Requirement: Document bytes are fetched as authenticated data, never as a subresource URL

The portal SHALL obtain document bytes through an authenticated request carrying the caller's credentials, and SHALL render them from an in-memory object reference. The portal SHALL NOT place a document's address in a subresource attribute that a browser would fetch without those credentials, and SHALL NOT place any credential in a URL.

#### Scenario: The document is fetched with credentials

- **GIVEN** an authenticated user opening a document
- **WHEN** the request for its bytes is made
- **THEN** it SHALL carry the caller's authorization credentials

#### Scenario: No credential appears in a URL

- **GIVEN** the viewer displaying a document
- **WHEN** the address it renders from is inspected
- **THEN** it SHALL contain no access token

#### Scenario: The rendered type is the one the system declared

- **GIVEN** a document whose stored media type differs from the type the system determined for it
- **WHEN** the viewer renders it
- **THEN** it SHALL use the type the system reported, not one inferred from the document or its name

### Requirement: The viewer releases what it holds

The portal SHALL release an in-memory document reference when the viewer closes and when it is replaced by another document, and SHALL abandon an in-flight request that its result can no longer be shown.

#### Scenario: Closing releases the document

- **GIVEN** an open viewer holding a document
- **WHEN** the user closes it
- **THEN** the in-memory reference SHALL be released

#### Scenario: Opening another document releases the previous one

- **GIVEN** an open viewer showing one document
- **WHEN** the user opens a different document
- **THEN** the first document's reference SHALL be released
- **AND** the viewer SHALL show the second document

#### Scenario: A superseded request is abandoned

- **GIVEN** a document still loading
- **WHEN** the user opens a different document before it arrives
- **THEN** the first request SHALL be abandoned
- **AND** its arrival SHALL NOT replace what the user asked for second

### Requirement: The viewer states why a document cannot be shown

The portal SHALL present each enumerated unavailability outcome as its own message, distinguishing a permanent consequence of the tenant's retention policy from a transient failure a user may retry, and SHALL NOT present a single generic error for all of them. Where the document's extracted text remains available, the viewer SHALL offer it as an alternative.

#### Scenario: A released original is explained as permanent

- **GIVEN** a cited document whose original was not retained
- **WHEN** the user opens it
- **THEN** the viewer SHALL explain that the original was not retained
- **AND** SHALL NOT invite the user to retry

#### Scenario: An unreachable source invites a retry

- **GIVEN** a cited document whose source is temporarily unreachable
- **WHEN** the user opens it
- **THEN** the viewer SHALL explain that the source could not be reached
- **AND** SHALL offer to try again

#### Scenario: A failed conversion is distinguished from a missing original

- **GIVEN** a cited document whose conversion for display failed
- **WHEN** the user opens it
- **THEN** the message shown SHALL differ from the one shown for an original that was not retained

#### Scenario: Extracted text is offered when the original cannot be shown

- **GIVEN** a cited document whose original cannot be produced but whose extracted text exists
- **WHEN** the viewer reports the original unavailable
- **THEN** it SHALL offer the extracted text, labelled as extracted text rather than as the document

### Requirement: The viewer is operable from the keyboard

The portal SHALL make the viewer dismissible with the keyboard, SHALL confine focus to it while it is open, and SHALL return focus to the chip that opened it when it closes.

#### Scenario: Escape closes the viewer

- **GIVEN** an open viewer
- **WHEN** the user presses Escape
- **THEN** it SHALL close

#### Scenario: Focus returns to the originating chip

- **GIVEN** a viewer opened from a citation chip
- **WHEN** it closes
- **THEN** focus SHALL return to that chip

#### Scenario: Focus stays within the open viewer

- **GIVEN** an open viewer
- **WHEN** the user cycles focus forward past its last focusable element
- **THEN** focus SHALL return to its first focusable element rather than reaching the conversation behind it

#### Scenario: The viewer is announced as a dialog

- **GIVEN** an open viewer
- **WHEN** its accessible role is inspected
- **THEN** it SHALL be exposed as a modal dialog with an accessible name identifying the document
