# Verification Plan

**Change:** confidence-routed-review
**Generated:** 2026-09-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | Post-processing confidence filtering | Low-confidence entities are filtered out | Given a threshold of 0.50, when extraction runs on text producing an entity at confidence 0.30, then that entity does not appear in the results | `tests/test_extract_confidence_threshold.py` (existing regression suite) | - [x] |
| 2 | extraction-service | Post-processing confidence filtering | Low-confidence entities are retained for routing | Given a threshold of 0.50 and a prediction at 0.30, when extraction runs, then the prediction is retained with type, value, confidence, offsets and model version, and is available to routing | `tests/test_extraction_confidence_filtering.py::test_below_threshold_predictions_retained` | - [x] |
| 3 | extraction-service | Post-processing confidence filtering | Retaining predictions does not change what business consumers see | Given a run executed with routing disabled and with routing enabled, when a business consumer queries entities, then both return the same entities and no routing-store record appears in either | `tests/test_extraction_confidence_filtering.py::test_retained_predictions_hidden_from_consumers` | - [x] |
| 4 | confidence-routed-review | Confidence-Based Routing | High-confidence prediction is auto-accepted | Given a review threshold of 0.90 and a prediction at 0.95, when routing runs, then it is recorded auto-accepted and does not appear in the review queue | `tests/test_confidence_routing.py::test_high_confidence_auto_accepted` | - [x] |
| 5 | confidence-routed-review | Confidence-Based Routing | Low-confidence prediction enters the review queue | Given a review threshold of 0.90 and a prediction at 0.62, when routing runs, then it appears in the review queue with recorded confidence 0.62 | `tests/test_confidence_routing.py::test_low_confidence_enters_queue` | - [x] |
| 6 | confidence-routed-review | Confidence-Based Routing | Review threshold is independent of the extraction threshold | Given extraction threshold 0.50 and review threshold 0.90, when the review threshold changes to 0.80, then the extraction threshold stays 0.50 and business-facing results are unchanged | `tests/test_confidence_routing.py::test_review_threshold_independent` | - [x] |
| 7 | confidence-routed-review | Confidence-Based Routing | Routed predictions record the serving model version | Given an extraction run served by tenant model version 3, when routing runs, then every routed prediction records model version 3 | `tests/test_confidence_routing.py::test_routed_predictions_record_model_version` | - [x] |
| 8 | confidence-routed-review | Review Queue Resolution | Human reviewer confirms a queued prediction | Given a queued prediction of type `organization` at 45-53, when a human confirms it as-is, then the outcome is recorded confirmed with the human route | `tests/test_review_queue.py::test_human_confirms_prediction` | - [x] |
| 9 | confidence-routed-review | Review Queue Resolution | Human reviewer corrects the offsets of a queued prediction | Given a queued prediction at 45-53, when a human corrects it to 45-58, then the outcome is recorded corrected with offsets 45-58 | `tests/test_review_queue.py::test_human_corrects_offsets` | - [x] |
| 10 | confidence-routed-review | Review Queue Resolution | Reviewer rejects a queued prediction | Given a queued prediction judged not an entity, when the reviewer rejects it, then the outcome is recorded rejected and no confirmed span is created | `tests/test_review_queue.py::test_reviewer_rejects_prediction` | - [x] |
| 11 | confidence-routed-review | Review Queue Resolution | LLM review produces the same outcome structure | Given a tenant policy routing to the LLM, when the LLM review job resolves a prediction, then the outcome is confirmed, corrected or rejected and records the LLM route | `tests/test_review_queue.py::test_llm_review_outcome_structure` | - [x] |
| 12 | confidence-routed-review | Review Queue Resolution | LLM review does not bypass the outcome path | Given a tenant policy routing to the LLM, when the job completes, then every resulting span was created from a recorded review outcome and none was written directly by the job | `tests/test_review_queue.py::test_llm_review_does_not_bypass_outcome_path` | - [x] |
| 13 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A confirmed outcome creates a span at the predicted offsets | Given an outcome confirming an `organization` prediction at 45-53, when processed, then a confirmed span exists with that type and those offsets | `tests/test_review_outcomes.py::test_confirmed_outcome_creates_span` | - [x] |
| 14 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A corrected outcome creates a span at the corrected offsets | Given an outcome correcting to 45-58, when processed, then a span exists at 45-58 and none at the original 45-53 | `tests/test_review_outcomes.py::test_corrected_outcome_uses_corrected_offsets` | - [x] |
| 15 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A rejected outcome creates no span | Given an outcome rejecting a prediction, when processed, then no confirmed span is created for it | `tests/test_review_outcomes.py::test_rejected_outcome_creates_no_span` | - [x] |
| 16 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A value correction does not produce a span | Given an extracted entity whose `corrected_value` differs from the document text at its offsets, when outcomes are processed, then no span is created from that value | `tests/test_review_outcomes.py::test_value_correction_does_not_create_span` | - [x] |
| 17 | confidence-routed-review | Review Outcomes Become Confirmed Spans | Spans from production review are distinguishable by origin | Given spans from manual annotation, batch acceptance and production review, when inspected, then each records its origin and production-review spans are distinguishable | `tests/test_review_outcomes.py::test_span_origin_is_recorded` | - [x] |
| 18 | confidence-routed-review | Accumulation Reporting | Accumulation is reported against the current model version | Given a tenant on model version 3 with 40 production-review spans since it was trained, when accumulation is requested, then 40 is reported against version 3 | `tests/test_accumulation_reporting.py::test_accumulation_against_current_version` | - [x] |
| 19 | confidence-routed-review | Accumulation Reporting | Base-model predictions do not count toward accumulation | Given a tenant with no trained model and 25 production-review spans from base-model predictions, when accumulation is requested, then those 25 are not counted and are recorded distinctly | `tests/test_accumulation_reporting.py::test_base_model_spans_excluded` | - [x] |
| 20 | confidence-routed-review | Accumulation Reporting | Accumulation growth triggers nothing | Given accumulation growing from 40 to 500, when the figure updates, then no training job is created, queued or submitted and no notification initiates a run | `tests/test_accumulation_reporting.py::test_accumulation_triggers_no_training` | - [x] |
| 21 | confidence-routed-review | Auto-Accept Audit Sampling | Audit sample is drawn randomly and recorded | Given 500 auto-accepted predictions, when an audit sample is drawn, then it is selected randomly from that population and the sampled identities are recorded | `tests/test_audit_sampling.py::test_audit_sample_random_and_recorded` | - [x] |
| 22 | confidence-routed-review | Auto-Accept Audit Sampling | Audit agreement rate is recorded | Given a fully reviewed audit sample, when the audit completes, then the agreement rate is recorded with the sample size and the audited model version | `tests/test_audit_sampling.py::test_audit_agreement_rate_recorded` | - [x] |
| 23 | confidence-routed-review | Auto-Accept Audit Sampling | Audit sampling does not alter unsampled predictions | Given 500 auto-accepted predictions and a sample of 20, when the audit finds some sampled ones incorrect, then the 480 unsampled retain accepted status | `tests/test_audit_sampling.py::test_audit_does_not_alter_unsampled` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Threshold conflation (design.md Decision 1) | Implementer reuses `settings.confidence_threshold` for routing, or lowers it so low-confidence predictions survive — coupling review volume to what analytics, chat and the entity projection see | Confirm two distinct configuration values exist and that routing reads the new one. Scenario 6 must show the extraction threshold unchanged when the review threshold moves, and Scenario 3 must show business consumers unaffected. |
| 2 | Second inference pass (design.md Decision 2) | Implementer adds a dedicated annotation-inference call over the document rather than routing the predictions extraction already produced, creating two paths that can disagree about what the model said | Trace the routing input: it must consume the existing extraction run's output. Grep for any new model-serving call in the routing path. |
| 3 | Span derived from `corrected_value` (design.md Decision 3) | Implementer treats the existing value-correction flow as the source of training spans, or searches the document for the corrected value to find offsets — which fails whenever the correction normalises rather than re-quotes, reintroducing the "answer not in the text" problem from change 1 | Confirm span creation reads only character offsets from the review outcome. Grep the span-creation path for any read of `corrected_value`. Scenario 16 supplies a corrected value that does not match the text and must produce no span. |
| 4 | LLM route bypassing review outcomes (design.md Decision 4) | Implementer has the LLM review job write confirmed spans directly "since it already decided", giving the LLM a privileged unaudited path into training data | Confirm the LLM job writes review outcomes and that span creation is driven only from outcomes. Scenario 12 must assert no span was written directly by the job. |
| 5 | Auto-trigger on accumulation (design.md Non-Goals, Decision 5) | Implementer "helpfully" enqueues a training job, schedules one, or emits a notification that starts one when accumulation crosses a value — the exact behaviour this change and change 6 both exclude | Grep the accumulation path for any training job creation, Celery enqueue, or scheduling call. Scenario 20 must assert nothing is created, queued or submitted as the figure grows. |
| 6 | Base-model accumulation (design.md Decision 5, ADR-008) | Implementer counts spans reviewed from base-model predictions toward the tenant's accumulation figure, inflating it with material that says nothing about whether retraining the tenant's model would help | Confirm the accumulation query filters on a tenant-trained model version and that base-model-served predictions are recorded distinctly. Execute Scenario 19. |
| 7 | LLM review job queue (ADR-006) | Implementer registers the LLM review job on the GPU `training.jobs` queue, coupling I/O-bound review work to the GPU node pool and queueing it behind training runs | Grep the job registration for the queue name; it must be change 1's non-GPU queue with no GPU selector. Confirm `training_service` queue configuration is unchanged in the diff. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-008-base-model-as-default | The base model serves as the default inference model (version 0) when a tenant has no active trained model | Base-model predictions must be routed and reviewable but must not accumulate as tenant-specific training evidence | Confirm the accumulation query excludes base-model-served predictions and records them distinctly. Execute Scenario 19 against a tenant with no trained model. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | Every routed prediction must record the model version that produced it, so accumulation is attributable to a version rather than to "the model" | Confirm the model version is captured at routing time from the serving response, not inferred later. Execute Scenario 7. |
| ADR-006-training-infrastructure | Async Celery + RabbitMQ; GPU workers for training specifically | The LLM review job is I/O-bound and must run on the non-GPU LLM queue established by change 1 | Grep the job registration for its queue name and confirm no GPU node-pool selector. Confirm no `training_service` queue changes in the diff. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The review queue, review outcomes, and accumulation records live in the tenant schema and resolve it as existing endpoints do | Trace schema resolution for each new table against the existing pattern; confirm no cross-tenant query in the routing or accumulation paths. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | Accumulation is a delta since last training and is a different quantity from readiness; it must not be presented as a readiness measure or compared to ADR-010's threshold | Confirm the accumulation response contains no readiness language and is not compared against the per-type threshold constant. Confirm no new readiness threshold is introduced. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [x] Scenario 1 (Business filtering unchanged): existing regression test output, unchanged
- [x] Scenario 2 (Below-threshold retained): test output asserting the retained prediction with type, value, confidence, offsets and model version
- [x] Scenario 3 (Retaining changes nothing consumers see): test output comparing `document_entities` across two runs of the same document, routing suppressed then enabled — identical (design.md Decision 15 narrowed this from the original "exactly 3 of 5" wording, which assumed a filter the document-backed path never had)
- [x] Scenario 4 (Auto-accept): test output asserting the prediction is accepted and absent from the queue
- [x] Scenario 5 (Queued): test output asserting queue membership with recorded confidence 0.62
- [x] Scenario 6 (Independent thresholds): test output asserting the extraction threshold and business results are unchanged when the review threshold moves
- [x] Scenario 7 (Model version recorded): test output asserting version 3 on every routed prediction
- [x] Scenario 8 (Human confirm): test output asserting the confirmed outcome and human route
- [x] Scenario 9 (Human correct offsets): test output asserting the corrected outcome at 36-50 — the spec's 45-58 transposed to this fixture's document, where `Acme Corp` sits at 36-45
- [x] Scenario 10 (Reject): test output asserting the rejected outcome and no span created
- [x] Scenario 11 (LLM outcome shape): test output asserting one of the three outcome kinds plus the LLM route
- [x] Scenario 12 (No LLM bypass): test output asserting every span traces to a recorded outcome
- [x] Scenario 13 (Confirmed → span): test output asserting the span at the predicted offsets
- [x] Scenario 14 (Corrected → span): test output asserting the span at 36-50 and none at the original 36-45
- [x] Scenario 15 (Rejected → no span): test output asserting no span exists
- [x] Scenario 16 (Value correction ignored): test output asserting no span from a non-matching `corrected_value`
- [x] Scenario 17 (Origin recorded): test output asserting the three origins are distinguishable
- [x] Scenario 18 (Accumulation reported): test output asserting the figure against model version 3, at a smaller count than the spec's 40 (4, then 2-of-7 across versions) — the count is arbitrary, the attribution is the claim
- [x] Scenario 19 (Base-model excluded): test output asserting the 25 base-model spans are excluded and recorded distinctly
- [x] Scenario 20 (Nothing triggered): test output plus assertion that no training job was created, queued or submitted as accumulation grew
- [x] Scenario 21 (Audit sample random): test output asserting random selection and persisted sampled identities
- [x] Scenario 22 (Agreement rate recorded): test output asserting rate, sample size and audited model version stored
- [x] Scenario 23 (Unsampled untouched): test output asserting the 40 unsampled predictions retain `accepted`, at a smaller population than the spec's 500/20

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions. Three deviations found during implementation were recorded as decisions rather than left silent: D14 (routing lives in the worker, not the ad-hoc endpoint), D15 (the visibility guarantee is about the routing store, not a `document_entities` filter), D16 (an audit neither consumes its population nor creates training data)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced — `span_review_provenance` mirrors `039`'s `span_batch_provenance`; the migration follows `038`/`039`'s enumerated-schema form; the Celery task follows the existing `_sync` + thin-task shape
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Only additive schema changes were introduced — five new tenant tables plus one `public.tenants` column with a default; `downgrade` drops exactly what `upgrade` creates. No existing table lost a column or a constraint
- [x] Change 4's sampling and agreement-rate logic is reused, not reimplemented — `audit_sampling` re-exports `batch_acceptance.draw_sample` and `.agreement_rate`, and a test asserts identity (`draw_sample is batch_acceptance.draw_sample`) rather than equivalent behaviour, because two implementations that agree today can still diverge
- [x] No training job creation, enqueue, or scheduling call exists anywhere in this change's diff — grepped for `training.jobs`, `training_jobs`, `send_task`, `apply_async`, `.delay(`, `add_periodic_task`, `crontab`, `beat_schedule` across all new files and all diffs to existing ones. The only textual hit is change 4's comment stating it deliberately avoids `training.jobs`. `src/training_service/` carries no change from this work

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 confirmed — `confidence_threshold` (0.50) and `review_confidence_threshold` (0.90) are separate settings; the worker reads the latter for routing. `test_the_two_thresholds_are_separate_settings` fails if they are ever shipped equal
- [x] Risk 2 confirmed — `TestNoSecondInferencePass` runs the real worker with a call-counting stub and asserts exactly one POST to model serving. `prediction_routing` takes entities as an argument and cannot call serving
- [x] Risk 3 confirmed — the only occurrence of `corrected_value` in the span-creation path is a docstring saying it is never read. `test_a_corrected_value_produces_no_span` supplies a value that does not occur in the document at all and asserts no span carries it
- [x] Risk 4 confirmed — both routes call the same `resolve_prediction`. `test_llm_review_does_not_bypass_outcome_path` left-joins every span to its outcome and fails on any orphan; `test_the_job_contains_no_span_write` AST-parses the job's string literals for a span write
- [x] Risk 5 confirmed — checked behaviourally (figure grown 2 → 12 with a Celery dispatch spy installed; nothing dispatched) and structurally (AST parse of all seven modules for dispatch calls), plus the diff-wide grep recorded under Structural Evidence
- [x] Risk 6 confirmed — `served_by_base_model` is recorded at routing time, and the accumulation query reports base-model spans in their own field. `test_base_model_spans_do_not_inflate_a_tenant_figure` mixes both and asserts 2 and 5 stay apart
- [x] Risk 7 confirmed — `celery_app.conf.task_default_queue` resolves to `annotation.llm_jobs` (verified live in-container). No node-pool selector anywhere in this change, and `src/training_service/` carries no change from this work

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

