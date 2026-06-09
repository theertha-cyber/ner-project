# ADR-002: Single Curated Base Model Strategy (No BYOM)

**Status**: Proposed

**Date**: 2026-06-04

## Context

Each tenant needs to fine-tune a model to recognize domain-specific named entities beyond standard CoNLL classes (PER, ORG, LOC, MISC). The question is which base model(s) tenants may use as the starting point for fine-tuning.

We evaluated three strategies:

- **(a) Single curated base model**: All tenants fine-tune from `dslim/bert-base-NER`. Eliminates model compatibility matrix and simplifies infrastructure.
- **(b) Tenant-selectable base models from a curated list**: A limited set of pre-approved models. Adds testing and validation overhead for each supported model.
- **(c) Full bring-your-own-model (BYOM)**: Any Hugging Face compatible model. Maximum flexibility but maximum infrastructure complexity and support burden.

## Decision

**Use a single curated base model — dslim/bert-base-NER** (strategy a).

This decision is non-negotiable for the initial release. Key rationale:

- Eliminates model compatibility matrix — every tenant fine-tunes from the same starting point.
- Single ONNX export path, single optimization strategy (quantization, batching).
- Cross-tenant metric comparisons are meaningful because baselines are identical.
- `dslim/bert-base-NER` supports token classification fine-tuning and recognizes standard CoNLL classes that serve as pre-labels during annotation.

Training hyperparameters (learning rate, epochs, batch size, max sequence length) are tenant-configurable per job request but always applied to the same base model.

## Consequences

### Positive
- Single training pipeline code path — simpler to maintain and debug.
- Simplified Model Registry — base model reference is always the same (name + hash).
- Consistent evaluation thresholds across all tenants.

### Negative
- BERT token classification may be suboptimal for highly visual documents or layout-dependent fields.
- Upgrading the base model requires re-fine-tuning all active tenant models.
- Blocks tenants with existing fine-tuned models from importing them.

### Mitigations
- Layout metadata (`page_no`, `block_no`) preserved in `document_text_span` for future layout-aware model evaluation.
- Base model upgrades gated by backward-compatibility evaluation and tenant notification.
- PRD explicitly lists BYOM as out of scope; re-evaluate at major version milestones.
- OCR confidence metadata stored alongside spans to handle scanned documents.

## Compliance

- All training jobs MUST reference `dslim/bert-base-NER` (name + hash) as `base_model`.
- The Training Orchestrator MUST reject jobs specifying any other base model.
- The Model Registry MUST validate the base model reference on job creation.
- Hyperparameter defaults: learning_rate=2e-5, num_epochs=3, batch_size=16, max_seq_length=128.

## References

- Technical Design Document §2 (Constraints — single curated base model)
- Technical Design Document §4.4 (Technology Choices — PyTorch + Hugging Face Transformers)
- Technical Design Document §FR-06 (Training Trigger API)
