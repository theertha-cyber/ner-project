## ADDED Requirements

### Requirement: Chat And Retrieval Path Instrumentation

The chat request path SHALL emit a span per stage carrying attributes describing the shape of the work done at that stage, and SHALL emit metrics for the outcomes that are aggregated across requests. Stages are: guardrail evaluation, entity resolution, catalogue slice retrieval, document retrieval and rerank, SQL generation, SQL execution, and answer composition. No span attribute or metric label introduced by this requirement SHALL carry question text, answer text, SQL text, retrieved content or entity values.

#### Scenario: A chat request produces a span per stage

- **GIVEN** the local stack is running and a chat question is answered end to end
- **WHEN** the resulting trace is retrieved
- **THEN** it SHALL contain a span for each stage the request actually executed
- **AND** each span SHALL carry a duration and the stage's outcome attribute

#### Scenario: SQL generation records repair depth and defect

- **GIVEN** a chat question for which the first generated query is invalid and a second attempt succeeds
- **WHEN** the SQL generation span and metrics are examined
- **THEN** the span SHALL record `attempts` of 2 and `repair_depth` of 1
- **AND** the first attempt SHALL record a `defect` drawn from an enumerated set (for example `unknown_column`, `bad_join`, `syntax`, `timeout`)
- **AND** a repair-depth histogram observation SHALL be recorded

#### Scenario: An abandoned query records why it was abandoned

- **GIVEN** a chat question where SQL generation exhausts its attempt budget or its deadline
- **WHEN** the span and metrics are examined
- **THEN** the outcome SHALL be `abandoned`
- **AND** an enumerated abandon reason SHALL be recorded, distinguishing attempt exhaustion from deadline exhaustion

#### Scenario: Retrieval records whether it returned anything

- **GIVEN** a chat question whose retrieval returns no documents
- **WHEN** the retrieval span and metrics are examined
- **THEN** the span SHALL record a result count of zero
- **AND** a zero-result counter SHALL be incremented

#### Scenario: LLM usage is recorded per call

- **GIVEN** a chat request that makes one or more LLM calls
- **WHEN** the spans for those calls are examined
- **THEN** each SHALL record input token count, output token count, provider latency and an outcome
- **AND** a failed call SHALL record an enumerated error class rather than the provider's message text

#### Scenario: No chat telemetry contains message or query content

- **GIVEN** a chat request has been answered
- **WHEN** every span attribute and log record produced by that request is collected
- **THEN** none SHALL contain the question text, the answer text, the generated SQL, a retrieved passage, or an entity value

### Requirement: Guardrail Decisions Are Counted, Including Fail-Open

Every guardrail decision SHALL increment a counter labelled by the rule that produced it, using the rule identifiers the code already returns. The case where the domain classifier raises and the guardrail admits the query anyway SHALL be counted separately from a normal admit, because it represents a security control degrading rather than passing.

#### Scenario: A blocked question increments its rule's counter

- **GIVEN** a question that the guardrail blocks as cross-tenant or as a personal-data query
- **WHEN** the guardrail counter is read
- **THEN** the counter for that rule SHALL have incremented

#### Scenario: A classifier failure is counted as fail-open, not as admit

- **GIVEN** the domain classifier raises an exception and the guardrail admits the query
- **WHEN** the guardrail counters are read
- **THEN** a dedicated fail-open counter SHALL have incremented
- **AND** the normal admit counter SHALL NOT be the only signal of what happened

#### Scenario: Empty-sources enforcement is counted

- **GIVEN** a request where source enforcement returns a fallback reply because no sources were present
- **WHEN** the guardrail counters are read
- **THEN** the counter for that rule SHALL have incremented

### Requirement: Entity Resolution Outcomes Are Recorded

Entity resolution SHALL record its outcome using the identifiers already defined in the resolver (`unresolved`, `unique`, `ambiguous`, `over_cap`) as a span attribute and as a counter label, together with the number of mentions checked. Mention text SHALL NOT appear in telemetry.

#### Scenario: Each resolution outcome is counted

- **GIVEN** a chat request whose entity resolution completes with any outcome
- **WHEN** the resolution span and counters are examined
- **THEN** the outcome SHALL be recorded as one of the defined identifiers
- **AND** the number of mentions checked SHALL be recorded
- **AND** no mention text SHALL appear in either

### Requirement: Extraction And Projection Instrumentation

The extraction pipeline SHALL emit, per document run, the stage reached, the duration of each stage, retry count, partial-failure count, pages processed, the model version used, and entity counts by entity type. The EAV-to-normalized projection SHALL emit its duration and a drift indicator. Entity values and document content SHALL NOT appear in any of it.

Entity type names are tenant-configured and therefore have no closed value set. They SHALL be recorded as span attributes and log fields, where they are already scoped by `tenant_id` and bounded by trace retention. They SHALL NOT be used as a metric label. Extraction counts exposed as metrics SHALL be aggregate and unlabelled by entity type; per-type detail is answered from spans.

#### Scenario: A completed extraction run reports its stages

- **GIVEN** a document is extracted successfully
- **WHEN** the run's spans and metrics are examined
- **THEN** each stage SHALL be represented with a duration
- **AND** pages processed, model version and per-type entity counts SHALL be recorded on the run's spans
- **AND** the metrics for that run SHALL record an aggregate entity count carrying no entity-type label