All backend evidence below was produced by one command, run against the live
`postgres-test` container. The host has no Python environment with this project's dependencies
(no `poetry`, no venv, `import pydantic` fails on the system interpreter), so the suite runs in a
container with the repo bind-mounted:

```
docker run --rm --network ner-project_default -v "${PWD}:/app" -w /app \
  -e NER_DATABASE_URL="postgresql+asyncpg://ner:ner@postgres-test:5432/ner_test" \
  -e NER_DATABASE_URL_SYNC="postgresql://ner:ner@postgres-test:5432/ner_test" \
  -e NER_JWT_SECRET="test-secret-do-not-use-in-prod" \
  ner-project-test:latest python -m pytest <files> -q
```

`ner-project-test:latest` is the `ner-project-gateway` image plus the `dev` dependency group;
the service images ship without pytest.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | Full change suite, run twice consecutively with identical results: `82 passed` over `test_extraction_confidence_filtering.py`, `test_confidence_routing.py`, `test_review_queue.py`, `test_review_outcomes.py`, `test_accumulation_reporting.py`, `test_audit_sampling.py`, `test_extract_confidence_threshold.py` | 1-23 | agent | 2026-09-07 |
| 2 | Test output | `tests/test_extract_confidence_threshold.py` — `5 passed`. The pre-existing filtering regression for the ad-hoc `/extract` endpoint, unchanged by this change | 1 | agent | 2026-09-07 |
| 3 | Test output | `tests/test_extraction_confidence_filtering.py` — `5 passed`. Row 3 is the narrowed guarantee from design.md Decision 15: the same document run twice, once with routing suppressed and once enabled, produced byte-identical `document_entities` | 2-3 | agent | 2026-09-07 |
| 4 | Test output | `tests/test_confidence_routing.py` — `15 passed`, including `TestNoSecondInferencePass`, which runs the real extraction worker with a call-counting stub and asserts exactly **one** POST to model serving | 4-7 | agent | 2026-09-07 |
| 5 | Test output | `tests/test_review_queue.py` — `20 passed`. Human route driven through the HTTP endpoint; LLM route driven through the real Celery task body with only the provider stubbed | 8-12 | agent | 2026-09-07 |
| 6 | Test output | `tests/test_review_outcomes.py` — `9 passed`. Row 16 supplies `corrected_value = "Acme Corporation"`, which is 16 characters against the 9 the document holds at those offsets and does not occur in the document at all | 13-17 | agent | 2026-09-07 |
| 7 | Test output | `tests/test_accumulation_reporting.py` — `8 passed`. Row 20 is checked twice: behaviourally, growing the figure 2 → 12 with a Celery dispatch spy installed; and structurally, by AST-parsing all seven modules of this change for `send_task` / `apply_async` / `delay` / `add_periodic_task` | 18-20 | agent | 2026-09-07 |
| 8 | Test output | `tests/test_audit_sampling.py` — `20 passed`. Row 23 checked on both dispositions and spans: the 40 unsampled predictions kept `accepted`, and a fully-confirmed audit produced zero spans and left the accumulation figure at 0 | 21-23 | agent | 2026-09-07 |
| 9 | Schema | `alembic upgrade head` applied migration `040` cleanly; `\d tenant_template.routed_predictions` and the `public.tenants.review_policy` column verified by inspection. All four tenant schemas (`tenant_template`, `tenant_demo_tenant`, two UUID tenants) carry all five new tables | 4-7, 18-23 | agent | 2026-09-07 |
| 10 | Log | Extraction worker output during the end-to-end routing test: `WORKER: doc=… routed_accepted=1 routed_queued=2`, from a single inference call. Confirms min-aggregation in practice — a two-token `Acme Corp` span scored 0.95/0.62 carries **0.62** and is queued, not accepted | 4-5 | agent | 2026-09-07 |
| 11 | Structural | Grep of the routing store's readers: `routed_predictions` is named only by `extraction_service/{worker,services/prediction_routing}.py` and `annotation_service/{worker.py,api/v1/review_queue.py,services/review_resolution.py,services/audit_sampling.py}`. No `chat_api`, `analytics_service`, or `document_service` module reads it. Asserted as a test, so a new reader fails the suite | 3 | agent | 2026-09-07 |
| 12 | Test output | Frontend: `src/components/review-queue/ReviewQueuePage.test.tsx` — `12 passed`, covering the queue listing, offset-based highlighting, confirm/correct/reject, and the accumulation card in both its tenant-version and base-model states | 8-10, 18-19 | agent | 2026-09-07 |
| 13 | Screenshot / live | Portal dev server, signed in as `admin@democorp.io`: **Review Queue** renders in the tenant-admin nav and the screen loads. This surfaced a real defect the mocked component tests could not — `authFetch.resolveUrl` had no rule for the new prefixes, so `/api/v1/review-queue` went to the portal's own origin and 404'd. Fixed by routing `review-queue`, `review-accumulation` and `audits` to `ANNOTATION_URL`, mirroring the three existing seed-bootstrap rules | 8-10 | agent | 2026-09-07 |
| 14 | Structural | `openspec validate confidence-routed-review --type change --strict` exits clean | — | agent | 2026-09-08 |
| 15 | Test output | Frontend routing regression: `src/lib/auth-fetch.test.ts` — `18 passed`, including `routes the confidence-routed review endpoints to ANNOTATION_URL`, which covers all five new paths. This is the case guarding the defect found live in entry 13 | 8-10 | agent | 2026-09-08 |
| 16 | Test output | Portal suite for this change's files: `37 passed, 1 failed` over `auth-fetch.test.ts`, `ReviewQueuePage.test.tsx`, `nav-config.test.ts`. The single failure is **pre-existing and unrelated** — `nav-config.test.ts` expects 5 `business_user` nav items and the code returns 4; this change touched only the `tenant_admin` and `annotator` lists | 8-10, 18-19 | agent | 2026-09-08 |

