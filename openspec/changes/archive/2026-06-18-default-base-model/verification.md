# Verification Plan

**Change:** default-base-model
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-serving | Internal inference endpoint | Inference returns predictions from fine-tuned model | Given a loaded fine-tuned model, when POST to infer endpoint, then response has status 200 with predictions and model_version | - [ ] |
| 2 | model-serving | Internal inference endpoint | Inference falls back to base model when no tenant model exists | Given no promoted model, when POST to infer endpoint, then response has status 200 with CoNLL labels and model_version "0" | - [ ] |
| 3 | model-serving | Internal inference endpoint | Inference falls back to base model when tenant model fails to load | Given a promoted model that fails to load, when POST to infer endpoint, then response has status 200 using base model with warning header | - [ ] |
| 4 | model-serving | Version resolution with base fallback | Version resolution returns promoted model when one exists | Given a tenant with promoted v2, when inference request arrives, then system resolves and uses model v2 | - [ ] |
| 5 | model-serving | Version resolution with base fallback | Version resolution returns version 0 when no model is promoted | Given a tenant with no promoted model, when inference request arrives, then system resolves to version 0 and uses base model pipeline | - [ ] |
| 6 | model-serving | Version resolution with base fallback | Base model is shared across tenants | Given tenants A and B with no promoted model, when inference requests arrive for both, then both use same base model instance loaded once | - [ ] |
| 7 | model-serving | Model warmup on promotion | Warmup on promotion does not affect base model | Given base model is loaded, when a new model is promoted and warmed up, then base model remains loaded and other tenants continue using it | - [ ] |
| 8 | extraction-service | Real-time extraction | Extract entities with fine-tuned model | Given a tenant with promoted model, when POST extract with text, then status 200 with entities and model_version set | - [ ] |
| 9 | extraction-service | Real-time extraction | Extract entities using base model when none is promoted | Given a tenant with no promoted model, when POST extract with text, then status 200 with entities with CoNLL types and model_version "0" | - [ ] |
| 10 | extraction-service | Batch extraction | Trigger batch extraction with base model | Given no promoted model and processed documents, when POST extract-batch, then status 202 with run_id and queued status | - [ ] |
| 11 | extraction-service | Batch extraction | Batch extraction uses version 0 when no model promoted | Given a tenant whose only promoted model was demoted, when batch extraction is triggered, then it proceeds using version 0 and records model_version "0" | - [ ] |
| 12 | extraction-service | Get extraction run status | Get extraction run status with model version | Given a completed batch run that used version 0, when GET status, then response contains model_version "0" | - [ ] |
| 13 | model-registry | Get active model version | Get active model when one is promoted | Given promoted model v2, when GET /models/active, then status 200 with version number, artifact path, metrics | - [ ] |
| 14 | model-registry | Get active model version | Get active model when none is promoted — returns base model | Given no promoted model, when GET /models/active, then status 200 with version_number 0, artifact_path "base", CoNLL labels, and X-Model-Source: base header | - [ ] |
| 15 | model-registry | Get active model version | Get active model when MLflow unavailable with no cached promoted model | Given no promoted model cached and MLflow unreachable, when GET /models/active, then returns base model metadata with status 200 and warning header | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Base model pipeline implementation | AI may attempt to load the base model via ONNX Runtime instead of Hugging Face pipeline, adding unnecessary complexity | Verify inference_service.py uses `transformers.pipeline("ner")` for the base model fallback, not ONNX |
| 2 | Error path for corrupted tenant model | AI may let a corrupted tenant model crash the inference request instead of falling back to base model | Verify the fallback path catches model load failures and returns base model results with a warning header |
| 3 | Model cache interaction | AI may store the base model in the per-tenant ModelCache instead of as a shared singleton, creating N copies | Verify base model is a module-level singleton in inference_service.py, not stored in ModelCache |
| 4 | Label list hardcoding | AI may hardcode an incorrect or incomplete CoNLL label list (e.g., missing I- tags or wrong order) | Verify the hardcoded label list matches standard CoNLL-2003: O, B-PER, I-PER, B-ORG, I-ORG, B-LOC, I-LOC, B-MISC, I-MISC |
| 5 | model_version field type | AI may use integer type for model_version in schemas, which breaks for version "0" vs "3" consistency | Verify ExtractResponse.model_version is a string field (str), not int |
| 6 | Batch worker version 0 handling | AI may not update the batch worker to handle version 0, leaving a guard that fails batch extraction | Verify worker.py's _get_active_model_version or equivalent handles the base model fallback |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-002 | Single curated base model (`dslim/bert-base-NER`), no BYOM | Fallback model MUST be `dslim/bert-base-NER`. No other base model is allowed. | Verify base model constant in code is `dslim/bert-base-NER` |
| ADR-003 | Shared serving pool with per-tenant routing, ONNX Runtime | Base model fallback MUST fit within shared serving pool. Fine-tuned models still use ONNX Runtime. | Verify fine-tuned models continue using ONNX Runtime; only base model uses HF pipeline |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test showing fine-tuned model inference returns predictions with model_version
- [ ] Test showing base model fallback returns CoNLL labels with model_version "0"
- [ ] Test showing base model fallback on corrupted tenant model with warning header
- [ ] Test showing version resolution returns promoted model when one exists
- [ ] Test showing version resolution returns version 0 when none promoted
- [ ] Test showing base model is shared singleton across tenants
- [ ] Test showing warmup does not affect base model availability
- [ ] Test showing extraction endpoint returns entities with fine-tuned model
- [ ] Test showing extraction endpoint returns CoNLL entities with model_version "0" when no model promoted
- [ ] Test showing batch extraction triggers with base model fallback
- [ ] Test showing batch extraction uses version 0 when model demoted
- [ ] Test showing extraction run status includes model_version
- [ ] Test showing active model endpoint returns promoted model when one exists
- [ ] Test showing active model endpoint returns base model metadata (v0) when none promoted
- [ ] Test showing active model endpoint returns base model when MLflow unavailable

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions
- [ ] ADR-002 compliance confirmed (base model is dslim/bert-base-NER)
- [ ] ADR-003 compliance confirmed (fine-tuned models still use ONNX Runtime)
- [ ] No undocumented architectural patterns introduced

### Edge Case Evidence

- [ ] Base model uses Hugging Face pipeline, not ONNX Runtime (Risk 1)
- [ ] Corrupted model load falls back to base model with warning (Risk 2)
- [ ] Base model is a shared singleton, not in per-tenant ModelCache (Risk 3)
- [ ] CoNLL label list matches standard CoNLL-2003 tags (Risk 4)
- [ ] model_version is string type in schemas (Risk 5)
- [ ] Batch worker handles version 0 fallback correctly (Risk 6)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** default-base-model
**Proposal:** `openspec/changes/default-base-model/proposal.md`
**Spec files reviewed:**
- specs/model-serving/spec.md
- specs/extraction-service/spec.md
- specs/model-registry/spec.md

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
