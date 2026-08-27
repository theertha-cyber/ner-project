## MODIFIED Requirements

### Requirement: Define / Edit Entity Type Slide-Over

The system SHALL render a `DefineEntityTypeSlideOver` component using the existing `SlideOver` primitive (width=460). The slide-over SHALL open when the user clicks "+ Define entity type" (create mode) or "Edit" on a card (edit mode). It SHALL display:

- A header with title "Create entity type" or "Edit entity type" and a monospace path `POST /api/v1/entity-types`
- A close (✕) button that dismisses without saving
- A **NAME** field (`placeholder: "vendor_name"`, JetBrains Mono) — disabled in edit mode
- A **DESCRIPTION** field (`placeholder: "Name of a vendor / supplier"`)
- An **EXAMPLES** field (`placeholder: "Acme Supplies, Global Tech Ltd"`, comma-separated, stored as array by splitting on `, `)
- **BASE MODEL LABEL** chip row with exactly four buttons: PER, ORG, LOC, MISC — only one active at a time (selected chip highlighted with primary-color background)
- A **CARDINALITY** two-option control with the labels "Single value" and "Multiple values", exactly one selected at a time, defaulting to "Multiple values" in create mode and reflecting the entity type's persisted `cardinality` in edit mode. Each option SHALL carry a one-line explanation of what the choice means for querying — "one value per document" for single, "many values per document" for multiple — so the admin is not required to know the generated schema to choose correctly
- A **VALUE KIND** select offering the supported kinds, defaulting to `text`, and reflecting the entity type's persisted `value_kind` in edit mode. It determines the column type a `single` entity type receives, so a numeric or date entity type left at `text` cannot be compared or ordered in generated SQL
- A **Required flag** toggle row (`label: "Required flag"`, sub-label: `"enforce presence at extraction"`)
- A save button labeled "Create entity type" or "Save changes" depending on mode

The submitted payload SHALL include `cardinality` and `value_kind` in both create and edit mode. The slide-over SHALL NOT send `sql_identifier` — it is system-assigned and read-only.

On save, the slide-over SHALL call `POST /api/v1/tenants/{slug}/entity-types` (create) or `PUT /api/v1/tenants/{slug}/entity-types/{name}` (edit), show a success toast, close the slide-over, and invalidate the entity types query. On API error, it SHALL show an error toast.

#### Scenario: Slide-over opens in create mode from header button

- **GIVEN** the entity types page is rendered
- **WHEN** the user clicks "+ Define entity type"
- **THEN** the slide-over opens with title "Create entity type"
- **AND** all fields are empty
- **AND** the NAME field is editable

#### Scenario: Slide-over opens in edit mode from card

- **GIVEN** entity type "vendor_name" exists with description "Name of a vendor", examples ["Northwind Logistics"], mapping {ORG: ["vendor_name"]}, required: true
- **WHEN** the user clicks "Edit" on the vendor_name card
- **THEN** the slide-over opens with title "Edit entity type"
- **AND** the NAME field shows "vendor_name" and is disabled (read-only)
- **AND** the DESCRIPTION field is pre-filled with "Name of a vendor"
- **AND** the ORG chip is selected
- **AND** the Required toggle is on

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

#### Scenario: Cardinality defaults to multiple in create mode

- **GIVEN** the slide-over opens in create mode
- **WHEN** the user inspects the CARDINALITY control
- **THEN** "Multiple values" SHALL be selected
- **AND** each option SHALL show its one-line explanation

#### Scenario: Cardinality reflects the persisted value in edit mode

- **GIVEN** entity type "candidate_email" persisted with `cardinality: "single"`
- **WHEN** the user clicks "Edit" on its card
- **THEN** "Single value" SHALL be selected in the CARDINALITY control

#### Scenario: Cardinality is submitted on create

- **GIVEN** the slide-over is in create mode with "Single value" selected
- **WHEN** the user clicks "Create entity type"
- **THEN** the POST body SHALL include `"cardinality": "single"`

#### Scenario: An unchanged cardinality round-trips on edit

- **GIVEN** entity type "skill" persisted with `cardinality: "multi"`
- **WHEN** the user edits only its description and saves
- **THEN** the PUT body SHALL include `"cardinality": "multi"`
- **AND** the persisted cardinality SHALL be unchanged

#### Scenario: Value kind reflects the persisted value in edit mode

- **GIVEN** entity type "years_experience" persisted with `value_kind: "number"`
- **WHEN** the user clicks "Edit" on its card
- **THEN** the VALUE KIND select SHALL show `number`

#### Scenario: Value kind defaults to text in create mode

- **GIVEN** the slide-over opens in create mode
- **WHEN** the user inspects the VALUE KIND select
- **THEN** it SHALL show `text`
- **AND** the submitted payload SHALL include `"value_kind": "text"`

#### Scenario: The slide-over never submits sql_identifier

- **GIVEN** the slide-over in either mode
- **WHEN** the user saves
- **THEN** the request body SHALL NOT contain an `sql_identifier` field

### Requirement: Entity Types API Hooks

The system SHALL provide the following TanStack Query hooks in `src/portal/src/hooks/`:

