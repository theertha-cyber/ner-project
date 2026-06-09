# ADR-003: Per-Tenant Model Serving Topology

**Status**: Proposed

**Date**: 2026-06-04

## Context

Each tenant has a fine-tuned model that must be available for inference at runtime. Requirements mandate version pinning (extraction requests use the tenant's active model version), isolation, and rollback. The requirement states "separate runtime deployment per tenant, or logically isolated deployment pool where infrastructure constraints require pooling."

We evaluated three topologies:

- **(a) Dedicated inference pod per tenant**: Strongest isolation. Each tenant gets its own model serving pod with dedicated GPU memory. High cost for low-volume tenants.
- **(b) Shared serving pool with tenant-aware routing**: A single model serving service loads models on-demand per tenant. Efficient GPU utilization, but noisy-neighbor risk.
- **(c) Serverless inference per request**: Models loaded from cold start per request. Lowest cost for sporadic usage but highest latency (multi-minute cold starts for model loading).

## Decision

**Use shared Model Serving Layer with per-tenant routing and version pinning** (strategy b), with a path to dedicated tenant pods for high-volume tenants.

Architecture:
- Internal endpoint: `POST /internal/v1/tenants/{tenant_id}/infer`
- Model loader loads active version on first request, caches in GPU memory, unloads after inactivity period
- High-volume tenants can be assigned dedicated serving pods via placement policy
- Model artifacts pulled from `s3://ner-platform/tenant-<uuid>/models/v<version>/`
- ONNX Runtime for inference with model quantization to reduce memory footprint

## Consequences

### Positive
- Efficient GPU utilization — shared pool amortizes cost across tenants.
- Simplified operations — single serving deployment to monitor and scale.
- Version pinning straightforward — active model version resolved from Model Registry at inference time.

### Negative
- Noisy-neighbor problem — high-throughput tenant can starve others.
- Model loading/unloading adds latency on cold-start requests.
- GPU memory fragmentation as different model versions cycle in and out.

### Mitigations
- Per-tenant request rate limiting and QoS weights.
- Model warmup after promotion (pre-load before marking active).
- Minimum model retention in GPU memory for high-priority tenants.
- ONNX Runtime with quantization to reduce per-model memory footprint.
- Dedicated pod assignment for tenants exceeding throughput thresholds.
- Autoscaling based on aggregate inference latency (P95 > 500ms → scale up).

## Compliance

- Extraction Service MUST route all inference requests through the Serving Layer's internal endpoint.
- The Serving Layer MUST resolve the active model version from the Model Registry on each request (or cached with configurable TTL).
- Model rollback MUST switch the active version pointer and reload the previous model within 10 minutes (production target).
- Autoscaling MUST be based on aggregate inference latency P95.

## References

- Technical Design Document §FR-08 (Model Serving — internal inference API)
- Technical Design Document §5 (Model Serving Layer — services table)
- Technical Design Document §4.1 (Architecture — Serving Layer component)
