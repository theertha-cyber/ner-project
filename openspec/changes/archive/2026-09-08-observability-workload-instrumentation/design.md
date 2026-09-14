## Context

`observability-foundation` shipped the mechanism: `src/shared/observability/` with `init_observability(service_name)` called by all ten processes, `contextvars` carrying `request_id`/`tenant_id`/`user_hash`/`trace_id`, JSON logs with an unconditional redaction filter, auto-instrumented spans for FastAPI, SQLAlchemy, asyncpg, httpx, redis and Celery, and RED metrics on `/metrics` with OTLP export for the two workers.

What it did not ship is any signal about what this platform does. Today a slow chat answer is one span tree of HTTP and SQL durations. It cannot distinguish a slow retrieval from a SQL generator that ran three attempts, and nothing anywhere counts the second case.

The relevant current state, confirmed in the code rather than assumed:

- `src/chat_api/services/sql_generator.py` already models the loop precisely — `SQLAttemptOutcome` is a closed set of five values, `SQLAttempt` carries `attempt`, `max_attempts`, `outcome`, `row_count`, `defect`, and `SQLGenerationFailed` carries a `reason`. The deadline branch at line 1645 already logs `"reason": "deadline_exhausted"`. None of it is counted.
- `SQLAttempt.defect` carries its evidence inline — `filename:<literal>`, `scope:<relations>` — where the literal is drawn from tenant data. `_defect_class()` at line 183 already exists to strip the payload from the prefix. A metric labelled by the raw `defect` field would put extracted resume content into Prometheus.
- `src/chat_api/services/entity_resolver.py` defines `UNRESOLVED`, `UNIQUE`, `AMBIGUOUS`, `OVER_CAP` as module constants and already passes `mentions_checked` around. Nothing counts them.
- `src/chat_api/services/guardrails.py:102-107` catches every classifier exception, logs `outcome=fail_open_admitted` at one call site, and admits the query. `classify_domain` runs two classifications and admits on a split. No counter reads any of it.
- `src/gateway/dependencies.py:60` raises `TenantMismatchError()` — one raise site, no counter.
- Nine call sites build a search path by f-string interpolation: `SET search_path TO {schema}` in `sql_generator.py` (five), `analytics_service/dependencies.py`, `analytics_service/worker.py`, `extraction_service/dependencies.py`, `shared/tenant_context.py`. Nothing asserts the interpolated value's shape. (Counted as eight in an earlier draft, which listed all nine and then summed them wrong.)
- `langsmith.wrappers.wrap_openai` is used in `rag_orchestrator.py` and `sql_generator.py`. LangSmith runs and OTel traces are two disconnected systems for the same LLM call.
- `src/model_serving/services/inference_service.py:354` already branches ONNX-versus-base and falls back to base on error at line 366. The branch taken is invisible.
- `src/training_service/worker.py` writes evaluation metrics to MLflow at lines 314-322. MLflow is the source of truth for model quality and stays so.

Constraints shaping the design:

- ADR-001 makes telemetry a place tenant data must not accumulate. This change adds far more fields than the foundation did, several of them one derivation away from tenant content.
- Prometheus label cardinality is multiplicative. Every enumerated label added here multiplies against every other one on the same family.
- The production cluster still does not exist. Everything here must be verifiable on the local stack the foundation change added.
- Sprint capacity is one developer, and instrumentation touches four workloads across ten processes.

## Goals / Non-Goals

**Goals:**

- Each of the four workloads reports the shape of its own work: chat and retrieval, extraction and projection, model serving, training.
- The Phase 1 repair-loop claim becomes a measured quantity — attempts, repair depth, defect class, abandon reason — rather than a hand-run question suite.
- The security signals Exit Gate 3 names exist as counters: tenant mismatch, search-path violation, auth failure by reason, rate-limit rejection.
- One enumerated allowlist governs which metric families may carry `tenant_id`, enforced by a test rather than by review.
- An automated release-gate scan that fails the build on seeded entity values or personal-data patterns in captured telemetry, and fails on an empty capture.
- LangSmith runs and OTel spans reachable from each other in one hop.

**Non-Goals:**

