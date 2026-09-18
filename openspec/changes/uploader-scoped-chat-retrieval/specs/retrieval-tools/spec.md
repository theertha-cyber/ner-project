## MODIFIED Requirements

### Requirement: Tenant scope is caller-supplied, never argument-supplied

The system SHALL carry `tenant_id`, `schema`, the database session, and the requesting user's identity and role in a `ToolContext` constructed by the calling application from authenticated request state. Tool `args_schema` SHALL NOT declare `schema`, `tenant_id`, `purpose`, the requesting user, the uploading user, the ingesting actor, or any other tenancy, purpose-restriction or uploader-restriction parameter, so no LLM-generated or user-generated argument can widen the tool's data scope.

#### Scenario: Tool schemas expose no tenancy parameters

- **GIVEN** every tool in the registry
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** none SHALL be `schema`, `tenant_id`, `tenant`, or `purpose`

#### Scenario: Tool schemas expose no uploader parameters

- **GIVEN** every tool in the registry
- **WHEN** its `args_schema.properties` keys are inspected
- **THEN** none SHALL name the requesting user, the uploading user, or the ingesting actor

#### Scenario: Tool queries the context's schema only

- **GIVEN** two tenant schemas each containing chunks matching the same query
- **WHEN** a tool is invoked with a `ToolContext` for the first schema
- **THEN** every returned result SHALL originate from the first schema
- **AND** no result SHALL originate from the second schema

#### Scenario: Purpose restriction survives the tool layer

- **GIVEN** a tenant schema containing both `purpose='training'` and `purpose='query'` chunks matching the query
- **WHEN** any document retrieval tool is invoked with any argument values
- **THEN** no returned result SHALL come from a `purpose='training'` chunk

#### Scenario: Uploader restriction survives the tool layer

- **GIVEN** a tenant schema containing `purpose='query'` chunks from a document ingested by a human other than the requesting user, matching the query
- **WHEN** any document retrieval tool is invoked for that non-administrative user with any argument values
- **THEN** no returned result SHALL come from that document

#### Scenario: A document scope cannot reach another user's document

- **GIVEN** a document ingested by a human other than the requesting user
- **WHEN** a retrieval tool is invoked with a `scope` of type `document` naming that document's id
- **THEN** the tool SHALL return no results from that document
- **AND** the invocation SHALL NOT raise an argument-validation error, because the scope is well formed and merely matches nothing visible
