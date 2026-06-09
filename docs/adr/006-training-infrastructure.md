# ADR-006: Training Infrastructure with Asynchronous GPU Workers

**Status**: Proposed

**Date**: 2026-06-04

## Context

Training tenant-specific models requires GPU resources, which are expensive and limited. Training jobs must not block the API or extraction pipeline. Requirements mandate "training jobs shall run asynchronously with GPU-capable workers."

We evaluated three approaches:

- **(a) Synchronous training in the API process**: Simplest implementation but blocks the API process during training. Unacceptable for production.
- **(b) Celery-based async GPU workers with RabbitMQ broker**: Mature task management, worker autoscaling, and monitoring. Workers consume from a `training.jobs` queue and run on GPU-capable K8s pods.
- **(c) Dedicated K8s Job per training run**: Each training run creates an independent K8s Job with GPU node pool. Maximum isolation but slower spin-up and more complex job lifecycle management.

## Decision

**Hybrid: Celery-based async GPU workers with RabbitMQ broker, backed by K8s GPU node pools** (strategy b + c hybrid).

Pipeline:
1. Training request published to RabbitMQ (`training.jobs` queue).
2. Celery workers consume jobs; each worker runs on a GPU-capable K8s pod in a dedicated GPU node pool.
3. GPU node pool autoscales 0 → N based on queue depth (scale-to-zero when idle).
4. Each worker spawns a PyTorch / Hugging Face Trainer for fine-tuning.
5. Metrics, artifacts, logs persisted to object storage and the Model Registry.
6. Backpressure limits concurrent GPU jobs per node pool.
7. Model checkpointing at each epoch — failed jobs resume from last checkpoint.

Training hyperparameters submitted with the job request: learning_rate, num_epochs, batch_size, max_seq_length.

## Consequences

### Positive
- Training never blocks API or extraction — fully asynchronous.
- GPU node pool autoscaling minimizes cost during idle periods.
- Celery provides mature task management (retries, monitoring, result backends).
- Individual training jobs can be monitored and cancelled independently.
- Checkpointing enables resume from failure.

### Negative
- Celery adds operational complexity (Flower monitoring, worker management).
- GPU node pool cold-start latency (minutes) delays training start.
- Hyperparameter tuning requires additional infrastructure (Optuna/Ray).

### Mitigations
- Model checkpointing at each epoch for resume on failure.
- GPU node pool pre-warming for tenants with scheduled training.
- Hyperparameter sweep deferred to post-MVP; empirically validated defaults used initially.
- Training duration alerts if job exceeds 2x estimated time.

## Compliance

- All training jobs MUST be submitted via RabbitMQ — no synchronous training API.
- Each training job MUST record dataset version, entity config version, base model, hyperparameters, and metrics.
- Training artifacts MUST be stored at `s3://ner-platform/tenant-<uuid>/models/v<version>/`.
- Training Orchestrator MUST enforce 500-entity minimum dataset threshold before accepting a job.
- GPU node pool autoscaling MUST scale to zero when no jobs are queued.
- Minimum dataset threshold: 500 labeled entities per entity type before training permitted.

## References

- Technical Design Document §2 (Assumptions — K8s GPU node pools)
- Technical Design Document §5 (Training Orchestrator — Celery GPU workers)
- Technical Design Document §4.4 (ML framework — PyTorch 2.x + Hugging Face Transformers)
- Technical Design Document §FR-06 (Training Trigger API)
