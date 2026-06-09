---
# QA Review Checklist
# Version: 1.0
#
# HOW THIS FILE IS USED
# The qa-reviewer skill loads this file at the start of every review session.
# Each item is evaluated against the delta spec scenarios, tasks.md acceptance
# criteria, and the original requirement documents.
#
# SEVERITY
#   BLOCKER → FAIL on this item forces overall verdict to FAIL
#   WARNING → FAIL on this item forces PASS WITH WARNINGS at most
#   INFO    → recorded but does not affect the verdict
#
# SECTIONS
# QA-SC  — Scenario Concreteness & Structure
# QA-HP  — Happy Path Coverage
# QA-FP  — Failure Path Coverage
# QA-EC  — Edge Cases & Boundary Conditions
# QA-PT  — Pattern-Specific Test Scenarios
# QA-AC  — Acceptance Criteria Quality
# QA-AV  — AC Executable Verification Policy
#         (policy: docs/workflow/acceptance-criteria.md)
# QA-TS  — Test Strategy Coverage
# QA-TD  — Test Data & State Assumptions
# QA-CC  — Concurrency & Race Condition Coverage
---

# QA Review Checklist

## Section QA-SC — Scenario Concreteness & Structure

> Verify that every GIVEN/WHEN/THEN scenario is structured correctly
> and specific enough to drive a test without guessing.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-SC-01 | BLOCKER | Every scenario follows the GIVEN/WHEN/THEN structure — no scenario uses freeform prose as a substitute. |
| QA-SC-02 | BLOCKER | Every GIVEN clause describes a specific, constructable precondition state — not a vague setup like "the system is running" or "the user exists". |
| QA-SC-03 | BLOCKER | Every WHEN clause describes a single, concrete action — not a compound action ("the user submits the form and the system validates it"). |
| QA-SC-04 | BLOCKER | Every THEN clause describes an observable, verifiable outcome — not an internal implementation detail ("the database row is updated") or a vague assertion ("the system works correctly"). |
| QA-SC-05 | BLOCKER | AND clauses in THEN are each individually verifiable — they are not bundled assertions that can only be checked together. |
| QA-SC-06 | WARNING | Scenarios are named distinctly enough to be referenced unambiguously in `tasks.md` acceptance criteria (e.g., "Scenario: Successful login" not "Scenario: Test 1"). |
| QA-SC-07 | WARNING | GIVEN clauses specify the relevant data values (e.g., "GIVEN a user with status 'active' and role 'admin'") — not just entity existence ("GIVEN a user exists"). |
| QA-SC-08 | WARNING | THEN clauses include the response or output characteristics that a test assertion would check (status code, field values, event published, log emitted). |
| QA-SC-09 | INFO | Each scenario tests exactly one behaviour — scenarios that verify multiple independent outcomes are split into separate, focused scenarios. |

## Section QA-HP — Happy Path Coverage

> Verify that every requirement has at least one scenario covering
> the primary success flow end-to-end.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-HP-01 | BLOCKER | Every ADDED or MODIFIED requirement has at least one scenario that exercises the full happy path from precondition to successful outcome. |
| QA-HP-02 | BLOCKER | No requirement has only failure or edge-case scenarios — the primary intended behaviour must also be covered. |
| QA-HP-03 | WARNING | Happy path scenarios cover all user roles that are permitted to perform the action (not just a generic "user"). |
| QA-HP-04 | WARNING | Happy path scenarios for write operations verify both the immediate response and the resulting system state (e.g., the entity is persisted, the event is published). |
| QA-HP-05 | INFO | Happy path scenarios for multi-step flows cover the complete journey, not just the final step in isolation. |

## Section QA-FP — Failure Path Coverage

> Verify that realistic failure modes are represented as scenarios
> so the system's error behaviour is specified and testable.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-FP-01 | BLOCKER | Every operation that calls an external dependency (DB, downstream service, message broker, cache) has at least one scenario covering transient failure of that dependency. |
| QA-FP-02 | BLOCKER | Every operation that calls an external dependency has at least one scenario covering permanent failure (e.g., downstream returns 404, DB constraint violation). |
| QA-FP-03 | BLOCKER | Every input validation rule has a scenario where the invalid input is submitted and the system's rejection response (status code, error message, field) is specified. |
| QA-FP-04 | BLOCKER | Every precondition that can be unmet at runtime (entity not found, wrong state, insufficient permissions) has a corresponding rejection scenario. |
| QA-FP-05 | WARNING | Transient failure scenarios specify what the system does after the failure: retry, fallback response, error returned to caller — not just "an error occurs". |
| QA-FP-06 | WARNING | Permanent failure scenarios specify the exact error response returned to the caller (HTTP status code, error code, error message shape). |
| QA-FP-07 | WARNING | Scenarios covering downstream unavailability do not assume the downstream is simply "down" — they distinguish slow response (timeout) from connection refused (fast failure). |
| QA-FP-08 | INFO | Failure scenarios for background processes (relay, saga, scheduler) cover the case where the process crashes mid-operation and resumes. |

