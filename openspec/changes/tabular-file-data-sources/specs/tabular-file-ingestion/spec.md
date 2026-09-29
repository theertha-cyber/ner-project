## ADDED Requirements

### Requirement: Tabular file upload validation

The system SHALL accept tabular file uploads only from an authenticated tenant administrator, and only for that administrator's own tenant. The tenant is taken from the authenticated request context, never from a request field. It SHALL accept only `.csv` and `.xlsx` files and SHALL reject `.xls`, `.xlsm` and every other extension with a finite `UNSUPPORTED_FILE_TYPE` error. It SHALL reject a file larger than 100 MB with `FILE_TOO_LARGE` and SHALL enforce that limit while reading the request body, before buffering the whole file. It SHALL reject an upload with `FILE_LIMIT_REACHED` when the tenant already has 20 files that are not deleted. An accepted upload SHALL store the original bytes and create a file record with version 1 and status `profiling`.

#### Scenario: CSV upload is accepted

- **GIVEN** an authenticated tenant administrator with fewer than 20 files
- **WHEN** the administrator uploads `sales_q3.csv` of 2 MB
- **THEN** the system SHALL store the original, create a record with version 1 and status `profiling`, and enqueue profiling

#### Scenario: Macro-enabled workbook is rejected

- **GIVEN** an authenticated tenant administrator
- **WHEN** the administrator uploads `budget.xlsm`
- **THEN** the system SHALL respond with `UNSUPPORTED_FILE_TYPE` and SHALL NOT store any object or create a record

#### Scenario: Oversized file is rejected while streaming

- **GIVEN** an authenticated tenant administrator
- **WHEN** the administrator uploads a 150 MB CSV
- **THEN** the system SHALL respond with `FILE_TOO_LARGE` once 100 MB has been read, and SHALL NOT store any object

#### Scenario: Per-tenant file cap

- **GIVEN** a tenant with 20 files that are not deleted
- **WHEN** an administrator uploads another file
- **THEN** the system SHALL respond with `FILE_LIMIT_REACHED`

#### Scenario: Non-administrator cannot upload

- **GIVEN** an authenticated user without the tenant-administrator role
- **WHEN** the user calls the upload endpoint
- **THEN** the system SHALL respond with the existing authorization error and SHALL NOT store anything

### Requirement: Platform object storage layout

The system SHALL store every tenant's tabular files in platform MinIO, regardless of the tenant's residency mode. Objects SHALL use the keys `tenants/{tenant_id}/tabular/{file_id}/v{version}/original.{csv|xlsx}` and `tenants/{tenant_id}/tabular/{file_id}/v{version}/data.parquet`. File metadata SHALL live in the control-plane tables `public.tabular_files` and `public.tabular_file_versions` and SHALL be read and written through a platform session only.

#### Scenario: Tenant-owned tenant uploads a file

- **GIVEN** a tenant whose residency mode is `tenant_owned`
- **WHEN** an administrator uploads a CSV
- **THEN** the original SHALL be stored in platform MinIO under `tenants/{tenant_id}/tabular/{file_id}/v1/`
- **AND** the metadata row SHALL be written to `public.tabular_files` through a platform session, not the tenant's store

#### Scenario: Object keys never cross tenants

- **GIVEN** files uploaded by tenants A and B
- **WHEN** their objects are listed
- **THEN** every object for tenant A SHALL sit under `tenants/{A}/tabular/` and none under `tenants/{B}/`

### Requirement: Safe file parsing

The ingest worker SHALL parse CSV files as text-only columns and SHALL parse XLSX files in read-only mode with cached cell values only, so that no formula, macro or external link is ever evaluated. For XLSX, each selected sheet SHALL become one table. A sheet SHALL be rejected with a finite `UNSUPPORTED_SHEET_LAYOUT` reason when it contains merged cells in the header region or has no detectable header row. The worker SHALL stop and mark the file `failed` with `ROW_LIMIT_EXCEEDED` when a table exceeds 1,000,000 data rows.

#### Scenario: Formula cells use cached values

- **GIVEN** an XLSX whose cell `D2` holds the formula `=B2*C2` with cached value `1200`
- **WHEN** the worker profiles the sheet
- **THEN** column `d`'s value for that row SHALL be `1200` and no formula SHALL be evaluated

#### Scenario: Merged header is rejected