- `useEntityTypes()` — `useQuery` calling `GET /api/v1/tenants/{slug}/entity-types`, keyed on `["entity-types", tenantSlug]`, returning the full array of entity types
- `useCreateEntityType()` — `useMutation` calling `POST /api/v1/tenants/{slug}/entity-types`, invalidates `["entity-types", tenantSlug]` on success
- `useUpdateEntityType()` — `useMutation` calling `PUT /api/v1/tenants/{slug}/entity-types/{name}`, invalidates `["entity-types", tenantSlug]` on success
- `useToggleEntityType()` — `useMutation` calling `PATCH /api/v1/tenants/{slug}/entity-types/{name}` with `{"is_active": boolean}`, invalidates `["entity-types", tenantSlug]` on success

All hooks SHALL use `authFetch` and obtain `tenantSlug` from `useAuth()`.

The `EntityType` type SHALL carry `cardinality` (`"single" | "multi"`), `value_kind` (string), and `sql_identifier` (`string | null`). The create and update payload types SHALL carry `cardinality` and `value_kind` and SHALL NOT carry `sql_identifier`.

#### Scenario: useEntityTypes fetches tenant-scoped list

- **GIVEN** the user is authenticated with tenantSlug `"acme-corp"`
- **WHEN** `useEntityTypes()` is called
- **THEN** it fetches `GET /api/v1/tenants/acme-corp/entity-types`
- **AND** the query key is `["entity-types", "acme-corp"]`

#### Scenario: useCreateEntityType invalidates list on success

- **GIVEN** `useCreateEntityType()` mutation is called with valid entity type data
- **WHEN** the POST returns 201
- **THEN** the `["entity-types", tenantSlug]` query is invalidated
- **AND** the entity types list re-fetches automatically

#### Scenario: The frontend type matches the API response

- **GIVEN** an entity type returned by the API
- **WHEN** it is consumed by `useEntityTypes`
- **THEN** `cardinality`, `value_kind`, and `sql_identifier` SHALL be present on the typed object
- **AND** no consumer SHALL need a cast to read them

## ADDED Requirements

### Requirement: Changing an entity type's cardinality requires confirmation

Because cardinality determines which generated relation holds an entity type's values, changing it on an existing entity type moves the query surface from a child table to a `subject` column or the reverse. Existing rows SHALL NOT be migrated between the two representations, and neither the old table nor the old column SHALL be dropped.

When the admin changes cardinality on an **existing** entity type and saves, the UI SHALL show a confirmation dialog before sending the request. The dialog SHALL state, in plain language, the direction of the change, that already-extracted values stay in the previous representation, and that documents must be re-extracted for the new representation to be populated. Cancelling SHALL leave the slide-over open with the change still selected and send no request. Confirmation SHALL NOT be requested in create mode, nor on an edit that leaves cardinality unchanged.

#### Scenario: Changing multi to single asks for confirmation

- **GIVEN** the slide-over is in edit mode for an entity type persisted as `multi`
- **WHEN** the user selects "Single value" and clicks "Save changes"
- **THEN** a confirmation dialog SHALL appear before any request is sent
- **AND** it SHALL state that previously extracted values remain in the child table
- **AND** it SHALL state that re-extraction is required to populate the `subject` column

#### Scenario: Changing single to multi asks for confirmation

- **GIVEN** the slide-over is in edit mode for an entity type persisted as `single`
- **WHEN** the user selects "Multiple values" and clicks "Save changes"
- **THEN** a confirmation dialog SHALL appear before any request is sent
- **AND** it SHALL state that previously extracted values remain in the `subject` column

#### Scenario: Confirming sends the update

- **GIVEN** the confirmation dialog is showing
- **WHEN** the user confirms
- **THEN** the PUT request SHALL be sent with the new `cardinality`
- **AND** a success toast SHALL be shown on 200

#### Scenario: Cancelling sends nothing

- **GIVEN** the confirmation dialog is showing
- **WHEN** the user cancels
- **THEN** no request SHALL be sent
- **AND** the slide-over SHALL remain open with the newly selected cardinality still shown

#### Scenario: An unchanged cardinality does not prompt

- **GIVEN** the slide-over is in edit mode
- **WHEN** the user changes only the description and saves
- **THEN** no confirmation dialog SHALL appear
- **AND** the PUT request SHALL be sent directly

#### Scenario: Create mode never prompts

- **GIVEN** the slide-over is in create mode
- **WHEN** the user selects either cardinality and saves
- **THEN** no confirmation dialog SHALL appear

### Requirement: Editing an entity type preserves its full base label mapping

The slide-over SHALL preserve every key of a persisted `base_label_mapping` across an edit. An entity type whose mapping carries more than one base label SHALL NOT lose the additional keys when the admin saves an unrelated field.

This matters because the relational projection routes entities by the full set of `base_label_mapping` keys. Silently dropping a key removes a base-model label from the routing index, which empties part of a base-model tenant's query surface with no visible error.

#### Scenario: A multi-key mapping survives an unrelated edit

- **GIVEN** entity type "employer" persisted with `base_label_mapping: {"ORG": ["employer"], "MISC": ["employer"]}`
- **WHEN** the admin edits only the description and saves
- **THEN** the PUT body's `base_label_mapping` SHALL still contain both `ORG` and `MISC`

#### Scenario: The chip row reflects the primary label without discarding the rest

- **GIVEN** the same multi-key entity type
- **WHEN** the slide-over opens in edit mode
- **THEN** one chip SHALL be shown selected
- **AND** the keys not represented by the chip row SHALL still be submitted on save