| 17 | Live end-to-end | Portal → `annotation_service` (rebuilt) → Postgres, signed in as `admin@democorp.io` on the demo tenant. Queue rendered 3 waiting with context, type, offsets and confidence; **Confirm** on the `organization` prediction took the queue to 2 and created the span below | 8, 13, 17 | agent | 2026-09-08 |
| 18 | Database | State after that confirmation, read directly: `spans` = (`organization`, 36, 45, `Acme Corp`, confidence **1.0**, bio_tags `{B-organization,I-organization}`) joined to a `span_review_provenance` row; `review_outcomes` = (`confirmed`, route `human`, origin `queue`, real reviewer id, `model_version` 0, `served_by_base_model` **t**); `routed_predictions` queued count 3 → 2. Confirms in one trace: the span is sliced from the document at the resolved offsets, its confidence is the reviewer's not the model's 0.62, the provenance row exists, and the prediction was discarded per Decision 11 | 8, 13, 17 | agent | 2026-09-08 |
| 19 | Live end-to-end | ADR-008 / Decision 5 on real data: the confirmed prediction was base-model served, so the accumulation card moved from "0 … since version 3 was trained" to the same 0 **plus** "A further 1 came from base-model predictions and are not counted here". The base-model span was recorded, reported distinctly, and kept out of the tenant figure | 19 | agent | 2026-09-08 |
| 20 | Live end-to-end | The offset-drift warning fired on genuinely wrong data. The demo row seeded `location` at 48-55; `Chennai` actually sits at 49-56. The screen showed *"The document now reads ' Chenna' at these offsets, but the model extracted 'Chennai'. Check the offsets before confirming."* — an unplanned check of the warning against a real off-by-one, in seed data written by the same agent | 8 | agent | 2026-09-08 |