## Section QA-EC — Edge Cases & Boundary Conditions

> Verify that boundary values, limit conditions, and unusual but
> valid inputs are covered by scenarios.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-EC-01 | BLOCKER | Every numeric or string field with a stated minimum or maximum has a scenario testing the value at exactly the boundary (not just comfortably within bounds). |
| QA-EC-02 | WARNING | Every enumerated field (status, type, role) has a scenario for an unrecognised or invalid enum value. |
| QA-EC-03 | WARNING | Empty collections, null values, and zero quantities are covered as scenarios for any operation that processes a list, nullable field, or numeric value. |
| QA-EC-04 | WARNING | Scenarios cover the case where an operation is performed on an entity that is in its terminal state (e.g., a cancelled order, a closed account) and cannot accept further transitions. |
| QA-EC-05 | WARNING | Date and time edge cases are covered where relevant: past dates, future dates, timezone differences, DST transitions, and epoch boundaries. |
| QA-EC-06 | WARNING | Scenarios cover extremely long input values (max-length strings, large payloads) to verify truncation or rejection behaviour is specified. |
| QA-EC-07 | INFO | Unicode and special character inputs are covered for any user-facing text field where the spec does not explicitly restrict character sets. |

## Section QA-PT — Pattern-Specific Test Scenarios

> Verify that every applied microservice pattern has the required
> failure and recovery scenarios. Only check patterns marked Applied
> in the Pattern Selection Log.

### Idempotency Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-ID-01 | BLOCKER | Scenario: first request with a new idempotency key is processed normally and a response is stored. |
| QA-PT-ID-02 | BLOCKER | Scenario: duplicate request with the same key within TTL returns the original response with no side effects (no DB write, no event published, no external call). |
| QA-PT-ID-03 | BLOCKER | Scenario: duplicate request after the key's TTL has expired is treated as a new request and processed normally. |
| QA-PT-ID-04 | WARNING | Scenario: two simultaneous first requests with the same key — only one is processed; the other receives the same response (race condition protection). |

### Retry Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-RT-01 | BLOCKER | Scenario: transient failure followed by success within retry count — the operation eventually succeeds. |
| QA-PT-RT-02 | BLOCKER | Scenario: all retries exhausted — the appropriate error is returned to the caller and no further attempts are made. |
| QA-PT-RT-03 | BLOCKER | Scenario: non-retryable error (e.g., 400, 403, 404) — no retry is attempted; the error is returned immediately. |
| QA-PT-RT-04 | WARNING | Scenario: retry succeeds after jittered backoff — the scenario verifies that the operation is not re-executed more than the configured count. |

### Circuit Breaker Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-CB-01 | BLOCKER | Scenario: N failures within window W — circuit opens and subsequent calls return the fallback without reaching the downstream. |
| QA-PT-CB-02 | BLOCKER | Scenario: open circuit receives a request — fallback is returned, downstream is not called, a circuit-open metric is emitted. |
| QA-PT-CB-03 | BLOCKER | Scenario: recovery window elapses, probe request succeeds — circuit closes and normal calls resume. |
| QA-PT-CB-04 | WARNING | Scenario: recovery window elapses, probe request fails — circuit remains open and the recovery window resets. |

### Outbox Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-OB-01 | BLOCKER | Scenario: DB write and outbox record are committed in the same transaction — if the transaction fails, no outbox record exists and no event is published. |
| QA-PT-OB-02 | BLOCKER | Scenario: relay publishes the outbox record to the broker and marks it published — it is not re-published on the next relay run. |
| QA-PT-OB-03 | BLOCKER | Scenario: application crashes after DB commit but before relay runs — relay picks up the unpublished record on restart and publishes it exactly once. |
| QA-PT-OB-04 | WARNING | Scenario: relay fails to get a broker ACK — the record is not marked published and will be retried on the next relay run. |
| QA-PT-OB-05 | WARNING | Scenario: consumer receives the same event twice (duplicate from relay retry) — consumer's idempotency guard prevents double-processing. |

