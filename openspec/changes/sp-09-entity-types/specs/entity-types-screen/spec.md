## ADDED Requirements

### Requirement: Entity Types List Page

The system SHALL render a full management page at `/entity-types` for authenticated users with role `tenant_admin`. The page SHALL replace the existing `PlaceholderScreen` with a header showing the API path moniker `/api/v1/entity-types`, an active-count / total count summary (e.g. "4 active / 6"), an `h1` with text "Entity Types", and a "+ Define entity type" primary action button. Below the header the page SHALL render a 2-column card grid (`grid-template-columns: repeat(2, 1fr); gap: 14px`) populated by the `EntityTypeCard` component for each entity type returned by the API. While the initial fetch is pending the grid SHALL show 6 skeleton placeholder cards. If the tenant has no entity types the page SHALL display an empty-state prompt encouraging the admin to define their first entity type.

#### Scenario: Page renders header and card grid for tenant admin

- **GIVEN** the user is authenticated with role `tenant_admin` and tenant slug `"acme-corp"`
- **WHEN** they navigate to `/entity-types`
- **THEN** the page title heading "Entity Types" is visible
- **AND** the path moniker `/api/v1/entity-types` appears above the heading in JetBrains Mono
- **AND** the active-count / total summary line is rendered (e.g. "4 active / 6")
- **AND** a "+ Define entity type" button is visible in the top-right

#### Scenario: Card grid shows skeleton while fetching

- **GIVEN** the entity types API call has not yet resolved
- **WHEN** the page first mounts
- **THEN** 6 skeleton placeholder cards are visible in the grid

#### Scenario: Empty state when no entity types exist

- **GIVEN** the tenant has zero entity types
- **WHEN** the API returns an empty array
- **THEN** the page shows an empty-state message (no grid, no cards)
- **AND** the "+ Define entity type" button remains visible

---

### Requirement: Entity Type Card

The system SHALL render an `EntityTypeCard` component for each entity type. The card SHALL display:

- A **colored dot** (34×34 px rounded square with inner 12×12 px dot) whose hue is derived from `index % 7` mapping to `[25, 330, 235, 285, 155, 200, 60]` degrees in OKLCH space, matching the `etDefs` mockup color scheme
- The entity type **name** in JetBrains Mono weight-600 14.5 px
- A **version label** (`v{n}`) in JetBrains Mono 10 px muted
- A **description** below the name in 12.5 px secondary color
- **Required** and **Active/Inactive** pill badges
- A **BASE LABEL MAPPING** section header in JetBrains Mono 10.5 px, with the mapping value shown as `{BASE} → {name}` (e.g. `ORG → vendor_name`) in a styled monospace box
- An **EXAMPLES** section header with up to 2 example values joined by ", "
- Two action buttons: **Edit** (opens the slide-over in edit mode) and a toggle button labeled "Deactivate" / "Reactivate" that soft-deletes or restores the entity type

The card SHALL apply a `translateY(-2px)` hover lift and `border-color: var(--primary-line)` highlight on hover.

#### Scenario: Card displays all fields for an active required entity type

- **GIVEN** an entity type `{name: "vendor_name", version: 2, description: "Name of a vendor", mapping: {ORG: ["vendor_name"]}, examples: ["Northwind Logistics", "Globex Supplies"], required: true, active: true}`
- **WHEN** the card renders at index 0
- **THEN** the name "vendor_name" and "v2" label are visible
- **AND** "Required" and "Active" pills are visible
- **AND** the BASE LABEL MAPPING section shows "ORG → vendor_name"
- **AND** the EXAMPLES section shows "Northwind Logistics, Globex Supplies"
- **AND** the dot uses hue 25 (orange)

#### Scenario: Card shows Deactivate button for active entity type

- **GIVEN** an entity type with `active: true`
- **WHEN** the card renders
- **THEN** the toggle button is labeled "Deactivate"

#### Scenario: Card shows Reactivate button for inactive entity type

- **GIVEN** an entity type with `active: false`
- **WHEN** the card renders
- **THEN** the toggle button is labeled "Reactivate"
- **AND** the "Inactive" pill replaces the "Active" pill

#### Scenario: Card hover lift

- **GIVEN** the entity type card is rendered
- **WHEN** the user hovers over the card
- **THEN** the card applies `transform: translateY(-2px)` and highlights its border with `var(--primary-line)`

---

### Requirement: Define / Edit Entity Type Slide-Over

The system SHALL render a `DefineEntityTypeSlideOver` component using the existing `SlideOver` primitive (width=460). The slide-over SHALL open when the user clicks "+ Define entity type" (create mode) or "Edit" on a card (edit mode). It SHALL display:

- A header with title "Create entity type" or "Edit entity type" and a monospace path `POST /api/v1/entity-types`
- A close (✕) button that dismisses without saving
- A **NAME** field (`placeholder: "vendor_name"`, JetBrains Mono) — disabled in edit mode
- A **DESCRIPTION** field (`placeholder: "Name of a vendor / supplier"`)
- An **EXAMPLES** field (`placeholder: "Acme Supplies, Global Tech Ltd"`, comma-separated, stored as array by splitting on `, `)
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

---

### Requirement: Activate / Deactivate Entity Type

The system SHALL allow a Tenant Admin to soft-toggle an entity type's active status from the card. Clicking "Deactivate" SHALL send `PATCH /api/v1/tenants/{slug}/entity-types/{name}` with `{"is_active": false}`. Clicking "Reactivate" SHALL send the same endpoint with `{"is_active": true}`. On success, the card's active pill and toggle button label SHALL update and a toast SHALL be shown. On error, an error toast SHALL be shown and the list SHALL be refetched.

#### Scenario: Deactivate changes card to inactive state

- **GIVEN** entity type "ship_to_location" is active
- **WHEN** the user clicks "Deactivate" on its card
- **THEN** a PATCH request is sent with `{"is_active": false}`
- **AND** on success, the card shows an "Inactive" pill
- **AND** the toggle button label changes to "Reactivate"
- **AND** the active-count in the header decrements by 1

#### Scenario: Reactivate restores active state

- **GIVEN** entity type "ship_to_location" is inactive
- **WHEN** the user clicks "Reactivate" on its card
- **THEN** a PATCH request is sent with `{"is_active": true}`
- **AND** on success, the card shows an "Active" pill
- **AND** the toggle button label changes to "Deactivate"

#### Scenario: Toggle error shows toast and refetches

- **GIVEN** the PATCH request fails with a 500
- **WHEN** the toggle completes with error
- **THEN** an error toast is shown
- **AND** the entity types list is refetched to restore accurate state

---

### Requirement: Entity Types API Hooks

The system SHALL provide the following TanStack Query hooks in `src/portal/src/hooks/`:

- `useEntityTypes()` — `useQuery` calling `GET /api/v1/tenants/{slug}/entity-types`, keyed on `["entity-types", tenantSlug]`, returning the full array of entity types
- `useCreateEntityType()` — `useMutation` calling `POST /api/v1/tenants/{slug}/entity-types`, invalidates `["entity-types", tenantSlug]` on success
- `useUpdateEntityType()` — `useMutation` calling `PUT /api/v1/tenants/{slug}/entity-types/{name}`, invalidates `["entity-types", tenantSlug]` on success
- `useToggleEntityType()` — `useMutation` calling `PATCH /api/v1/tenants/{slug}/entity-types/{name}` with `{"is_active": boolean}`, invalidates `["entity-types", tenantSlug]` on success

All hooks SHALL use `authFetch` and obtain `tenantSlug` from `useAuth()`.

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