**Environment note.** Node.js was removed from this machine partway through implementation and
reinstalled the following day as v24.20.0 under nvm
(`%LOCALAPPDATA%\Author Software\nvm\.nodejs`). Entries 15, 16 and 14 were collected after that
reinstall; entries 1-13 predate it and were unaffected, being either container-run (backend) or
browser-observed. Anyone re-running the portal suite in a fresh shell may need that directory on
`PATH` and a `npm install --prefix src/portal` first.

**Left as found, for the human reviewer:**

- The pre-existing `nav-config.test.ts` `business_user` count failure (entry 16). It is not this
  change's to fix, but it will keep the portal suite red until someone does.
- Demo rows remain in `tenant_demo_tenant` for inspection: `rq-p1` was consumed by the
  confirmation in entry 17, `rq-p2` (the deliberate off-by-one from entry 20) and `rq-p3` are
  still queued, and `rq-p4` is auto-accepted and therefore available to an audit draw. They are
  test fixtures, not real tenant data, and should be removed before this tenant is used for
  anything else.

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** confidence-routed-review
**Proposal:** `openspec/changes/confidence-routed-review/proposal.md`
**Spec files reviewed:**

- specs/confidence-routed-review/spec.md
- specs/extraction-service/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** Hanna.ansar (theertha@inapp.com)