- Dashboards, alert rules, runbooks, SLOs — story 5.1 consumes what is defined here.
- Production backends on the cluster — story 4.5.
- Changing any behaviour being measured. The guardrail fail-open stays open, the search-path assertion counts rather than raises, rate-limit policy is untouched. This change measures; the decisions the measurements inform belong to their own changes.
- Per-tenant quotas, billing, log retention, Mimir, Pyroscope.
- Replacing MLflow as the store for model quality metrics.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Schema-per-tenant `tenant_<uuid>`; isolation explicitly extends to logs and indexes | Every attribute and label added here is a candidate leak. Enumerated values only; derived counts and category names, never the data they were derived from. The search-path assertion exists because this ADR's boundary is enforced by a string interpolation today. |
| ADR-003 Per-Tenant Model Serving Topology | Version-pinned per-tenant serving, base-model fallback | Model-serving telemetry must carry the active version and distinguish the tenant-ONNX path from the base-model path, since "which model answered" is not derivable from the service name. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every change traceable from intent to evidence | Acceptance criteria map to executable checks in `verification.md`; the release-gate scan is itself the evidence artifact Exit Gate 3 names. |
| ADR-005 OpenCode Agent Permissions and Boundaries | Bounded agent roles | No constraint beyond normal review. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation enforcement, P95 < 10s monitored | The foundation supplied the request-duration histogram. This change supplies the stage breakdown that makes a P95 breach diagnosable rather than merely visible. Citation enforcement becomes counted, not just executed. |
| ADR-008 Base Model as Default Inference Model (Version 0) | Base model answers when no tenant model is promoted; supersedes ADR-002's 404 behaviour | Base-model inference is a normal path, not an error path. Its telemetry must be a distinguishable success, not a fallback counted as a failure. |
| ADR-009 System Admin Sets Training Hyperparameters at Approval | Hyperparameters set at approval; supersedes that clause of ADR-006 | Training job telemetry keys off the approved job record, not off a request payload. |
| ADR-010 Dataset Readiness Measured Per Entity Type | Per-entity-type thresholds; supersedes ADR-006's two threshold clauses | Extraction entity counts are reported per entity type on spans, which is the granularity readiness is already measured at. Metrics carry an aggregate count only — see Decision 12. |

ADR-002 is superseded by ADR-008 for default inference behaviour and is historical context only. ADR-006 remains in force except for the clauses ADR-009 and ADR-010 replace.

## Decisions

### Decision 1: One declared registry of domain metrics, not `create_counter` at call sites

**Choice:** `src/shared/observability/domain_metrics.py` declares every metric family this change introduces — name, type, description, exact label keys, and the enumerated value set for each label — as module-level definitions. Call sites import a named recorder (`record_sql_attempt(...)`, `record_guardrail_decision(...)`) and pass typed arguments. No call site constructs a metric or invents a label.

**Rationale:** The allowlist requirement is not satisfiable without a place to enumerate. A test can only assert "no family outside the list carries `tenant_id`" if the set of families is enumerable by import rather than discoverable by running every code path. The same declaration is what lets a test assert that a label value is drawn from a closed set, which is the cardinality control that actually matters — an unbounded label value is the failure mode, not an unbounded family count.

It also makes the redaction problem tractable. Fifty scattered `create_counter` calls are fifty places a `filename:<literal>` can become a label. One module is one review surface.

**Alternatives considered:**
- OTel meter obtained per module, metrics created at first use — ruled out; this is the convention approach, and the foundation design already documents where conventions led in this repository (eight divergent `tenant_context.py` files).
- A registry that accepts arbitrary label dicts with a runtime denylist — ruled out; a denylist catches the names you thought of. The declared-labels approach makes an undeclared label a `TypeError` at the call site instead.

### Decision 2: Label values are derived categories, never the underlying field

**Choice:** Every label value passed to a recorder is either a module constant already defined in the code being measured, or a category function that strips payload. `SQLAttempt.defect` is labelled through the existing `_defect_class()`. Exception labels carry `type(e).__name__`, never `str(e)`. LLM errors carry an enumerated error class, never the provider's message.

**Rationale:** This is the single highest-risk aspect of the change and it is not hypothetical. `defect` is documented in `sql_generator.py` as carrying evidence inline, and one of those payloads is a filename literal drawn from a tenant document. Labelling it directly would place tenant content in Prometheus, where retention is long, access is broad and there is no redaction filter — the foundation's logging filter does not sit on the metrics path at all.

Reusing the code's own constants rather than writing new string literals also means a rename in `entity_resolver.py` or `SQLAttemptOutcome` breaks the import rather than silently emitting a stale label value that no dashboard matches.

