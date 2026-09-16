## MODIFIED Requirements

### Requirement: Pre-Step-1 Upload Entry Points

The `/annotate/automated` page SHALL render a "Before you begin" section with two work cards,
above the primary "Start with step 1" action rather than below it: "Upload documents" (linking
to `/documents?upload=1&purpose=training&mode=automated`) and "Upload Q&A pair" (linking to
`/documents?upload=1&purpose=qa_pair`). Placing "Start with step 1" after these prerequisite
cards, rather than beside the heading, avoids presenting two competing "click me first" signals
on the same screen — the cards are what step 1 actually depends on. These cards SHALL be visible
regardless of stepper state, since Step 1 ("Suggest Entity Types") depends on seed documents
already sitting in the tenant's document library that this page itself provides no other path
to add.

#### Scenario: Both upload entry points are visible before step 1

- **GIVEN** a Tenant Admin views `/annotate/automated`
- **WHEN** the page renders
- **THEN** a "Before you begin" section SHALL show two cards: "Upload documents" and "Upload Q&A
  pair"

#### Scenario: Upload documents opens the uploader pre-set to Automated

- **GIVEN** a Tenant Admin activates "Upload documents" on `/annotate/automated`
- **WHEN** navigation completes
- **THEN** the Tenant Admin SHALL be at `/documents?upload=1&purpose=training&mode=automated`
- **AND** the upload dialog SHALL be open with "Automated" selected in the annotation-mode
  selector

#### Scenario: Upload Q&A pair opens the Q&A-pair uploader

- **GIVEN** a Tenant Admin activates "Upload Q&A pair" on `/annotate/automated`
- **WHEN** navigation completes
- **THEN** the Tenant Admin SHALL be at `/documents?upload=1&purpose=qa_pair`
- **AND** the upload dialog SHALL be open in Q&A-pair mode

#### Scenario: The primary "Start with step 1" action is unchanged

- **GIVEN** a Tenant Admin views `/annotate/automated`
- **WHEN** "Start with step 1" is activated
- **THEN** navigation SHALL go to `/annotate/automated/schema`
- **AND** the button SHALL render after the "Before you begin" cards in the page, not beside the
  heading