**Date:** 2026-09-08

**How this sign-off was given:** approved in-session on 2026-09-08, on the basis of the evidence
recorded in Section 5 and the confirmations in Sections 3 and 4. Those checks were performed and
reported by the implementing agent; the reviewer approved the archive on that reported basis
rather than independently re-executing each one. The boxes above were ticked by the agent at the
reviewer's explicit instruction. Recorded here so the gate's provenance is legible to anyone
reading this later.

**Notes:**

> Status of these notes after implementation, added 2026-09-08. The notes below were written
> before any code existed and are kept verbatim. Where implementation closed one, the resolution
> is named here rather than by editing the note.
>
> - *Five measurement and policy questions*: review threshold → **D7** (0.90, its own setting);
>   human-versus-LLM policy → **D10** (per-tenant switch, LLM off everywhere until agreement data
>   exists); span-level confidence aggregation → **D8** (minimum across tokens, the rule
>   `aggregate_confidence` already applied); audit cadence → **D13** (weekly, `max(20, 5%)`,
>   capped at 100). Whether a correction re-runs extraction is **still open** — not required by
>   this change.
> - *Retention bound*: **D11** — discarded on resolution, plus a 90-day cap on the abandoned path.
> - *Negative training signal from a rejection*: **D12** — the outcome is recorded, no span and no
>   explicit `O` is written. The reviewer rejected one type at those offsets, not every type.
> - *Nothing is triggered*: confirmed two ways — behaviourally (accumulation grown 2 → 12 with a
>   Celery dispatch spy installed, nothing dispatched) and structurally (AST parse of all seven
>   modules, plus a diff-wide grep). `src/training_service/` carries no change from this work.
> - *One model grading another*: the route is recorded on every outcome, and **D10** keeps the LLM
>   route off until human-route agreement gives it something to be compared against.
>
> Three decisions were taken during implementation that were not anticipated here, and each
> changed the shape of the work: **D14** (routing belongs in the extraction worker — the ad-hoc
> endpoint has no document, so a prediction retained there could never become a span), **D15**
> (the visibility guarantee is about the routing store, because the document-backed path never
> filtered `document_entities` and adding a filter would have removed entities business consumers
> receive today), and **D16** (an audit neither consumes its population nor creates training
> data).

- **This change deliberately triggers nothing.** Accumulation is reported and that is all. Change 6 owns the retraining decision and it is human-gated. Reviewer should confirm no training job creation, enqueue, or scheduling call exists anywhere in the diff — this is the single easiest thing for an implementer to add "helpfully" and the single most important thing to keep out.
- **Five measurement and policy questions are unresolved and must be decided before implementation**: the review threshold value, the human-versus-LLM routing policy, how span-level confidence is aggregated from per-token probabilities (this silently determines what lands in the queue and must be stated explicitly), whether a correction re-runs extraction, and audit cadence.
- **A retention bound for below-threshold predictions is required.** This change makes extraction stop discarding them; without a bound on how long or how many are kept, storage grows unboundedly on a large corpus.
- **Unresolved and consequential**: whether a rejected prediction should produce a negative training signal. It is real information that the model was wrong, but representing it means deciding whether that region becomes an explicit `O` or is left unlabeled — which interacts directly with the partial-labeling concern that shaped change 1. Do not decide this casually during implementation.
- The LLM reviewing BERT's output is one model grading another, with potentially correlated blind spots. Recording the review route is what makes LLM-route and human-route agreement comparable; if they diverge materially, the LLM route's weight should be reconsidered.
