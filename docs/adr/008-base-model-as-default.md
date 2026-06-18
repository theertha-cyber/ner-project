# ADR-008: Base Model as Default Inference Model (Version 0)

**Status**: Proposed

**Supersedes**: ADR-002 (partially — overrides the "no active model → 404" behavior)

**Date**: 2026-06-16

## Context

ADR-002 established `dslim/bert-base-NER` as the single curated base model for fine-tuning, but did not define behavior when no tenant-specific model has been promoted. The current implementation returns HTTP 404/400 for any extraction request when no model is promoted, rendering the platform unusable until a tenant completes the annotation → training → promotion cycle.

Users should be able to extract standard CoNLL entities (PER, ORG, LOC, MISC) immediately, using the base model as a default, even before fine‑tuning a custom model.

## Decision

**Treat the base model `dslim/bert-base-NER` as version 0 for every tenant.** When no fine‑tuned model is promoted, the system uses the base model for inference and the Model Registry returns base model metadata (version 0, CoNLL label list, empty metrics) instead of a 404.

Key points:

- The base model is a shared singleton in the Model Serving Layer — one instance serves all tenants.
- Version 0 is synthetic — it has no database row and no MLflow stage.
- Extraction responses include a `model_version` field distinguishing `"0"` (base) from trained versions (`"1"`, `"2"`, etc.).
- Promoting a fine‑tuned model automatically upgrades the tenant from version 0 to the promoted version.
- Demoting a fine‑tuned model returns the tenant to version 0.

## Consequences

### Positive
- Tenants can extract entities immediately after provisioning — no training required.
- The extraction API never returns "no active model" errors (base model always available).
- Clear user‑visible signal (`model_version`, `X-Model-Source` header) when base model is active.

### Negative
- Base model predictions use CoNLL labels (PER, ORG, LOC, MISC), not tenant‑specific custom labels.
- Cold start: first inference after serving startup requires downloading the base model from Hugging Face Hub.

### Mitigations
- Base model is downloaded and cached once per serving instance, not per tenant.
- The Hugging Face `pipeline` API uses local disk cache (`~/.cache/huggingface/`) so subsequent restarts are fast.
- A future optimization can pre‑load the base model at serving startup.

## Compliance

- The Model Registry active model endpoint MUST return version 0 metadata when no Production stage version exists.
- The Model Serving Layer MUST fall back to the base Hugging Face pipeline when the resolved version is 0.
- Every extraction response MUST include `model_version` set to either `"0"` or the promoted version number.
- Fine‑tuned model inference MUST continue to use ONNX Runtime (unchanged from ADR-003).
- The base model SHALL be `dslim/bert-base-NER` (unchanged from ADR-002).

## References

- ADR-002: Single Curated Base Model Strategy (No BYOM) — superseded for default behavior
- ADR-003: Per-Tenant Model Serving Topology — unchanged
- Technical Design Document §FR-06 (Training Trigger API)
