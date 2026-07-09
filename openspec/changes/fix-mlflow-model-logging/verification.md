# Verification Plan

**Change:** fix-mlflow-model-logging
**Generated:** 2026-07-08
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | onnx-conversion | Convert trained model to ONNX format | ONNX file is produced after training | Given a completed HuggingFace Trainer train run, when the worker calls optimum.onnx.export_onnx, then a .onnx file is written with same output logits shape as PyTorch model | Task 3.3 — unit test: export_onnx produces model.onnx | - [ ] |
| 2 | onnx-conversion | Convert trained model to ONNX format | ONNX file is uploaded to blob storage | Given an ONNX file in model directory, when worker uploads to MinIO, then a .onnx file exists at the artifact path alongside PyTorch files | Task 3.2 — verified by `_save_artifacts` walking model_dir | - [ ] |
| 3 | onnx-conversion | Convert trained model to ONNX format | ONNX file is loadable by model-serving layer | Given an ONNX file at the expected MinIO path, when model-serving downloads and loads via onnxruntime.InferenceSession, then the model loads without errors and returns valid predictions | Task 3.4 — integration test: onnxruntime loads ONNX model | - [ ] |
| 4 | training-retry-guard | Prevent re-execution of completed or failed jobs | Job already completed is not re-executed | Given a Celery task for a job with status=completed, when the task begins execution, then the worker logs a warning and returns without training | Task 2.2 — unit test: skip completed job | - [ ] |
| 5 | training-retry-guard | Prevent re-execution of completed or failed jobs | Job already failed is not re-executed | Given a Celery task for a job with status=failed, when the task begins execution, then the worker logs a warning and returns without training | Task 2.3 — unit test: skip failed job | - [ ] |
| 6 | training-retry-guard | Prevent re-execution of completed or failed jobs | Job in non-terminal status proceeds normally | Given a Celery task for a job with status=approved, when the task begins execution, then the worker proceeds with the training pipeline | Task 2.4 — unit test: proceed for approved job | - [ ] |
| 7 | training-worker | Log training run to MLflow Tracking | MLflow run starts when training begins | Given a Celery training task executing, when the task begins, then a new MLflow run is created under experiment tenant_{tid} with hyperparams logged | Task 4.2 — integration test: MLflow run creation | - [ ] |
| 8 | training-worker | Log training run to MLflow Tracking | Per-epoch metrics are logged to MLflow | Given an active MLflow run during training, when each epoch completes, then train_loss, eval_loss, eval_precision, eval_recall, eval_f1 are logged via mlflow.log_metrics | Task 4.2 — integration test: metrics logged per epoch | - [ ] |
| 9 | training-worker | Log training run to MLflow Tracking | Model artifacts are logged on completion | Given a completed training run, when the model is saved and converted to ONNX, then model artifacts are logged via mlflow.transformers.log_model with registered model name tenant_{tid}_ner_model | Task 4.1 — verify mlflow.transformers.log_model succeeds | - [ ] |
| 10 | training-worker | Log training run to MLflow Tracking | Training failure logs error to MLflow | Given a training run that encounters a failure, when the worker catches the exception, then MLflow run status is set to FAILED and error_message tag contains details | Task 4.2 — integration test: failure path | - [ ] |
| 11 | training-worker | Save model artifacts | Artifacts are stored after training | Given a completed training run, when the worker saves model and tokenizer, then model.onnx exists at the artifact path alongside other files | Task 3.1 / 3.2 — ONNX export code and artifact upload | - [ ] |
| 12 | mlflow-verification-tests | MLflow client-server version compatibility | MLflow client version matches server version range | Given MLflow server v2.20.0, when client calls mlflow.transformers.log_model with registered_model_name, then the call succeeds without 404 | Task 4.1 — verify no 404 on model registration | - [ ] |
| 13 | mlflow-verification-tests | ONNX artifact completeness | ONNX file exists in exported artifacts | Given a completed (or mocked) training run, when artifacts are exported to a temp directory, then a .onnx file exists and is loadable by onnxruntime.InferenceSession | Task 3.3 / 3.4 — unit + integration tests | - [ ] |
| 14 | mlflow-verification-tests | Retry guard prevents duplicate execution | Worker skips completed job | Given a training job with status=completed, when fine_tune_model is invoked with that job ID, then the worker logs a skip warning and job status remains completed | Task 2.2 — unit test | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | ONNX export implementation | AI may use the deprecated `transformers.onnx` module instead of `optimum`, or use incorrect dynamic axis configuration for variable-length BERT sequences | Verify the ONNX export code uses `optimum` and sets `dynamic_axes={"input_ids": {0: "batch_size", 1: "sequence_length"}}` |
| 2 | MLflow version pin | AI may forget to update pyproject.toml pin in addition to worker code, or may use 3.x-only API calls in the worker alongside the 2.x pin | Verify pyproject.toml has `mlflow>=2.20.0,<3.0.0` and no 3.x-only API calls (like `logged-models`) are used |
| 3 | Retry guard interaction with existing exception handler | AI may place the status check after the MLflow run is started (creating orphan runs), or may not handle the case where the DB query itself fails | Verify the status check is the very first action after the try block, before any MLflow or training setup |
| 4 | ONNX file naming | AI may name the ONNX file something other than `model.onnx`, or may not place it in the same directory as the other model artifacts | Verify the exported ONNX filename matches what model-serving's `*.onnx` glob expects |
| 5 | Docker image size increase | Adding `optimum` may pull unnecessary ONNX Runtime backend dependencies, doubling the image size | Verify `optimum`'s actual installed dependencies — prefer `optimum[exporters]` minimal install |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-002 | Single curated base model (dslim/bert-base-NER), no BYOM | ONNX conversion must use dslim/bert-base-NER as the base architecture; worker must not introduce support for alternative base models | Confirm ONNX export references the same BASE_MODEL constant and does not accept user-provided base models |
| ADR-003 | Per-tenant model serving with shared pool, version pinning | ONNX artifacts must integrate with existing serving topology (per-tenant resolution, version pinning) | Confirm the ONNX file path follows the existing `tenants/{tid}/models/v{version}/` convention used by model-serving |
| ADR-006 | Celery-based async GPU workers with Redis broker | Retry guard must not break Celery's acks_late delivery semantics | Confirm the status check is a read-only query that does not interfere with Celery's task lifecycle or ack behavior |
| ADR-008 | Base model (v0) is default when no tenant model is promoted | ONNX conversion and MLflow logging must not break the v0 fallback path | Confirm model-serving still falls back to base model when no fine-tuned ONNX model exists |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing optimum.onnx export produces a .onnx file with matching output logits shape
- [ ] Scenario 2: Test output showing .onnx file exists at the MinIO artifact path after upload
- [ ] Scenario 3: Test output showing onnxruntime.InferenceSession loads the exported model and returns predictions
- [ ] Scenario 4: Test output showing worker skips execution when training_jobs.status = "completed"
- [ ] Scenario 5: Test output showing worker skips execution when training_jobs.status = "failed"
- [ ] Scenario 6: Test output showing worker proceeds normally when training_jobs.status = "approved"
- [ ] Scenario 7: Test output showing MLflow run created with experiment tenant_{tid} and hyperparams logged
- [ ] Scenario 8: Test output showing per-epoch metrics logged to MLflow
- [ ] Scenario 9: Test output showing mlflow.transformers.log_model succeeds and registered model exists
- [ ] Scenario 10: Test output showing MLflow run status=FAILED with error_message tag on training failure
- [ ] Scenario 11: Test output showing model.onnx in the artifact directory alongside other model files
- [ ] Scenario 12: Test output showing mlflow.transformers.log_model with registered_model_name succeeds against v2.20 server
- [ ] Scenario 13: Test output showing .onnx file exists and is loadable by onnxruntime
- [ ] Scenario 14: Test output showing worker logs skip warning and job status unchanged for completed job

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — ONNX export uses `optimum` with correct dynamic axes for BERT variable-length sequences
- [ ] Risk 2 mitigation confirmed — pyproject.toml pinned to `mlflow>=2.20.0,<3.0.0` and no 3.x-only API calls used
- [ ] Risk 3 mitigation confirmed — status check is the first action after try block, before any MLflow/training setup
- [ ] Risk 4 mitigation confirmed — exported ONNX file is named `model.onnx` (matching model-serving's glob pattern)
- [ ] Risk 5 mitigation confirmed — optimum dependency installs minimal export backend

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

**Change slug:** fix-mlflow-model-logging
**Proposal:** openspec/changes/fix-mlflow-model-logging/proposal.md
**Spec files reviewed:**
- specs/onnx-conversion/spec.md
- specs/training-retry-guard/spec.md
- specs/training-worker/spec.md
- specs/mlflow-verification-tests/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
