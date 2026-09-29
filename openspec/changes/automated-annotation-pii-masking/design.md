## Context

`extract_and_ground_document` (`worker.py`) is the single implementation both the single-document
LLM pre-labeling job and the batch job (`seed-bootstrap`) run through — its own docstring states
this is deliberate, so the two paths cannot silently drift. It currently loads the real document
text, sends it in full to the external LLM provider (`AzureOpenAIClient.complete_json`), and
grounds the response against that same real text. `entity-sensitivity-classification` added a
`sensitivity` tier to each entity type but wired it into nothing. This change makes `sensitivity`
take effect at the one place it needs to: before the document text crosses the boundary into
`client.complete_json`.

## Goals / Non-Goals

**Goals**
- Guarantee that an entity type's real values never reach the external LLM provider once that
  type is classified `pattern` or `local_only`.
- Reuse detection mechanisms that already exist rather than building new ones: `validation_rule`
  regexes (already on every entity type) and the tenant's own hosted extraction model
  (`model_serving`'s `/internal/v1/infer`, already used for real-time pre-labeling suggestions
  during manual annotation via `base_label_mapping`).
- Keep the reviewer-facing behavior — what gets stored in `suggested_spans`, what a human reviews
  and approves — unchanged. Masking is invisible past the external LLM call.
- Fail closed: any failure in local detection blocks the external call rather than falling back
  to sending unmasked text.

**Non-Goals**
- A general-purpose PII detection library or a new local NER model. This change wires up detection
  mechanisms the platform already has.
- Solving local detection for a `local_only` type with no `base_label_mapping` — refused outright
  (see **Local-Only Type Coverage Requirement**), not worked around.
- Anything about the keyword pre-labeling path, which never called an external LLM and is
  unaffected.
- A tenant-level rollout/enablement gate for this behavior — flagged as an Open Question in
  proposal.md, left to product direction.

## Decisions

**Detection runs against the real text; only the copy is masked.** `mask_document` receives
`document_text` (the real thing) and produces `masked_text` plus the offset map — detection has to
see the real text to find spans in it. The real text itself never crosses into `build_user_payload`
or `client.complete_json`; only `masked_text` does. This is the one invariant the whole change
exists to hold, which is why it is recorded as ADR-015 (see below) rather than left as an
implementation detail.

**Pattern detection is pure; local-model detection is I/O behind a client protocol.** Regex
matching against `validation_rule` needs no network and is tested the way `llm_prelabel.py`'s
existing pure functions are (`ground_quote`, `parse_llm_response`) — text in, spans out, no stub
required. Calling `model_serving` is real I/O, so it goes behind a `LocalModelClient` Protocol with
a `StubLocalModelClient`, mirroring `llm_client.py`'s existing `LLMClient` /
`StubLLMClient` split — the same reason that split exists here: the provider is the one thing
tests must not reach.

**Local-model detection reuses `base_label_mapping`, not a new mapping.** `model_serving`'s
`/internal/v1/infer` returns CoNLL-class token predictions (PER/ORG/LOC/MISC); `entity-config`'s
existing **Base Label Mapping** requirement already maps those classes to tenant entity types for
real-time pre-labeling suggestions during manual annotation. This change is a second consumer of
the same mapping, not a new one — a `local_only` type is locally detectable exactly when it is
already eligible to receive base-model pre-labels today.

**A `local_only` type with no `base_label_mapping` blocks the trigger, not just a warning.** The
alternative — running pre-labeling anyway and silently sending that type's real values to the
external LLM because no local mechanism could find them — is precisely the failure this whole
change exists to prevent. Refusing at the trigger endpoint (422 `LOCAL_ONLY_TYPE_NOT_COVERED`)
matches the existing pattern of enforcing a business rule at the API layer rather than only in the
portal (the same reasoning `annotation-workflow-review-simplification`'s design.md gives for the
`INITIAL_BATCH_NOT_APPROVED` check).

**Fail-closed on detection failure, deliberately the opposite of the domain classifier's fail-open.**
`GuardrailService._classify_once` (chat_api) fails open on purpose — it is a scope/cost filter, not
a security boundary, and tenant isolation is enforced structurally elsewhere. Masking *is* the
security boundary here: there is no downstream check that would catch real PII that reached the
external LLM because local detection silently failed. So if the local model call errors, times
out, or a `validation_rule` fails to compile, `extract_and_ground_document` raises before
`client.complete_json` is ever called, and the job records a failure distinguishable from an
external-provider failure (`LLMUnavailable` vs. a new `LocalDetectionUnavailable`).