**Alternatives considered:**
- Hash unbounded values into a bounded space — ruled out; a hashed label is unreadable on a dashboard and still unbounded in cardinality.
- Put the raw defect on the span and only the class on the metric — ruled out for the payload-carrying defects specifically. Spans are exported to the same collector and the personal-data scan covers span attributes, so the distinction buys nothing and costs a scan failure. The attempt *number* and outcome go on the span; the payload goes nowhere.

### Decision 3: Instrument the service layer, not the graph nodes

**Choice:** Spans and metrics are added inside the service functions that do the work — `sql_generator`, `entity_resolver`, `guardrails`, the retrieval modules, `inference_service` — rather than as wrappers in `src/chat_api/graph/nodes.py`.

**Rationale:** The node layer sees inputs and outputs; it does not see the attempt loop, the fallback branch or the classifier exception, which is exactly the information missing today. Instrumenting at the node boundary would produce a second copy of the durations auto-instrumentation already reports and none of the interior detail.

The node layer still gets one span per node for the stage-per-request requirement, but it carries the node's outcome only, not a duplicate of the service's measurements.

**Alternatives considered:**
- A decorator applied to node functions — ruled out; uniform and cheap, and blind to everything that matters.
- LangGraph callbacks — ruled out; couples the platform's telemetry contract to a framework's callback surface, and the extraction, serving and training workloads have no graph at all, so it would solve one quarter of the problem with a mechanism the other three cannot use.

### Decision 4: `TenantMismatchError` counts itself

**Choice:** The counter increments in `TenantMismatchError.__init__` in `src/shared/exceptions.py`, not at the raise site in `src/gateway/dependencies.py:60`.

**Rationale:** There is one raise site today. The value of this counter is entirely about the sites that do not exist yet — a new service, a new dependency, a new authorization path. A counter at the raise site is a convention the next author must remember; a counter in the constructor cannot be raised without being counted.

The exception module currently imports nothing from observability, so the increment is guarded and the import is local to the function, keeping `exceptions.py` importable in contexts where observability is not initialised.

**Alternatives considered:**
- Increment at the raise site — ruled out on the reasoning above.
- Increment in a FastAPI exception handler — ruled out; it counts only mismatches that reach a handler, and misses any raised outside a request scope or swallowed by intermediate code.

### Decision 5: Search-path assertion is a shared helper that counts and logs, and does not raise

**Choice:** `assert_tenant_schema(schema, code_path)` in the observability module validates against `^tenant_[0-9A-Za-z_-]{1,56}$`, increments a violation counter and logs at ERROR on mismatch, and returns. It is called immediately before each of the nine `SET search_path TO {schema}` interpolations. The logged schema value is truncated and character-restricted so a violating value cannot itself inject into the log record.

**Pattern corrected during implementation.** This decision originally specified `^tenant_[0-9a-f-]+$`, which assumes a schema is `tenant_` plus a raw hyphenated UUID. The codebase produces no such name and never has: every one of the ~20 `_schema()` helpers renders `f"tenant_{tenant_id.replace('-', '_')}"`, so a live schema is `tenant_3f2a1b4c_9d8e_4f10_a1b2_c3d4e5f60718`, and the test fixtures seed slug-named schemas (`tenant_test_tenant`, `tenant_no_model`). The hex-and-hyphen pattern therefore rejects **100% of legitimate schemas** — it would fire the violation counter and an ERROR record on every query the platform serves, burying the one real violation in millions of false ones. A counter that always fires is not a signal, which defeats the entire purpose of this decision.

The widened pattern enforces the property the assertion actually exists for: the `tenant_` prefix plus identifier-safe characters only, bounded at 56 characters so the whole name stays inside Postgres's 63-character identifier limit. That is what stops a value interpolated into `SET search_path TO {schema}` from carrying SQL structure. It still rejects `public`, `public; DROP SCHEMA tenant_a CASCADE` and `tenant_a"; --`, which are the shapes that matter. What it gives up relative to the original is the assertion that a schema names a *well-formed UUID* — a stricter claim than tenant isolation needs here, and one no current caller could satisfy.

Tightening this back toward a UUID shape is worth revisiting only alongside a change that makes schema naming uniform; today `shared/tenant_context.py` builds `f"tenant_{tenant_id}"` without the underscore substitution every other site applies, so the platform does not agree with itself on the format yet.

