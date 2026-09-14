## ADDED Requirements

### Requirement: Shared Observability Initialization Across All Processes

Every deployable process — the eight FastAPI services (`gateway`, `chat_api`, `document_service`, `extraction_service`, `model_serving`, `training_service`, `annotation_service`, `analytics_service`) and the two Celery workers (`celery_worker`, `celery_worker_extraction`) — SHALL configure logging, tracing and metrics through a single shared entry point `src/shared/observability.init_observability(service_name)` invoked once at process start. No process SHALL configure the root logger independently.

Where an OTLP endpoint is configured, every process SHALL export its log records to that endpoint in addition to writing them to stdout, so records are queryable outside the container that produced them. An empty endpoint SHALL disable export entirely and SHALL NOT affect stdout.

#### Scenario: A service emits application logs at the configured level

- **GIVEN** any of the ten processes is running with `NER_LOG_LEVEL` unset
- **WHEN** application code in that process calls `logger.info(...)`
- **THEN** the record SHALL be written to stdout
- **AND** it SHALL NOT be discarded because the root logger has no handler attached

#### Scenario: No process calls basicConfig directly

- **GIVEN** the `src/` tree is searched for `logging.basicConfig`
- **WHEN** the results are examined
- **THEN** the only occurrence SHALL be inside `src/shared/observability/`

#### Scenario: Log level is configurable per process

- **GIVEN** a process starts with `NER_LOG_LEVEL=DEBUG` in its environment
- **WHEN** application code calls `logger.debug(...)`
- **THEN** the record SHALL be emitted

#### Scenario: Log records reach the configured log store

- **GIVEN** a process is running with `NER_OTLP_ENDPOINT` set to a reachable collector
- **WHEN** application code calls `logger.info(...)`
- **THEN** the record SHALL be written to stdout and exported over OTLP
- **AND** the exported record SHALL carry the same JSON body, the same context fields and the same redaction as the copy written to stdout
- **AND** given the endpoint is empty, the record SHALL still be written to stdout and SHALL NOT be exported

### Requirement: Structured JSON Log Records With Correlation Context

Every log record emitted by any process SHALL be serialized as a single-line JSON object carrying at minimum `ts`, `level`, `service`, `event`, `request_id`, `trace_id`, `tenant_id` and `user_hash`. Context fields SHALL be populated automatically from the ambient request context rather than passed explicitly at each call site. Where no request context exists — process startup, a scheduled task — the context fields SHALL be present with a null value rather than absent.

#### Scenario: A log record emitted during a request carries request context

- **GIVEN** a request has been admitted with a resolved tenant and authenticated user
- **WHEN** application code within that request calls `logger.info(...)`
- **THEN** the emitted record SHALL parse as JSON
- **AND** its `request_id`, `tenant_id`, `user_hash` and `trace_id` fields SHALL match the values resolved for that request

#### Scenario: A log record emitted outside a request has null context

- **GIVEN** a process is executing startup code with no active request
- **WHEN** application code calls `logger.info(...)`
- **THEN** the emitted record SHALL parse as JSON
- **AND** `request_id`, `tenant_id`, `user_hash` and `trace_id` SHALL each be present with a null value

### Requirement: Correlation Identifier Propagated Across Every Hop

A single correlation identifier SHALL follow one unit of work across process boundaries. The identifier SHALL be read from the inbound `X-Request-ID` header when present and generated when absent, stored in the ambient request context, forwarded as `X-Request-ID` on every outbound HTTP call to another platform service, carried in the payload of every Celery task enqueued during that request, and restored into the ambient context by the worker executing that task.

#### Scenario: Identifier survives a service-to-service HTTP call

- **GIVEN** a request arrives at the gateway carrying `X-Request-ID: abc-123`
- **WHEN** the gateway makes an onward HTTP call to another platform service during that request
- **THEN** the outbound request SHALL carry the header `X-Request-ID: abc-123`
- **AND** log records emitted by the receiving service while handling it SHALL carry `request_id` of `abc-123`

#### Scenario: Identifier survives enqueue to a Celery worker

- **GIVEN** a request with correlation identifier `abc-123` enqueues a Celery task
- **WHEN** a worker picks up and executes that task
- **THEN** log records emitted by the worker during that task SHALL carry `request_id` of `abc-123`

#### Scenario: Identifier is generated when absent

- **GIVEN** a request arrives with no `X-Request-ID` header
- **WHEN** the request is handled
- **THEN** a new identifier SHALL be generated
- **AND** it SHALL be returned to the caller in the `X-Request-ID` response header

#### Scenario: Inbound identifier is never used as an authorization or tenancy input

- **GIVEN** a request arrives carrying an `X-Request-ID` header supplied by an external caller
- **WHEN** the request is handled
- **THEN** the value SHALL be used only for correlation
- **AND** tenant and user identity SHALL continue to be derived from the validated JWT claims alone

### Requirement: Single Shared Observability Middleware

Correlation and telemetry setup SHALL be implemented once, in `src/shared/observability`, and mounted by every FastAPI service. The per-service `src/*/middleware/tenant_context.py` modules SHALL NOT each generate or attach their own request identifier. Tenant resolution, token decoding and authorization SHALL remain in the existing per-service middleware and are out of scope for the shared component.

#### Scenario: No service generates its own request identifier

- **GIVEN** the eight `src/*/middleware/tenant_context.py` files are searched for request-identifier generation
- **WHEN** the results are examined
- **THEN** no occurrence of request-identifier generation SHALL remain in any of them