**Placeholders are stable per unique exact text within one document.** The same detected substring
(e.g. the same child's name appearing three times) maps to the same placeholder token
(`⟦PERSON_1⟧` every time), and a different value of the same type gets a different index
(`⟦PERSON_2⟧`). This preserves the external LLM's ability to reason about relationships within the
`open`-type extraction it is still doing ("the contract between ⟦PERSON_1⟧ and Acme Corp") without
ever revealing which real value a placeholder stands for. Matching is exact-text, case-sensitive,
within one document only — no cross-document identity is implied or persisted.

**Grounding runs against the masked copy; offsets translate back before storage.** The external
LLM's returned quotes are grounded against `masked_text` using the existing exact-match rule
(`ground_quote`), completely unchanged. What's new is a translation step: a grounded offset in
`masked_text` maps back to the corresponding offset in `document_text` via the segment table
`mask_document` produced. A quote that grounds inside what used to be a placeholder cannot occur
in practice (the external prompt never asks for entity types that would match placeholder text),
but if it did, the translation step drops it rather than storing a corrupted offset — the same
"a wrong offset is worse than a missing suggestion" principle `ground_quote`'s own docstring
already states.

**Cache key gains `sensitivity`, `validation_rule`, and `base_label_mapping`.**
`entity_config_version.CONFIG_FIELDS` currently hashes `name`, `description`, `examples`,
`qa_examples`. A tenant reclassifying a type from `open` to `local_only` changes what prompt gets
built and what gets sent externally, but changes none of those four fields — so today's cache
would serve a stale (pre-reclassification, unmasked) result indefinitely. The same is true one
level down: tightening a `pattern` type's `validation_rule`, or changing a `local_only` type's
`base_label_mapping`, changes what local detection finds — and therefore the final merged
result — without changing the external prompt at all. All three fields are added to the hashed
set so any of these edits busts the cache the same way adding a QA pair already does.

## Risks / Trade-offs

- **[Risk]** A `pattern` type's `validation_rule` is too loose or too strict, under- or
  over-matching real values. → **Mitigation**: this is a pre-existing property of
  `validation_rule` as a validation regex, not new risk this change introduces; `entity-
  sensitivity-classification`'s design.md already flagged this and left the judgment call to
  whoever configures the type.
- **[Risk]** `model_serving` becomes a hard dependency of LLM pre-labeling for any tenant with a
  `local_only` type, where it was not a dependency before. → **Mitigation**: deliberate and
  necessary — fail-closed means exactly this coupling. `model_serving`'s own availability
  characteristics are unchanged by this work; a tenant with no `pattern`/`local_only` types calls
  it zero times, same as today.
- **[Trade-off]** A `local_only` type with no `base_label_mapping` cannot use automated
  pre-labeling at all, not even for its `open`-type siblings in the same document. Accepted:
  scoping the refusal to "this document's batch" rather than "this one entity type" would require
  partial-document extraction with an entity type silently dropped, which is a worse failure mode
  to reason about than a clear, named 422 at trigger time.
- **[Trade-off]** Placeholder tokens (`⟦PERSON_1⟧`) are a made-up delimiter chosen to be unlikely
  to collide with real document text. A document that happens to already contain that exact
  bracket character is not specifically guarded against; accepted as low-probability and
  detectable (grounding would simply treat it as ordinary text with no special meaning, since only
  `mask_document`'s own segment table — not string matching — identifies which spans are
  placeholders).

**Recorded as ADR-015** (`docs/adr/015-no-sensitive-entity-text-to-external-llm.md`): the guarantee
that `pattern`/`local_only` entity type values never reach the external LLM provider is a durable
policy commitment, not a tactical detail of this change — a future change that adds a new
consumer of document text in the pre-labeling path (a different provider, a new extraction mode)
must explicitly honor or supersede this ADR rather than reintroduce the exposure this change
removes.

## Migration Plan

Deploy the `050` migration (additive CHECK-constraint widening, reversible) before or together
with the backend change — the new `source` values are only ever written by the new code, so
ordering between them is not load-bearing. No document data changes. Rollback is a plain revert of
both; a `pattern`/`local_only`-sourced span written under the new code would fail the old CHECK
constraint on downgrade, so downgrade should only be performed after confirming no such rows exist
(mirroring the reversibility caveat `038b` itself documents for its own CHECK constraint).

## Open Questions

Carried from proposal.md: the tenant-reclassification rollout gate, and whether unmapped
`local_only` types deserve a dedicated future detection path.