### Saga Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-SA-01 | BLOCKER | Scenario: all saga steps complete successfully — final state is reached and all downstream services reflect the completed transaction. |
| QA-PT-SA-02 | BLOCKER | Scenario: a mid-saga step fails — compensating transactions execute in reverse order and the system returns to a consistent pre-saga state. |
| QA-PT-SA-03 | BLOCKER | Scenario: application restarts mid-saga — saga resumes from the correct step without re-executing completed steps. |
| QA-PT-SA-04 | WARNING | Scenario: a compensating transaction itself fails — the saga enters a dead-letter state and a manual intervention alert is triggered. |
| QA-PT-SA-05 | WARNING | Scenario: the same saga trigger event is received twice — the second invocation is idempotent and does not create a duplicate saga. |

### Cache Scenarios

| ID | Severity | Checklist Item |
|---|---|---|
| QA-PT-CA-01 | BLOCKER | Scenario: cache hit — data is returned without querying the DB; a cache-hit metric is emitted. |
| QA-PT-CA-02 | BLOCKER | Scenario: cache miss — DB is queried, result is cached, data is returned; a cache-miss metric is emitted. |
| QA-PT-CA-03 | BLOCKER | Scenario: cache is unavailable — system degrades to DB reads without returning an error to the caller. |
| QA-PT-CA-04 | BLOCKER | Scenario: data is written — the relevant cache entry is invalidated (or updated for write-through) before the response is returned. |
| QA-PT-CA-05 | WARNING | Scenario: cache entry TTL expires — the next read results in a cache miss and a fresh DB read, not an error. |

## Section QA-AC — Acceptance Criteria Quality

> Verify that each task's acceptance criteria is precise, binary,
> observable, and automatable.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-AC-01 | BLOCKER | Every task in `tasks.md` has at least one acceptance criterion. |
| QA-AC-02 | BLOCKER | Every acceptance criterion is binary — it can be evaluated as definitively PASS or FAIL with no subjective judgment required. |
| QA-AC-03 | BLOCKER | Every acceptance criterion is observable — it references a concrete, externally verifiable output (response body field, HTTP status, database row, event published, metric value, log entry). |
| QA-AC-04 | BLOCKER | Every functional task has at least one acceptance criterion that references a scenario from the delta spec (by name or requirement ID). |
| QA-AC-05 | WARNING | Acceptance criteria do not use vague language: "works correctly", "handles gracefully", "behaves as expected", "is fast" — these must be replaced with measurable conditions. |
| QA-AC-06 | WARNING | Acceptance criteria for pattern implementation tasks cover both the success path and at least one failure path (e.g., "cache miss correctly falls back to DB" not just "cache hit returns data"). |
| QA-AC-07 | WARNING | Every acceptance criterion for an integration with an external system specifies the test double strategy (mock, stub, test container, or real service in test environment). |
| QA-AC-08 | INFO | Acceptance criteria are ordered from simplest to most complex within each task so the agent can verify incrementally. |

## Section QA-AV — AC Executable Verification Policy

> Enforces the AC Verification Policy defined in
> `docs/workflow/acceptance-criteria.md`. Every AC in every `spec.md`
> (and every AC entry in `tasks.md`) must have at least one executable
> verification artifact that fails when the AC's `THEN` clause is
> violated. Unverified ACs are BLOCKERS regardless of how complete the
> rest of the spec is.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-AV-01 | BLOCKER | Every AC in `tasks.md` names at least one verification artifact — test file path AND specific test case name. "Tests will cover this" / "see test suite" / missing field = FAIL. |
| QA-AV-02 | BLOCKER | Every named verification artifact is automatically executable — it runs as part of the project's standard test command (`PROJECT.md` section 10) without interactive input, manual fixtures outside source control, or developer-only steps. |
| QA-AV-03 | BLOCKER | Every AC's verification artifact has a "Must fail if" note that describes a mutation of the `THEN` clause the artifact would detect. Absence of this note means we cannot confirm the artifact fails on violation — FAIL. |
| QA-AV-04 | BLOCKER | The chosen verification layer can actually observe the AC's `THEN` clause. Example FAIL: an AC whose THEN asserts "a row is written to Postgres" verified by a unit test that mocks the repository. |
| QA-AV-05 | BLOCKER | For ACs whose `THEN` asserts an externally observable contract (HTTP response shape, event payload, gRPC message), a contract test is used — not only a unit/integration test. |
| QA-AV-06 | WARNING | Verification artifacts are named using the AC's `GIVEN / WHEN / THEN` (e.g., `given_insufficient_balance_when_withdraw_then_rejected`) so artifact–AC traceability is self-evident. |
| QA-AV-07 | WARNING | Verification artifacts exercise the AC exactly — no broader (no smuggled-in extra invariants) and no narrower (no skipping the `THEN`). |
| QA-AV-08 | WARNING | For ACs involving concurrency or ordering (saga resume, outbox relay, idempotency race), the verification artifact reproduces the concurrency condition (not a sequential approximation). |
| QA-AV-09 | INFO | Where the project supports mutation testing, the AC's verification artifact is part of the mutation-tested set — strong evidence the artifact fails on `THEN` violation. |