#### Scenario: Existing tenant enforcement is unchanged

- **GIVEN** the tenant-isolation test suite that passes before this change
- **WHEN** it is re-run after the shared middleware is mounted
- **THEN** every test SHALL still pass

### Requirement: Sensitive Content Excluded From Telemetry

No log record and no span attribute SHALL contain generated SQL text, prompt text, model answer text, document content, extracted entity values, credentials, bearer tokens, widget keys, or connection strings. Events describing such operations SHALL record their shape instead — counts, durations, outcomes and enumerated failure reasons. A redaction filter SHALL be applied to every log record as a mandatory part of `init_observability`, so that a call site that passes a prohibited field cannot produce a record containing it.

#### Scenario: SQL generation is logged without the query text

- **GIVEN** the chat path generates SQL and executes it
- **WHEN** the `sql_attempt` event is logged
- **THEN** the record SHALL contain the attempt number, outcome, defect category, matched row count and duration
- **AND** it SHALL NOT contain the generated SQL string

#### Scenario: A prohibited field passed by a call site is stripped

- **GIVEN** application code calls `logger.info` passing a field named `sql`, `prompt`, `answer`, `document_text`, `password`, `token` or `authorization`
- **WHEN** the record is emitted
- **THEN** the emitted JSON SHALL NOT contain that field's value

#### Scenario: Extracted personal data never reaches a log record

- **GIVEN** a document is processed and entities are extracted from it
- **WHEN** the resulting log records for that request are collected
- **THEN** no record SHALL contain an extracted entity value
- **AND** records MAY contain entity counts and entity type names

### Requirement: Opaque Identity In Telemetry

Telemetry SHALL identify tenants and users by opaque values only. Tenants SHALL appear as their UUID, never as a slug, company name or subdomain. Users SHALL appear as a truncated HMAC-SHA256 of their user identifier under a pepper sourced from the environment. Raw user identifiers and email addresses SHALL NOT appear in any log record or span attribute.

#### Scenario: User identity is hashed

- **GIVEN** a request from an authenticated user
- **WHEN** log records for that request are collected
- **THEN** each SHALL carry a `user_hash` field
- **AND** no record SHALL contain the raw user identifier or the user's email address

#### Scenario: The same user is correlatable within a retention window

- **GIVEN** two separate requests from the same authenticated user under an unchanged pepper
- **WHEN** the `user_hash` values from both are compared
- **THEN** they SHALL be equal

#### Scenario: Tenant identity is a UUID

- **GIVEN** a request resolved to a tenant
- **WHEN** log records and span attributes for that request are collected
- **THEN** the tenant SHALL be represented by its UUID
- **AND** no tenant slug or display name SHALL appear

### Requirement: Distributed Traces Spanning Services And Workers

Each process SHALL emit OpenTelemetry spans via auto-instrumentation for FastAPI, SQLAlchemy, asyncpg, httpx, redis and Celery, exported over OTLP to a collector endpoint configured by environment variable. Spans produced by different processes while handling one unit of work SHALL share a single trace identifier, and that identifier SHALL appear on log records emitted during the same work.

#### Scenario: One trace spans two services

- **GIVEN** the local stack is running and a request to the gateway triggers an onward call to another service
- **WHEN** the resulting trace is retrieved from the trace backend
- **THEN** it SHALL contain spans from both processes under a single trace identifier

#### Scenario: A trace extends into a Celery task

- **GIVEN** a request enqueues a Celery task
- **WHEN** the resulting trace is retrieved after the worker has executed the task
- **THEN** the worker's spans SHALL appear under the same trace identifier as the originating request

#### Scenario: Logs join traces

- **GIVEN** a request that produced both spans and log records
- **WHEN** the `trace_id` on those log records is compared with the trace identifier of the spans
- **THEN** they SHALL be equal

#### Scenario: Missing collector does not break the request path

- **GIVEN** the configured OTLP endpoint is unreachable
- **WHEN** a request is handled
- **THEN** the request SHALL be served normally
- **AND** the process SHALL NOT raise an unhandled exception on span export failure

### Requirement: Metrics Endpoint On Every Service

Each of the eight FastAPI services SHALL expose a Prometheus-format `/metrics` endpoint reporting request count, error count, request duration histogram and database connection pool usage. The two Celery workers, which run no HTTP server, SHALL export the equivalent metrics over OTLP to the collector instead. The `/metrics` endpoint SHALL NOT require tenant context and SHALL be exempt from tenant middleware, and SHALL NOT carry `tenant_id` as a label on any metric introduced by this change.

#### Scenario: Metrics endpoint responds

- **GIVEN** any of the eight FastAPI services is running
- **WHEN** `GET /metrics` is called without an Authorization header
- **THEN** the response SHALL be HTTP 200 in Prometheus text exposition format

#### Scenario: Request metrics increment

- **GIVEN** a service's request counter is read
- **WHEN** a request is served and the counter is read again
- **THEN** the second reading SHALL be greater than the first

#### Scenario: No tenant label is emitted by this change

- **GIVEN** the `/metrics` output of any service
- **WHEN** the label sets of the metric families introduced by this change are examined
- **THEN** none SHALL include a `tenant_id` label
- **AND** the check SHALL be scoped to the families this change declares, so that a later change adding a deliberately tenant-labelled family does not falsify this scenario