- **GIVEN** an XLSX sheet whose first two rows are a merged title banner
- **WHEN** the worker profiles the sheet
- **THEN** the sheet SHALL be reported with `UNSUPPORTED_SHEET_LAYOUT` and SHALL NOT be offered for publish

#### Scenario: Row cap is enforced while streaming

- **GIVEN** a CSV with 1,200,000 data rows
- **WHEN** the worker profiles it
- **THEN** the file SHALL be marked `failed` with `ROW_LIMIT_EXCEEDED` without the whole file being loaded first

### Requirement: Column identifier sanitization

The worker SHALL derive a SQL-safe identifier for every column from its header. Derivation SHALL lowercase the header, replace each run of non-alphanumeric characters with `_`, trim leading and trailing `_`, prefix `c_` when the result starts with a digit or is empty, prefix `c_` when the result is a SQL reserved word, truncate to 63 characters, and de-duplicate by appending `_2`, `_3` and so on. The original header SHALL be kept as the column's display label. Table names SHALL follow the same rules, derived from the file name, or the sheet name for XLSX.

#### Scenario: Headers become safe identifiers

- **GIVEN** headers `Order ID`, `2024 Revenue ($)`, `select`, `Amount`, `amount`
- **WHEN** the worker sanitizes them
- **THEN** the identifiers SHALL be `order_id`, `c_2024_revenue`, `c_select`, `amount`, `amount_2`
- **AND** each column SHALL keep its original header as display label

### Requirement: Type inference by candidate elimination

For each column the worker SHALL first map null tokens (`""`, `N/A`, `NA`, `null`, `-`, `#N/A`, compared case-insensitively after trimming) to NULL. It SHALL then choose, in the order `boolean`, `bigint`, `numeric`, `date`, `timestamp`, the first type that every non-null value converts to, and SHALL fall back to `text`. Evidence SHALL cover every row of the table, not a sample. An integer candidate SHALL reject values with a leading zero (for example `007`). When a column fails its strictest numeric or temporal candidate only because of a minority of values, the worker SHALL still infer `text` and SHALL record a warning with the count and the first row numbers of the non-conforming values. When every non-null value of a date column parses as both `DD/MM` and `MM/DD`, the worker SHALL NOT pick a format and SHALL mark the column `date_format_required`. An all-null column SHALL be `text`.

#### Scenario: Leading zeros stay text

- **GIVEN** a column with values `007`, `012`, `145`
- **WHEN** the worker infers its type
- **THEN** the inferred type SHALL be `text`

#### Scenario: Null tokens are ignored

- **GIVEN** a column with values `1200`, `450`, `N/A`, `-`, empty
- **WHEN** the worker infers its type
- **THEN** the inferred type SHALL be `bigint` with a null count of 3

#### Scenario: Mixed column falls back with a warning

- **GIVEN** a column where 9,990 of 10,000 non-null values are integers and 10 are `abc`
- **WHEN** the worker infers its type
- **THEN** the inferred type SHALL be `text`
- **AND** the profile SHALL carry a warning with count 10 and the first row numbers of those values

#### Scenario: Ambiguous dates are not guessed

- **GIVEN** a column whose values are `03/04/2026`, `05/06/2026`, `11/12/2026`
- **WHEN** the worker infers its type
- **THEN** the column SHALL be marked `date_format_required` with no chosen format

#### Scenario: Unambiguous day-first dates are detected

- **GIVEN** a column whose values include `25/04/2026`
- **WHEN** the worker infers its type
- **THEN** the column SHALL be `date` with format `DD/MM/YYYY`

### Requirement: Draft profile

After inference the worker SHALL store a draft profile for each table and set the file status to `needs_review`. For every column the profile holds: identifier, display label, inferred type, date format when applicable, null count, distinct count, min and max for numeric and temporal columns, up to 10 top values for text columns with at most 50 distinct values, and warnings. For every table it holds the row count.

#### Scenario: Profile is ready for review

- **GIVEN** `sales_q3.csv` finished profiling
- **WHEN** the administrator requests its profile
- **THEN** the response SHALL list each column's identifier, label, type, null and distinct counts, and the value list for `region` (`EMEA`, `APAC`, `AMER`)
- **AND** the file status SHALL be `needs_review`

### Requirement: Administrator review and load report

