# sql-execution-privileges

## ADDED Requirements

### Requirement: Generated SQL executes under a least-privilege role

Generated SQL SHALL execute under a dedicated database role that holds no privileges on cross-tenant relations. The role SHALL have `SELECT` on the whitelisted tables within tenant schemas and SHALL have no grants on any relation in the `public` schema, on `pg_catalog` beyond the default read-only catalog exposure, or on any other tenant's schema. This control is defence in depth behind the statement validator: a future gap in table-reference resolution SHALL degrade into a permission error rather than a cross-tenant disclosure.

#### Scenario: Generated SQL cannot read cross-tenant relations even if validation is bypassed

- **GIVEN** a generated statement that references `public.widget_api_keys` and that the validator has, for any reason, admitted
- **WHEN** the statement is executed through the generated-SQL execution path
- **THEN** the database SHALL raise an insufficient-privilege error
- **AND** no row from `public.widget_api_keys` SHALL be returned
- **AND** the failure SHALL be recorded as a structured retrieval failure, not as an empty result

#### Scenario: Legitimate tenant-scoped query succeeds under the restricted role

- **GIVEN** a validated statement selecting from `document_entities` joined to `documents` within the caller's tenant schema
- **WHEN** the statement is executed through the generated-SQL execution path
- **THEN** the statement SHALL execute successfully
- **AND** the returned rows SHALL be identical to those the previous connection role returned for the same statement

#### Scenario: Restricted role cannot write

- **GIVEN** a statement that attempts `UPDATE document_entities SET entity_value = 'x'`
- **WHEN** the statement reaches the database under the generated-SQL execution role
- **THEN** the database SHALL reject the statement on privileges
- **AND** the existing read-only transaction control SHALL remain in force independently of this role

### Requirement: Execution role is server-controlled

The role used for generated-SQL execution SHALL be selected by server configuration and SHALL NOT be derivable from, or influenced by, the user's question, the conversation history, the generated SQL text, or any tool argument. The role SHALL be applied by the execution path itself, in the same manner that `schema` is bound from authenticated request context.

#### Scenario: Role cannot be selected by generated SQL

- **GIVEN** generated SQL containing `SET ROLE` or `SET SESSION AUTHORIZATION`
- **WHEN** the statement passes through validation
- **THEN** the validator SHALL reject the statement
- **AND** no role change SHALL reach the database

#### Scenario: Role is applied without a tool argument

- **GIVEN** the structured retrieval capability's declared argument schema
- **WHEN** the schema is inspected at registration time
- **THEN** the schema SHALL declare no argument that names a database role, user, or connection
- **AND** the existing forbidden-tenancy-argument assertion SHALL continue to reject `schema`, `tenant_id`, `tenant`, and `purpose`
