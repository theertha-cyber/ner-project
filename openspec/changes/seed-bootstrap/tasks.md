## 1. Prerequisites

- [ ] 1.1 Confirm change 1 (`llm-assisted-prelabeling`) has landed — its LLM client, prompt construction, grounding function, entity type constraint, and non-GPU queue are all reused by this change rather than reimplemented.
- [ ] 1.2 Confirm change 3 (`training-data-integrity`) has landed. Without it, a model trained from this flow learns from misaligned and truncated data regardless of annotation quality, and the acceptance gate would pass a batch that still produces a broken model.
- [ ] 1.3 Confirm the PII / data-residency decision from change 1 task 1.1 has been made. This change sends 100-200 documents to an external LLM rather than one; the exposure is materially larger.
- [ ] 1.4 Decide the four measurement values that this spec deliberately leaves open: the agreement threshold, the sample size, what counts as agreement (exact span match versus overlap — record whether a one-token boundary correction counts as disagreement), and the practical seed set size. These MUST come from real reviewed batches. Until evidence exists, configure the threshold conservatively or require full review.
- [ ] 1.5 Decide whether a rejected batch's suggestions are discarded or left in place for individual review (design.md Open Questions), and record the decision.

## 2. Schema Proposal

- [ ] 2.1 Add a proposal request endpoint accepting a seed document set, returning 202 with a `proposal_id`; reject with 422 when no document in the set has extracted text.
- [ ] 2.2 Add a proposal generation task on change 1's non-GPU queue that prompts the LLM with the seed documents and the tenant's existing QA pairs, returning candidate entity types with names, descriptions, and verbatim example values.
- [ ] 2.3 Validate every returned example against its source document, discarding any that does not appear verbatim — reuse change 1's grounding helper rather than writing a second matcher.
- [ ] 2.4 Persist proposals and their candidates in the tenant schema, with a per-candidate disposition field (pending / approved / edited / rejected).
- [ ] 2.5 Add approve, edit, and reject endpoints for individual candidates. Approval MUST call the existing entity type creation API — it MUST NOT insert into `entity_definitions` directly (design.md Decision 1). Return 422 when an approved candidate's name collides with an existing active entity type.
- [ ] 2.6 Add `tests/test_seed_bootstrap_proposal.py` with `test_request_proposal_returns_202`, `test_candidate_examples_are_verbatim`, `test_proposal_creates_no_entity_types`, `test_proposal_422_no_processed_documents`, `test_approve_candidate_creates_entity_type`, `test_reject_candidate_creates_nothing`, `test_edit_candidate_before_approval`, and `test_approve_duplicate_name_422`, covering Spec Alignment rows 1-8.

## 3. Batch Pre-labeling

- [ ] 3.1 Add a batch trigger endpoint accepting a document set and returning 202 with a single `batch_id`.
- [ ] 3.2 Add a batch task on change 1's non-GPU queue — never `training.jobs` and with no GPU node-pool selector (ADR-006). It MUST call change 1's existing extraction and grounding path per document, not a second implementation (design.md Decision 2).
- [ ] 3.3 Persist per-document batch outcome (succeeded / failed, ungrounded-suggestion count) and expose aggregate batch status. A failure on one document MUST NOT abort the batch.
- [ ] 3.4 Add `tests/test_seed_bootstrap_batch.py` with `test_enqueue_batch_returns_batch_id`, `test_single_document_failure_does_not_abort_batch`, `test_batch_honours_entity_type_constraint`, and `test_batch_grounding_matches_single_document`, covering Spec Alignment rows 9-12. The grounding parity test MUST exercise the real batch path, not a stub.

## 4. Sampled Acceptance Gate

- [ ] 4.1 Add an acceptance record table in the tenant schema storing batch id, sampled document ids, sample size, agreement rate, decision, reviewer, and timestamp. Additive only.
- [ ] 4.2 Implement random sample selection across the whole batch — not the first N, and not reviewer-chosen (design.md Decision 4). Persist the drawn ids at selection time.
- [ ] 4.3 Implement agreement rate computation from the reviewer's dispositions, using the definition of agreement decided in task 1.4.
- [ ] 4.4 Gate bulk acceptance on the rate meeting the configured threshold. A sub-threshold batch MUST promote zero spans — there is no partial acceptance path (design.md Decision 3). Reject bulk acceptance outright when the sample review is incomplete.
- [ ] 4.5 Implement bulk promotion of an accepted batch's suggestions into confirmed spans, recording batch-acceptance provenance so these spans are distinguishable from individually promoted ones.
- [ ] 4.6 Add `tests/test_seed_bootstrap_acceptance.py` with `test_sample_is_random_and_recorded`, `test_batch_above_threshold_bulk_accepts`, `test_batch_below_threshold_rejected`, `test_acceptance_requires_completed_sample_review`, and `test_bulk_promoted_spans_record_route`, covering Spec Alignment rows 13-17. The below-threshold test MUST assert zero spans promoted, not merely that the request errored.

## 5. Pre-Submission Readiness Check

- [ ] 5.1 Add a readiness endpoint reporting per-entity-type confirmed entity counts against the existing `DATASET_READINESS_ENTITIES_PER_TYPE` value in `src/gateway/api/v1/dashboard.py`. Read that single source of truth — do NOT define a new constant (ADR-010, design.md Decision 5).
- [ ] 5.2 Evaluate the union of active entity definitions and distinct entity types present in confirmed spans, so a configured-but-unannotated type remains visible with a count of 0 (ADR-010).
- [ ] 5.3 Confirm the check is advisory: it MUST NOT block training submission, MUST NOT set hyperparameters, and MUST NOT pre-empt the System Admin approval step (ADR-009).
- [ ] 5.4 Add `tests/test_seed_bootstrap_readiness.py` with `test_readiness_names_shortfalling_types`, `test_unannotated_types_are_visible`, `test_readiness_does_not_block_submission`, and `test_readiness_is_per_type_not_total`, covering Spec Alignment rows 18-21.

## 6. Frontend Surfaces

- [ ] 6.1 Add a schema proposal review screen listing candidates with their examples, and per-candidate approve / edit / reject controls.
- [ ] 6.2 Add a batch acceptance review screen presenting the drawn sample, capturing reviewer dispositions, displaying the computed agreement rate against the threshold, and enabling bulk acceptance only when the threshold is met.
- [ ] 6.3 Surface the pre-submission readiness report where a training job is submitted, naming shortfalling entity types with their counts.
- [ ] 6.4 Confirm the per-document Suggest flow from changes 1 and 2 is unchanged by these additions.

## 7. Verification & Evidence

- [ ] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 7.5 Confirm by reading the call graph that the batch path reuses change 1's grounding and extraction code rather than reimplementing it.
- [ ] 7.6 Run one real bootstrap end to end on a tenant: schema proposal, approval, batch pre-label, sampled acceptance, readiness check, training submission through the existing approval flow. Record the resulting per-type counts and the agreement rate.
- [ ] 7.7 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 7.8 Run `openspec validate seed-bootstrap --type change --strict` and confirm it exits clean before archive.