The administrator SHALL be able to change each column's identifier (subject to the same sanitization), type, date format and exclusion flag. They SHALL also be able to edit the table-level null tokens, set a description for the table and for each column, and approve or drop each column's value hints. Every review change SHALL be validated, and the system SHALL recompute the load report under the reviewed settings. The load report SHALL show rows read, rows that would load, and rows that would be rejected, with up to 100 rejected row numbers and a finite reason per row, plus a typed preview of the first 20 rows. Excluded columns SHALL be absent from the preview.

#### Scenario: Forcing a stricter type reports rejects

- **GIVEN** a `text` column with 10 non-integer values out of 10,000
- **WHEN** the administrator changes its type to `bigint`
- **THEN** the load report SHALL show 10 rows that would be rejected, each with its row number and reason `cast_failed`

#### Scenario: Excluded column disappears from preview

- **GIVEN** a profile with column `salary`
- **WHEN** the administrator marks `salary` as excluded
- **THEN** the 20-row preview SHALL NOT contain `salary`

#### Scenario: Invalid identifier edit is refused

- **GIVEN** a column under review
- **WHEN** the administrator sets its identifier to `drop table x`
- **THEN** the system SHALL refuse the edit with a validation error naming the field

### Requirement: Publish gate

The system SHALL refuse to publish while any included column is `date_format_required`, while any included table lacks a table description, or while two included columns share an identifier. On a successful publish it SHALL convert the table to `data.parquet` using the approved types, formats and null tokens, drop rows that fail casting (the count is shown in the report), and store the canonical contract. The contract lists the relation name, included columns with types, descriptions and approved value hints, the source file name, sheet and version. Publish SHALL then set status `ready`. A file SHALL NOT be offered to chat unless its status is `ready`.

#### Scenario: Unresolved date format blocks publish

- **GIVEN** a profile with an included column marked `date_format_required`
- **WHEN** the administrator publishes
- **THEN** the system SHALL refuse with `DATE_FORMAT_REQUIRED` naming the column, and the status SHALL stay `needs_review`

#### Scenario: Missing table description blocks publish

- **GIVEN** a reviewed profile without a table description
- **WHEN** the administrator publishes
- **THEN** the system SHALL refuse with `DESCRIPTION_REQUIRED`

#### Scenario: Successful publish

- **GIVEN** a fully reviewed profile for `sales_q3.csv`
- **WHEN** the administrator publishes
- **THEN** `tenants/{tenant_id}/tabular/{file_id}/v1/data.parquet` SHALL exist with the approved column types
- **AND** the stored contract SHALL list only included columns
- **AND** the file status SHALL be `ready`

### Requirement: Versioned replace

Re-uploading a file SHALL create a new version of the same file, which goes through profiling and review independently. While the new version is not `ready`, the previous `ready` version SHALL remain the version served to chat. The review of the new version SHALL show a schema diff against the served version: columns added, removed, retyped and renamed. Publishing the new version SHALL atomically make it the served version. The previous version's objects SHALL then be deleted.

#### Scenario: Old version stays live during review

- **GIVEN** `sales_q3` version 1 is `ready`
- **WHEN** the administrator uploads version 2 and it is in `needs_review`
- **THEN** chat SHALL continue to query version 1

#### Scenario: Schema diff is shown

- **GIVEN** version 1 has columns `amount` (`bigint`) and `region`, and version 2 has `amount` (`numeric`) and `country`
- **WHEN** the administrator opens the version 2 review
- **THEN** the diff SHALL show `amount` retyped, `region` removed and `country` added

#### Scenario: Publishing switches the served version

- **GIVEN** version 2 is reviewed
- **WHEN** the administrator publishes it
- **THEN** the next chat query SHALL use version 2, and version 1's objects SHALL be deleted

### Requirement: File deletion

Deleting a file SHALL mark it `deleted` so it is immediately excluded from chat. It SHALL remove every version's objects from MinIO and remove its contract. Chat workers SHALL treat any cached copy whose version is not the served `ready` version as invalid.

#### Scenario: Deleted file leaves chat immediately

- **GIVEN** a `ready` file `sales_q3`
- **WHEN** the administrator deletes it
- **THEN** the next chat turn SHALL NOT offer `sales_q3` to the planner
- **AND** no object SHALL remain under `tenants/{tenant_id}/tabular/{file_id}/`
