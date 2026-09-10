## MODIFIED Requirements

### Requirement: Entity Type Card

The system SHALL render an `EntityTypeCard` component for each entity type. The card SHALL display:

- A **colored dot** (34×34 px rounded square with inner 12×12 px dot) whose hue is derived from `index % 7` mapping to `[25, 330, 235, 285, 155, 200, 60]` degrees in OKLCH space, matching the `etDefs` mockup color scheme
- The entity type **name** in JetBrains Mono weight-600 14.5 px
- A **version label** (`v{n}`) in JetBrains Mono 10 px muted
- A **provenance chip** in JetBrains Mono 10 px reading `manual`, `suggested`, or `imported`; when `provenance_ref` is present the chip reads `suggested · {ref}` or `imported · {ref}`
- A **description** below the name in 12.5 px secondary color
- **Required** and **Active/Inactive** pill badges
- A **BASE LABEL MAPPING** section header in JetBrains Mono 10.5 px, with the mapping value shown as `{BASE} → {name}` in a styled monospace box
- An **EXAMPLES** section header with up to 2 example values joined by ", "
- Two action buttons: **Edit** (opens the slide-over in edit mode) and a toggle button labeled "Deactivate" / "Reactivate"

The card SHALL apply a `translateY(-2px)` hover lift and `border-color: var(--primary-line)` highlight on hover.

#### Scenario: Card displays all fields for an active required entity type

- **GIVEN** an entity type `{name: "vendor_name", version: 2, description: "Name of a vendor", mapping: {ORG: ["vendor_name"]}, examples: ["Northwind Logistics", "Globex Supplies"], required: true, active: true, provenance: "manual"}`
- **WHEN** the card renders at index 0
- **THEN** the name "vendor_name" and "v2" label are visible
- **AND** "Required" and "Active" pills are visible
- **AND** the BASE LABEL MAPPING section shows "ORG → vendor_name"
- **AND** the EXAMPLES section shows "Northwind Logistics, Globex Supplies"
- **AND** the dot uses hue 25 (orange)
- **AND** a provenance chip reading "manual" is visible

#### Scenario: Card shows a suggested provenance chip with reference

- **GIVEN** an entity type with `provenance: "suggested"` and `provenance_ref: "schema v3"`
- **WHEN** the card renders
- **THEN** a provenance chip reading "suggested · schema v3" is visible

#### Scenario: Card shows an imported provenance chip

- **GIVEN** an entity type with `provenance: "imported"` and `provenance_ref: "hr_gold_set.jsonl"`
- **WHEN** the card renders
- **THEN** a provenance chip reading "imported · hr_gold_set.jsonl" is visible

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
