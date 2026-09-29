## ADDED Requirements

### Requirement: Tabular files tool

The system SHALL provide a `tabular_files` retrieval tool whose single argument is the natural-language `query` to answer from the tenant's uploaded files. Tenant scope SHALL come from the tool context of the authenticated request, never from a tool argument. The tool SHALL be registered in a turn's registry only when server-side resolution finds at least one `ready` file for the authenticated tenant. Its result envelope SHALL carry result rows, the relation and column names used, a truncation flag, and on failure a finite outcome class. The envelope SHALL carry no SQL text.

#### Scenario: Tool schema exposes no tenancy or file-location parameters

- **GIVEN** the `tabular_files` tool
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** the only key SHALL be `query`, and none SHALL be `schema`, `tenant_id`, `tenant`, `file_id`, or `path`

#### Scenario: Tool reads only the context tenant's files

- **GIVEN** tenants A and B each with a ready file named `sales_q3`
- **WHEN** the tool is invoked with a `ToolContext` for tenant A
- **THEN** every returned row SHALL come from tenant A's served Parquet version

#### Scenario: Tool registered only when a file is ready

- **GIVEN** a tenant with one `ready` file
- **WHEN** the per-request registry is built
- **THEN** `registry.get("tabular_files")` SHALL return the tool, and `export_schemas()` SHALL include it

#### Scenario: Envelope omits SQL text

- **GIVEN** a successful `tabular_files` call
- **WHEN** the envelope is returned
- **THEN** it SHALL contain rows, relation and column names, and the truncation flag, and SHALL NOT contain the SQL statement
