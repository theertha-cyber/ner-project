# ADR-015. Entity types classified `pattern` or `local_only` never reach the external LLM provider

- **Status:** accepted
- **Date:** 2026-09-17

## Context

LLM-driven pre-labeling (`llm-prelabeling`, `seed-bootstrap`) sends a tenant's document text in
full to an external LLM provider (Azure OpenAI) to extract entity spans. For a tenant whose
documents carry information such as a foster-care client's name, date of birth, or home address,
sending that text to a third-party model provider is a compliance and conduct problem regardless
of what contractual data-handling terms are in place — the platform should not depend on a
provider agreement to keep a tenant's regulated data from leaving its own infrastructure.

`entity-sensitivity-classification` gave each entity type a `sensitivity` tier (`open`, `pattern`,
`local_only`) but left it unread by the pipeline. `automated-annotation-pii-masking` is the change
that makes it load-bearing: entity types classified `pattern` are detected locally via regex,
`local_only` types via the tenant's own already-hosted extraction model, and only a masked copy of
the document — with those spans replaced by placeholders — is sent externally.

## Decision

Once an entity type is classified `pattern` or `local_only`, its real values SHALL NOT appear in
any payload sent to an external LLM provider, under any circumstance, from any part of the
pre-labeling pipeline (single-document or batch). This is enforced by construction: the function
that calls the external provider (`extract_and_ground_document`) never holds a reference to
anything but the masked copy by the time that call is made, and if local detection cannot
complete for a document, the external call SHALL NOT happen at all — the job fails instead
(fail-closed). This is a stricter posture than the platform's other LLM-facing guardrail (the
domain classifier in `chat_api`, which deliberately fails open because it is a scope filter, not a
security boundary); here there is no downstream check that would catch an exposure that already
happened, so the boundary must hold at the one place it can.

## Consequences

- A future change that adds a new way for document text to reach an external LLM in the
  pre-labeling path — a different provider, a new extraction mode, a debug/inspection endpoint —
  must route through the same masking step, or explicitly supersede this ADR with a documented
  reason. Adding such a path silently, next to this one, is the exact failure this ADR exists to
  prevent.
- `model_serving` becomes a hard dependency of LLM pre-labeling for any tenant with at least one
  `local_only` entity type: if it is unreachable, pre-labeling fails for that tenant rather than
  degrading to sending unmasked text.
- A `local_only` entity type with no viable local detection mechanism (no `base_label_mapping`)
  cannot be used with automated pre-labeling at all — refused at the trigger, not silently
  unprotected.
- This guarantee covers the LLM pre-labeling pipeline only. It says nothing about other paths that
  read document text (e.g. `chat_api`'s retrieval-augmented answering) — those are governed by
  their own guardrails and are out of scope for this decision.
