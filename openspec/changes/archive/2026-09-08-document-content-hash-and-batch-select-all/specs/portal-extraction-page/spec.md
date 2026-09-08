## ADDED Requirements

### Requirement: Batch Document-Selection Modal — Bulk Selection

The batch document-selection modal SHALL render a "Select all" checkbox between the "Select documents to extract" heading and the scrollable document list, and a selected-count line below the list. Both controls SHALL operate only on the documents currently shown in the modal.

A document is *selectable* when its `already_extracted` flag is `false`. "Select all" SHALL be checked when the modal contains at least one selectable document and every selectable document is selected, and unchecked otherwise. Checking it SHALL select every selectable document; unchecking it SHALL deselect every selectable document. It SHALL be disabled when the modal contains zero selectable documents.

Documents with `already_extracted: true` SHALL NEVER enter the selection set by any path, including "Select all", and SHALL remain visibly unchecked and disabled. The selected-count line SHALL report only selectable documents that are actually selected.

This requirement adds controls to the existing modal and SHALL NOT change its dimensions, layout, scroll behavior, typography, buttons, per-row checkbox styling, or dark/light theme behavior.

#### Scenario: Unextracted documents are selectable

- **GIVEN** the modal is open with a document whose `already_extracted` is `false`
- **WHEN** the user clicks that document's checkbox
- **THEN** the checkbox SHALL become checked
- **AND** the selected-count line SHALL report one selected document

#### Scenario: Select all selects every eligible document and excludes already-extracted ones

- **GIVEN** the modal is open with three selectable documents and two already-extracted documents
- **WHEN** the user checks "Select all"
- **THEN** all three selectable documents' checkboxes SHALL be checked
- **AND** both already-extracted documents' checkboxes SHALL remain unchecked and disabled
- **AND** the selected-count line SHALL report three selected documents

#### Scenario: Clearing Select all deselects eligible documents without affecting disabled ones

- **GIVEN** the modal is open with "Select all" checked and every selectable document selected
- **WHEN** the user unchecks "Select all"
- **THEN** every selectable document's checkbox SHALL become unchecked
- **AND** the already-extracted documents' checkboxes SHALL remain unchecked and disabled
- **AND** the "Run extraction" action SHALL be disabled

#### Scenario: Select all reflects the current selection state

- **GIVEN** the modal is open with every selectable document individually checked
- **WHEN** the modal renders
- **THEN** the "Select all" checkbox SHALL be checked
- **AND** unchecking any single document SHALL make "Select all" unchecked

#### Scenario: Select all is disabled when there are no eligible documents

- **GIVEN** the modal is open and every listed document has `already_extracted: true`
- **WHEN** the modal renders
- **THEN** the "Select all" checkbox SHALL be disabled
- **AND** the "Run extraction" action SHALL be disabled

#### Scenario: Run extraction submits only eligible selected documents

- **GIVEN** the modal is open with a mix of selectable and already-extracted documents and "Select all" checked
- **WHEN** the user clicks "Run extraction"
- **THEN** the confirmed document ID list SHALL contain exactly the selectable documents' IDs
- **AND** SHALL NOT contain any already-extracted document's ID
