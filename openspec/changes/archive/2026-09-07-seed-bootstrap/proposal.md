## Why

Changes 1 and 2 let a tenant get LLM suggestions for one document at a time and approve them individually. That is enough to prove the mechanism, but it does not produce a trained model. Getting from an empty tenant to a working BERT v1 requires three things that do not exist yet: a way to work out which entity types a tenant's documents actually contain, a way to pre-label a large batch without firing one request per document from a browser, and a way to accept a large batch of machine-generated annotations without either reviewing all 200 by hand (which defeats the automation) or accepting them blind (which puts unverified labels into training).

This is change 4 of a 6-change plan. It depends on change 1 (the LLM pre-labeling capability) and change 3 (without the export and truncation fixes, the resulting model would train on misaligned, truncated data regardless of how good the annotations are).

## What Changes

- Add an entity schema proposal step: the LLM reads a small seed set of documents together with the tenant's QA pairs and proposes candidate entity types with example values. A human reviews the proposal and approves, edits, or rejects each candidate. Approved candidates are created as normal entity type definitions through the existing entity-config API. The LLM SHALL NOT create entity types directly.
- Add a batch pre-labeling trigger: one job that pre-labels a set of documents, replacing the per-document request loop change 2 deliberately deferred. The batch job is trackable as a single unit with per-document outcomes.
- Add a sampled acceptance gate: before a batch of machine-generated suggestions can be bulk-promoted to confirmed spans, a reviewer checks a randomly drawn sample. The measured agreement rate is recorded and must clear a configured threshold before bulk acceptance is permitted. A batch that falls short is rejected as a batch, not silently partially accepted.
- Add a pre-submission readiness check that reports per-entity-type shortfalls against the existing dataset readiness threshold before a training job is submitted, so a tenant learns which labels are starved before spending a GPU run rather than after.
- Bulk-promote accepted suggestions into confirmed spans, recording that they arrived via batch acceptance rather than individual review.

## Capabilities

### New Capabilities

- `seed-bootstrap`: the path from a seed set to a first trained model — entity schema proposal with human approval, batch pre-labeling, sampled acceptance of a machine-annotated batch, and the pre-submission readiness check.

### Modified Capabilities

None. Entity type creation reuses the existing `entity-config` API, span promotion reuses the existing confirmed-span model, and training submission and approval reuse `training-jobs` and `training-approval` unchanged.

## Impact

- **Backend**: new endpoints and a Celery batch task in `src/annotation_service`, reusing change 1's LLM client, grounding logic, and `annotation.llm_jobs` queue pattern; a readiness query reusing the per-entity-type threshold already defined at `src/gateway/api/v1/dashboard.py` (`DATASET_READINESS_ENTITIES_PER_TYPE`).
- **Database**: a table to record batch pre-labeling jobs and their sampled-acceptance outcome (sample size, agreement rate, decision, reviewer, timestamp), so an accepted batch is auditable. Additive; new table only.
- **Frontend**: a schema proposal review screen and a batch acceptance review screen. Both are new surfaces, not modifications to the annotation workspace.
- **Depends on**: change 1 (LLM pre-labeling capability and `qa_examples`) and change 3 (export windowing, offset correctness, sequence length). Change 2 is not a hard dependency, though its QA-pairs editor is the natural way for a tenant to populate the input this change consumes.
- **No impact**: the per-document Suggest flow from changes 1 and 2 continues to work unchanged; model serving, extraction, and the chat/analytics paths are untouched.

## Open Questions

- **Agreement threshold value**: what sampled agreement rate should permit bulk acceptance? This must be measured against real reviewed batches rather than guessed. Until there is data, the threshold should be configurable and default to a conservative value — or default to requiring full review, with sampling enabled explicitly once a tenant has evidence.
- **Sample size**: how many documents constitute a meaningful sample of a 100-200 document batch? Needs a stated basis rather than a round number.
- **What counts as agreement?** Exact span match, or overlap? A reviewer correcting a boundary by one token is a different signal from a reviewer deleting a hallucinated entity. The metric must distinguish these or it will read as noise.
- **Seed set size**: guidance from design discussion is roughly 20 documents to reach usable per-type coverage, but this depends on entity density per document and should be reported to the tenant as a live calculation rather than fixed in a spec.
- **PII / data residency** remains gated from change 1 task 1.1 and applies with more force here, since this change sends 100-200 documents to an external LLM rather than one.