**Rationale:** These eight sites interpolate a value into SQL. If any caller ever supplies something unexpected, today nothing notices. A counter that fires is the evidence Exit Gate 3 asks for, and it can be added to every site in one commit with zero behavioural risk.

Raising is the right end state and the wrong step now. Converting an interpolation site into a hard failure changes the query path's behaviour under conditions we currently have no data about — we would be choosing a failure mode blind. Measure first, then decide with a non-zero or zero counter in hand. The proposal flags this and it stays flagged.

**Alternatives considered:**
- Raise immediately — ruled out above; it is a behavioural change smuggled into an instrumentation change.
- Parameterise the search path instead of asserting — ruled out as out of scope, and Postgres does not accept `SET search_path` as a bound parameter anyway; the fix is an identifier-quoting change with its own testing burden.
- Assert once in a shared session helper — ruled out; three of the eight sites do not go through `shared/tenant_context.py`, so a single choke point would cover five and give false confidence about the other three.

### Decision 6: Celery queue depth is reported by one owner, not by every worker

**Choice:** Queue depth is a pull-time observable gauge that reads the broker's list length for the two configured queues, registered in the service that owns each queue's producer side, not in the worker processes.

**Rationale:** Depth is a property of the queue, not of a worker. Every worker reporting it would produce N identical series differing only by instance, and a dashboard would then have to pick one arbitrarily or sum them into a number that means nothing. Wait time and execution duration are per-task and stay in the worker, where the task actually runs.

Reading at scrape time rather than on a timer follows the pattern the foundation already established for `DatabasePoolCollector`: occupancy is only true at the instant it is read.

**Alternatives considered:**
- Every worker reports depth — ruled out on duplicate series.
- A separate exporter sidecar — ruled out; a container to read one Redis list length is not proportionate, and it would be a new deployment unit to carry to the cluster.

### Decision 7: Task wait time comes from the enqueue timestamp on the message, not from a broker query

**Choice:** The Celery header hook the foundation added for correlation also stamps an enqueue timestamp. `task_prerun` computes wait time as the difference against it.

**Rationale:** The hook already exists and already writes headers, so this is a field, not a mechanism. Deriving wait time any other way requires the broker to tell us when the message arrived, which Redis does not.

Clock skew between the enqueuing service and the worker is the known weakness. Both run in the same compose stack locally and will run in one cluster in production, so skew is bounded by NTP; the metric is a distribution used for "is the queue backing up", not a precise per-task figure. A negative computed wait is clamped to zero and counted, so skew becomes visible rather than silently distorting the histogram.

**Alternatives considered:**
- `task_received` minus `task_published` from Celery's own events — ruled out; requires the events subsystem enabled and a consumer process, both of which are new operational surface.

### Decision 8: LangSmith correlation is metadata in both directions, isolated from the request path

**Choice:** At the two `wrap_openai` sites, the ambient OTel trace id is attached to the LangSmith run as metadata, and the LangSmith run id is set as a span attribute on the enclosing span. Both operations are wrapped so that any failure — LangSmith disabled, unreachable, SDK change — logs at DEBUG and is dropped.

**Rationale:** These are two views of the same LLM call, and the reason the correlation is worth building is that the interesting failures need both: LangSmith holds the prompt and completion, OTel holds where the call sat in a ten-process request. One click apart is the whole requirement.

Isolation is not optional. LangSmith is configured by bare environment variables read directly by its SDK (`.env.example:69-74`), it is off by default, and it is a third-party network dependency. It must never be able to fail a chat request.

**Alternatives considered:**
- Export LangSmith runs into the collector as spans — ruled out; duplicates a system that already stores them, and the value is the link, not a second copy.
- Use the trace id as the LangSmith run id — ruled out; not the SDK's identifier to assign, and a trace covers many runs.

### Decision 9: Training reports lifecycle only; model quality stays in MLflow

**Choice:** Platform metrics carry job state transitions, total duration, epoch progress and an enumerated failure cause. F1, precision, recall and loss are not mirrored. A test asserts no metric family exposes them.

**Rationale:** `worker.py` already logs evaluation metrics to MLflow, which is the system built for model quality — it versions them against the run, the params and the artifact. Mirroring into Prometheus creates a second source of truth with worse fidelity, no run linkage and a retention window that will disagree. "Is the job stuck or failing" is an operational question and belongs in metrics; "is this model good" is an experiment question and belongs in MLflow.

