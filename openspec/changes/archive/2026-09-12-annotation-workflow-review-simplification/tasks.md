## 1. Backend — reviewer roles and the sequencing gate

- [x] 1.1 `_gate_acceptance_reviewer`: refuse every acceptance-gate call for a `large` batch
      (422 `LARGE_BATCH_NOT_REVIEWED`); require `annotator` (not `tenant_admin`) for `initial`
- [x] 1.2 `create_prelabel_batch`: reject a `large`-batch request with 422
      `INITIAL_BATCH_NOT_APPROVED` when the tenant has no `initial` batch with
      `annotator_review_status = 'approved'`
- [x] 1.3 `accept_batch`: remove the now-unreachable `large`-kind branch; the `initial`-only
      path now always sets `annotator_review_status = 'approved'` (still no
      `training_eligible_at`, still no notification)
- [x] 1.4 `record_initial_batch_guidance`: require `annotator` instead of `tenant_admin`

## 2. Backend — automatic large-batch promotion

- [x] 2.1 `run_prelabel_batch_sync`: look up `batch_kind` at the start of the run
- [x] 2.2 New `_auto_promote_large_batch`: idempotency guard (`training_eligible_at IS NULL`),
      synthetic `batch_acceptance_records` row (`reviewer = NULL`, `sampled = false`), promote
      every suggested span to a confirmed span with `span_batch_provenance`, delete the
      promoted suggestions, write the `automated_batch_approved` notification directly (sync
      raw SQL — no `AsyncSession` available in the worker)
- [x] 2.3 Call it from `run_prelabel_batch_sync` when `batch_kind == "large"` and at least one
      document succeeded

## 3. Frontend — sequential flow, no batch-kind choice

- [x] 3.1 `BatchAcceptancePage.tsx`: remove the batch-kind radio; derive
      `canCreateInitial` / `canCreateLarge` / `largeDone` from `usePrelabelBatches`
- [x] 3.2 Auto-select the tenant's current batch (`large` if it exists, else `initial` unless
      rejected) so the page shows the right state without requiring an in-session creation
- [x] 3.3 Add a "Start a new validation batch" recovery action for a rejected `initial` batch
- [x] 3.4 Add the "Train model →" action once the `large` batch finishes, navigating to
      `/annotate/automated/retrain`
- [x] 3.5 `useBatchAcceptance` gains an `enabled` flag; the component only polls `/acceptance`
      for an `initial` batch, never a `large` one
- [x] 3.6 `/annotate/review-batch` (landing + `[id]`): filter and label for `initial` batches,
      not `large`

## 4. Verification & Evidence

- [x] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec
      Alignment and confirm all pass
- [x] 4.2 Collect functional evidence (test output) for each scenario — one entry per row in
      verification.md § Evidence Log
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination
      Risk Register — including the mid-verification discovery and repair of
      `test_automated_workflow_guided.py` (Risk 2)
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
      (ADR-013, ADR-011)
- [x] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer
      required — see caveat: this is the implementing agent's own re-inspection, not an
      independent human review)
- [x] 4.6 Run `openspec validate annotation-workflow-review-simplification --type change --strict`
      before archive
