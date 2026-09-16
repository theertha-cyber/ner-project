## MODIFIED Requirements

### Requirement: Define / Edit Entity Type Slide-Over

The system SHALL render a `DefineEntityTypeSlideOver` component using the existing `SlideOver` primitive (width=460). The slide-over SHALL open when the user clicks "+ Define entity type" (create mode) or "Edit" on a card (edit mode). It SHALL display:

- A header with title "Create entity type" or "Edit entity type" and a monospace path `POST /api/v1/entity-types`
- A close (✕) button that dismisses without saving
- A **NAME** field (`placeholder: "vendor_name"`, JetBrains Mono) — disabled in edit mode
- A **DESCRIPTION** field (`placeholder: "Name of a vendor / supplier"`)
- An **EXAMPLES** field (`placeholder: "Acme Supplies, Global Tech Ltd"`, comma-separated, stored as array by splitting on `, `)
- An **EXAMPLE Q&A** section rendering zero or more question/answer row pairs bound to the `qa_examples` field, with an "+ Add Q&A pair" control to append a row and a remove control on each row. The section SHALL be optional — an entity type with no Q&A rows SHALL be valid and SHALL submit `qa_examples` as an empty array. A row with only one of question or answer filled SHALL block submission with an inline validation message; a fully empty row SHALL be discarded on save rather than blocking.
- **BASE MODEL LABEL** chip row with exactly four buttons: PER, ORG, LOC, MISC — only one active at a time (selected chip highlighted with primary-color background)
- A **Required flag** toggle row (`label: "Required flag"`, sub-label: `"enforce presence at extraction"`)
- A save button labeled "Create entity type" or "Save changes" depending on mode

On save, the slide-over SHALL call `POST /api/v1/tenants/{slug}/entity-types` (create) or `PUT /api/v1/tenants/{slug}/entity-types/{name}` (edit), show a success toast, close the slide-over, and invalidate the entity types query. On API error, it SHALL show an error toast.

#### Scenario: Slide-over opens in create mode from header button

- **GIVEN** the entity types page is rendered
- **WHEN** the user clicks "+ Define entity type"
- **THEN** the slide-over opens with title "Create entity type"
- **AND** all fields are empty
- **AND** the NAME field is editable
- **AND** the EXAMPLE Q&A section renders with no rows

#### Scenario: Slide-over opens in edit mode from card

- **GIVEN** entity type "vendor_name" exists with description "Name of a vendor", examples ["Northwind Logistics"], mapping {ORG: ["vendor_name"]}, required: true
- **WHEN** the user clicks "Edit" on the vendor_name card
- **THEN** the slide-over opens with title "Edit entity type"
- **AND** the NAME field shows "vendor_name" and is disabled (read-only)
- **AND** the DESCRIPTION field is pre-filled with "Name of a vendor"
- **AND** the ORG chip is selected
- **AND** the Required toggle is on

#### Scenario: Existing QA pairs are pre-filled in edit mode

- **GIVEN** entity type "years_experience" exists with `qa_examples: [{"question": "How many years of experience does X have?", "answer": "X has 10 years of experience"}]`
- **WHEN** the user clicks "Edit" on the years_experience card
- **THEN** the EXAMPLE Q&A section renders exactly 1 row
- **AND** the row's question input shows "How many years of experience does X have?"
- **AND** the row's answer input shows "X has 10 years of experience"

#### Scenario: Adding a QA pair row and saving submits qa_examples

- **GIVEN** the slide-over is open in edit mode for "years_experience" with no existing Q&A rows
- **WHEN** the user clicks "+ Add Q&A pair", enters a question and an answer, and clicks "Save changes"
- **THEN** the PUT request body SHALL contain `qa_examples` with one object having the entered `question` and `answer`

#### Scenario: Removing a QA pair row

- **GIVEN** the slide-over is open with 2 Q&A rows
- **WHEN** the user clicks the remove control on the first row and saves
- **THEN** the request body SHALL contain `qa_examples` with only the remaining pair

#### Scenario: Partially filled QA pair row blocks submission

- **GIVEN** the slide-over is open with one Q&A row whose question is filled and whose answer is empty
- **WHEN** the user clicks the save button
- **THEN** an inline validation message SHALL be shown on that row
- **AND** no API request SHALL be sent
- **AND** the slide-over SHALL remain open

#### Scenario: Saving with no QA pairs submits an empty array

- **GIVEN** the slide-over is open in create mode with name, description and examples filled and no Q&A rows added
- **WHEN** the user clicks "Create entity type"
- **THEN** the POST request body SHALL contain `qa_examples` as an empty array
- **AND** on 201 response the slide-over SHALL close

#### Scenario: BASE MODEL LABEL chip selection is single-select

- **GIVEN** the slide-over is open
- **WHEN** the user clicks "LOC"
- **THEN** the LOC chip becomes active/highlighted
- **AND** any previously selected chip becomes unselected

#### Scenario: Create submits POST and shows success toast

- **GIVEN** the slide-over is in create mode with valid fields filled
- **WHEN** the user clicks "Create entity type"
- **THEN** a POST request is sent to `/api/v1/tenants/acme-corp/entity-types`
- **AND** on 201 response, a success toast is shown
- **AND** the slide-over closes
- **AND** the entity types list refreshes

#### Scenario: Edit submits PUT and increments version

- **GIVEN** the slide-over is in edit mode for "customer_name" at version 1
- **WHEN** the user updates the description and clicks "Save changes"
- **THEN** a PUT request is sent to `/api/v1/tenants/acme-corp/entity-types/customer_name`
- **AND** on 200 response, the card shows `v2`
- **AND** a success toast is shown

#### Scenario: Escape key closes the slide-over

- **GIVEN** the slide-over is open
- **WHEN** the user presses Escape
- **THEN** the slide-over closes without saving

#### Scenario: API error shows error toast

- **GIVEN** the slide-over is open and the API returns a 422 or 500
- **WHEN** the user submits the form
- **THEN** an error toast is displayed
- **AND** the slide-over remains open so the user can correct the input