## Section QA-TS — Test Strategy Coverage

> Verify that the spec supports a complete, appropriately layered
> test suite and that the required test layers are identified.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-TS-01 | BLOCKER | Unit test tasks exist for all business logic, domain rules, and validation rules that can be tested without infrastructure dependencies. |
| QA-TS-02 | BLOCKER | Integration test tasks exist for all DB interactions, cache interactions, message broker interactions, and external API calls. |
| QA-TS-03 | BLOCKER | Contract test tasks exist for all new or modified API endpoints and event schemas that are consumed by other services. |
| QA-TS-04 | WARNING | E2E test tasks exist for the primary happy path of any user-facing feature (if the project has an E2E test suite). |
| QA-TS-05 | WARNING | Test tasks are ordered after their corresponding implementation tasks — no test task precedes the code it tests. |
| QA-TS-06 | WARNING | Pattern implementation tasks (Outbox, Saga, Circuit Breaker, Cache) each have a dedicated test task that specifically covers the pattern's failure mode, not just the happy path. |
| QA-TS-07 | INFO | Performance or load test tasks are present for any feature with an explicit NFR latency or throughput target. |

## Section QA-TD — Test Data & State Assumptions

> Verify that GIVEN clauses are specific enough for a test engineer
> to construct the required test data and system state without guessing.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-TD-01 | BLOCKER | GIVEN clauses that reference an entity (e.g., "a user") specify the entity's relevant attributes for the scenario (status, role, relevant field values) — not just its existence. |
| QA-TD-02 | WARNING | GIVEN clauses that reference a count or quantity (e.g., "3 failed attempts") specify the exact value, not a vague qualifier ("several", "multiple"). |
| QA-TD-03 | WARNING | GIVEN clauses that reference time (e.g., "within the TTL", "30 days ago") specify the time relationship precisely enough to construct in a test. |
| QA-TD-04 | WARNING | GIVEN clauses do not reference test infrastructure specifics ("given the Redis server is restarted") — they describe system state ("given the cache is empty for key K"). |
| QA-TD-05 | INFO | Where test data setup is complex (multi-entity state, specific event history), the scenario notes that a factory or fixture is expected — this is reflected in the test task. |

## Section QA-CC — Concurrency & Race Condition Coverage

> Verify that concurrent execution scenarios are present for operations
> that are vulnerable to race conditions.

| ID | Severity | Checklist Item |
|---|---|---|
| QA-CC-01 | BLOCKER | Any operation that reads-then-writes a shared resource (check-then-act pattern) has a scenario covering two concurrent requests racing to update the same record. |
| QA-CC-02 | BLOCKER | Idempotency key storage is covered by a concurrent-first-request scenario (two requests with the same key arriving simultaneously before either is stored). |
| QA-CC-03 | WARNING | Saga compensation scenarios cover the case where a compensating transaction races with an already-in-flight forward step. |
| QA-CC-04 | WARNING | Cache invalidation scenarios cover the case where a write invalidates a key while a concurrent read is repopulating it (stale-put prevention). |
| QA-CC-05 | INFO | Optimistic locking conflict scenarios (version mismatch on update) are covered where the data model uses optimistic concurrency. |

---

## Verdict Calculation

| Condition | Verdict |
|---|---|
| Any BLOCKER item status is FAIL | **FAIL** |
| One or more WARNING items status is FAIL, no BLOCKER failures | **PASS WITH WARNINGS** |
| All BLOCKER and WARNING items status is PASS | **PASS** |

Pattern-specific sections (QA-PT-*) only apply when the corresponding
pattern is marked Applied in the Pattern Selection Log. Skip the entire
sub-section if the pattern is Not applicable or Already in place with
no new code required.

---

## Customisation Notes

- Add project-specific scenario requirements under a new QA-PR section.
- Adjust QA-TS items to reflect your project's actual test layers.
- Disable QA-CC items if the service is single-threaded by design.
- Add QA-PT sub-sections for any additional patterns your project uses.