The test exists because this is exactly the boundary that erodes — the first dashboard request for "show me F1 over time" is what breaks it, and it should break with a failing build and a deliberate decision.

**Alternatives considered:**
- Mirror everything for one-pane-of-glass dashboards — ruled out on two-sources-of-truth grounds; the dashboard can link to MLflow.

### Decision 10: The allowlist is five families, enforced against the live registry

**Choice:** `TENANT_LABEL_ALLOWLIST` is an explicit frozenset naming five families: chat request count, LLM tokens, LLM cost, extraction jobs, rate-limit rejections. The enforcement test imports the declarations, walks every registered family, and fails naming any family carrying `tenant_id` that is not listed. No prefix, no pattern, no wildcard.

**Rationale:** The foundation deliberately shipped zero tenant labels and deferred this list here. Per-tenant consumption attribution is the one need that genuinely requires the label — it is what Exit Gate 3 means by attribution and what billing will eventually read. Everything else can be answered by joining a trace, where `tenant_id` already lives and access is narrower.

A pattern-based rule would be the same mistake at one remove: `ner_llm_*` admits families nobody reviewed. Explicit enumeration makes growth a diff.

**Alternatives considered:**
- Zero labels, attribution via traces only — ruled out; trace sampling makes consumption figures wrong by construction, and consumption must be exact.
- Label by tenant broadly and control cost with recording rules — ruled out; the disclosure concern is unaffected by aggregation, since the raw series still exist and are readable.

### Decision 11: The release-gate scan drives the real stack and treats an empty capture as failure

**Choice:** A script under `scripts/` seeds a tenant with known sentinel entity values, drives one chat request and one extraction end to end against the running compose stack, then queries Loki, Tempo and Prometheus for the resulting telemetry and fails on any sentinel match, any personal-data pattern match, or a capture below a minimum expected record count.

**Rationale:** The leak this guards against occurs in the exporters and the formatters, not in the application's own data structures. A lighter harness that asserts on in-memory records would pass while the OTLP log handler ships an unredacted attribute — which is precisely the class of gap the foundation change found late (its task 3.5: Loki provisioned, receiving nothing, no scenario covering delivery).

The empty-capture rule follows directly. A scan that queries three backends and reports clean because export was misconfigured is worse than no scan, because it produces evidence for a gate.

**Alternatives considered:**
- Unit-level assertions on captured records — ruled out above; kept as fast tests, not as the gate.
- Scan only logs — ruled out by the spec; span attributes and metric labels are where this change adds the most new surface.

### Decision 12: Entity type is a span attribute, never a metric label

**Choice:** Extraction records entity counts per type on spans and log records. Metrics carry an aggregate entity count with no entity-type label. A test asserts no declared family carries one.

**Rationale:** Entity types are tenant-configured — `src/gateway/api/v1/entity_types.py` exposes `list_entity_types(tenant_id)`, and Section 3 of the execution plan makes tenant-defined fields the reason the EAV store exists at all. That breaks two commitments this design already made. Decision 2 requires every label value to be a module constant or a category function; a tenant-authored string is neither. The cardinality mitigation requires each label's value set to be enumerable at declaration so series counts are computable before shipping; a tenant-defined set is not enumerable at all.

There is a disclosure problem underneath the cardinality one. A tenant that configures `policy_holder` and `claim_number` is identifiable from label values alone, in a store shared across tenants with no redaction on the metrics path. That routes around the tenant-label allowlist rather than violating it, which makes it the harder failure to notice.

Spans carry the same names safely: they are already scoped by `tenant_id`, bounded by trace retention rather than kept for a year, and covered by the release-gate scan. ADR-010's per-entity-type granularity is preserved where it is actually queried.

**Alternatives considered:**
- Label the metric by type and cap the number of distinct values — ruled out; a cap silently drops the long tail, and the tail is exactly where an unusual tenant configuration shows up.
- Hash the type name into a bounded space — ruled out for the same reason as in Decision 2: unreadable on a dashboard, and a stable hash still fingerprints the tenant.
- Emit one metric family per entity type — ruled out; it moves unbounded cardinality from label values into family names, which is worse.

## Risks / Trade-offs