#### Scenario: A failed extraction run records where it failed

- **GIVEN** a document whose extraction fails partway through
- **WHEN** the run's spans and metrics are examined
- **THEN** the stage at which it failed SHALL be identifiable
- **AND** a failure counter labelled by exception class SHALL have incremented

#### Scenario: Projection reports duration and drift

- **GIVEN** an extraction write that triggers the EAV-to-normalized projection
- **WHEN** the projection span and metrics are examined
- **THEN** the projection duration SHALL be recorded
- **AND** a drift indicator SHALL be recorded distinguishing a clean projection from one where source and projected row counts disagree

#### Scenario: Entity values never appear in extraction telemetry

- **GIVEN** a document containing known seeded entity values is extracted
- **WHEN** every span attribute, metric label and log record from that run is collected
- **THEN** none SHALL contain a seeded entity value
- **AND** entity type names and counts MAY be present on spans and log records

#### Scenario: Entity type is never promoted to a metric label

- **GIVEN** a tenant that has configured entity types of its own naming
- **WHEN** the label sets of every metric family declared by this change are examined
- **THEN** none SHALL include an entity-type label
- **AND** the check SHALL fail if such a label is introduced, since tenant-configured type names are neither enumerable at declaration nor safe to expose in a store shared across tenants

### Requirement: Celery Queue Instrumentation

Both Celery queues SHALL report depth, task wait time, task execution duration, retry count, failure count labelled by exception class, and worker liveness.

#### Scenario: Queue depth is observable

- **GIVEN** tasks are enqueued faster than the workers consume them
- **WHEN** the queue depth metric is read
- **THEN** it SHALL report a non-zero depth for the affected queue

#### Scenario: Task wait time is distinguished from execution time

- **GIVEN** a task that waits in the queue before executing
- **WHEN** its metrics are examined
- **THEN** the time spent waiting SHALL be recorded separately from the time spent executing

#### Scenario: A failing task is counted by exception class

- **GIVEN** a task that raises
- **WHEN** the failure counter is read
- **THEN** it SHALL have incremented under a label naming the exception class
- **AND** the label SHALL NOT contain the exception message text

### Requirement: Model Serving Instrumentation

Model serving SHALL record inference duration, the number of windows or batches processed, model load and cold-start events, the active model version as a span attribute, rerank duration, and which inference path executed (tenant ONNX model or base model).

#### Scenario: An inference call records duration and path

- **GIVEN** an inference request for a tenant with a promoted model
- **WHEN** the inference span is examined
- **THEN** it SHALL record duration, the active model version, and that the tenant model path executed

#### Scenario: Base-model fallback is distinguishable

- **GIVEN** an inference request for a tenant with no promoted model
- **WHEN** the inference span is examined
- **THEN** it SHALL record that the base-model path executed

#### Scenario: Model load is recorded as an event

- **GIVEN** a tenant model is loaded into memory for the first time
- **WHEN** the spans and metrics are examined
- **THEN** a model-load event SHALL be recorded with its duration

### Requirement: Training Job Instrumentation

Training SHALL record job state transitions, total duration, epoch progress and failure cause. Model quality metrics SHALL remain in MLflow and SHALL NOT be duplicated as platform metrics.

#### Scenario: A job's lifecycle is observable

- **GIVEN** a training job runs to completion
- **WHEN** its metrics are examined
- **THEN** each state transition SHALL be recorded
- **AND** the total duration SHALL be recorded

#### Scenario: A failed job records its cause

- **GIVEN** a training job that fails
- **WHEN** its metrics are examined
- **THEN** a failure counter SHALL have incremented under an enumerated cause
- **AND** the job's final state SHALL be recorded

#### Scenario: Model quality metrics are not duplicated

- **GIVEN** a completed training job whose evaluation metrics were logged to MLflow
- **WHEN** the platform metric families are examined
- **THEN** no metric family SHALL expose F1, precision, recall or loss

### Requirement: LangSmith And OpenTelemetry Traces Are Correlated

Where a LangSmith run is created for an LLM interaction, the ambient OpenTelemetry trace identifier SHALL be attached to that run, and the LangSmith run identifier SHALL be attached to the corresponding span, so that either system leads to the other for the same unit of work. Absence or failure of LangSmith SHALL NOT affect the request path.

#### Scenario: A LangSmith run carries the OTel trace identifier

- **GIVEN** LangSmith tracing is enabled and a chat request makes an LLM call
- **WHEN** the LangSmith run for that call is retrieved
- **THEN** it SHALL carry the OpenTelemetry trace identifier of the originating request

#### Scenario: The span carries the LangSmith run identifier

- **GIVEN** the same request
- **WHEN** the corresponding span is retrieved
- **THEN** it SHALL carry the LangSmith run identifier as an attribute

#### Scenario: LangSmith being unavailable does not break the request

- **GIVEN** LangSmith is disabled or unreachable
- **WHEN** a chat request is handled
- **THEN** it SHALL be answered normally
- **AND** the OpenTelemetry spans SHALL still be emitted
