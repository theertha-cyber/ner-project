## REMOVED Requirements

### Requirement: Import Deep Link

Removed. The `import=1` query-parameter auto-trigger caused the file picker to reopen
unexpectedly on any remount of `/imported-documents` that didn't change the URL — notably
after using the per-row Review screen's "← Back" button, since that screen swaps in via local
component state without touching the URL. The picker now opens only in direct response to a
click on the page's own "Import file" button.

## MODIFIED Requirements

### Requirement: Request Training From an Import

The `/imported-documents` surface SHALL show, per file, whether it is training-eligible, and
SHALL offer a "Train model" action for eligible files that navigates directly to
`/training-jobs?source=import` (Models & Training, scoped to the import source) — the same
hand-off the Import landing page's own "2. Train model" step uses. The action SHALL NOT call
`POST /api/v1/training-retrain-requests` or otherwise create a System-Admin-approval request as
a side effect of the click; submitting the job remains an explicit, separate step on the
Training Jobs screen. There SHALL be no "review annotations" gate imposed on the Tenant Admin
between an eligible import and reaching that hand-off.

#### Scenario: Request training from an eligible import

- **GIVEN** a training-eligible imported file
- **WHEN** a Tenant Admin clicks "Train model"
- **THEN** the browser SHALL navigate to `/training-jobs?source=import`
- **AND** no training job SHALL have been created by the click itself
- **AND** no annotation-review step SHALL have been required first

## ADDED Requirements

### Requirement: Bulk-Accept Unmapped Types

For a file with one or more rows pending mapping, the `/imported-documents` file-summary list
SHALL offer an "Accept all as new types" action that submits every currently-unmapped type on
that file to `POST /api/v1/annotation-imports/{source_file}/type-map` as a `{"create": true}`
mapping, in a single request — without requiring the Tenant Admin to open each row or choose a
mapping per type first. To support this, `GET /api/v1/annotation-imports` SHALL include, per
file, an `unmapped_types` array (type name and row count) of the file's currently-unmapped
types, in the same shape the import-time response already uses.

#### Scenario: Accept all as new types creates every unmapped type in one call

- **GIVEN** an imported file with 2 unmapped types, `NAME` (3 rows) and `EMAIL` (2 rows)
- **WHEN** a Tenant Admin clicks "Accept all as new types"
- **THEN** a single `POST .../type-map` request SHALL be sent with
  `{"NAME": {"create": true}, "EMAIL": {"create": true}}`
- **AND** both entity types SHALL be created with import provenance
- **AND** the file SHALL become training-eligible once no unmapped type remains

#### Scenario: The file list reports current unmapped types

- **GIVEN** a file with 1 row still pending mapping, referencing an unknown type `XX`
- **WHEN** `GET /api/v1/annotation-imports` is called
- **THEN** that file's entry SHALL include `unmapped_types: [{"type": "XX", "row_count": 1}]`

#### Scenario: A file with nothing pending reports no unmapped types

- **GIVEN** a file with zero rows pending mapping
- **WHEN** `GET /api/v1/annotation-imports` is called
- **THEN** that file's entry SHALL include `unmapped_types: []`