- [A label value derived from tenant data reaches Prometheus, where the foundation's redaction filter does not apply] → Declared label enumerations in one module (Decision 1), category functions rather than raw fields (Decision 2), and the release-gate scan covering metric labels explicitly (Decision 11). The `defect` field is the known live instance and is handled through the existing `_defect_class()`.
- [Cardinality growth across four workloads makes the metrics endpoint expensive or the backend unstable] → Every label's value set is enumerated at declaration, so the series count per family is computable before shipping rather than discovered in production. A test asserts each declared label's enumeration is finite and non-empty.
- [Per-stage spans on the chat path add latency to the platform's slowest request type] → Spans are created at stage boundaries, not per attempt-internal step; export stays asynchronous as the foundation established. Chat request duration is measured on the local stack before and after and recorded in `verification.md`.
- [Instrumentation drifts from the code it measures — an outcome is renamed and a dashboard silently goes blank] → Recorders take the code's own module constants, so a rename is an import error. The declarations module imports from the measured modules, not the reverse.
- [The release-gate scan is slow and flaky in CI, and someone disables it] → It runs as a separate job against the compose stack rather than inline with unit tests, and the empty-capture rule means a broken run fails rather than passes quietly, so disabling it is a visible act rather than a silent degradation.
- [The guardrail keeps failing open, now with a counter that makes it look handled] → The counter is deliberately separate from the admit counter so a fail-open cannot hide inside a normal admit. This change measures only; the decision it enables is flagged in Open Questions and belongs to its own change.
- [The search-path assertion counts violations nobody watches until story 5.1 builds alerts] → Violations also log at ERROR, which the foundation's pipeline already delivers to Loki, so the signal exists before the alert does.
- [Four workloads across ten processes is a wide change for one developer] → The declarations module lands first with its allowlist test, then one workload per commit; each workload's tests are independently green, and an incomplete change still leaves the platform strictly better instrumented than before.
- [Clock skew distorts Celery wait time] → Negative waits clamp to zero and increment a skew counter, making the distortion visible (Decision 7).

## Migration Plan

1. `src/shared/observability/domain_metrics.py`: declarations, recorders, `TENANT_LABEL_ALLOWLIST`, and `assert_tenant_schema`. No call sites. Land the allowlist enforcement test and the label-enumeration test with it, so every later step is gated by them.
2. Tenant-safety call sites: the counter in `TenantMismatchError.__init__`, `assert_tenant_schema` at all eight interpolation sites, auth-failure reasons, the rate-limiter rejection counter. Smallest diff, highest gate value, no behavioural change.
3. Chat path, in dependency order: guardrails, entity resolution, catalogue slice, retrieval and rerank, SQL generation and execution, LLM usage, answer composition.
4. Extraction and projection, then the Celery queue metrics for both queues.
5. Model serving, then training.
6. LangSmith correlation at the two `wrap_openai` sites.
7. The release-gate scan script, verified once by reintroducing a leak deliberately and confirming it fails, then wired into CI.

**Rollback:** Every step is additive. Steps 3-6 revert per workload with no cross-dependency. The foundation's `otlp_endpoint`-empty kill switch still disables all export without a code change; it does not disable `/metrics`, so if a specific family proves too expensive, removing its declaration and its recorder call is a two-file revert. Step 2's assertion never raises, so it cannot break a query path on rollout.

## Open Questions

- The five allowlist members. Assumption: chat requests, LLM tokens, LLM cost, extraction jobs, rate-limit rejections. Changed only by amending the enumerated list under review.
- Whether the release-gate scan blocks merge or blocks release. Assumption: blocks merge to `main`, since a leak merged is a leak in every later branch. Needs confirming against CI runtime once the scan's real duration is known.
- Whether the search-path assertion should raise. Assumption: count and log in this change; converting it is a behavioural change and belongs to its own. Revisit once the counter has run long enough to show whether it ever fires.
- Whether `guardrails.py` should keep failing open once measured. Assumption: unchanged here. Flagged because a silently degrading security control is a risk the counter reveals rather than fixes.
- Whether chat spans should carry `tenant_id` as an attribute at every stage or only at the request root. Assumption: root only, inherited by query on trace id, to keep per-span attribute weight down. Revisit if trace queries prove awkward in Grafana.
- Resolved during artifact review, previously open: whether entity counts by type should be a metric labelled by entity type. They must not be — see Decision 12. Per-type detail lives on spans; metrics carry an aggregate count only.
- No in-force ADR needs revisiting. ADR-007's P95 monitoring obligation is progressively satisfied — histogram in the foundation, stage breakdown here, alert in story 5.1 — and needs no superseding ADR.
