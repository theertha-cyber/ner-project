## Context

`automated-annotation-pii-masking` needs a way to know, per entity type, whether that type's real
values are allowed to reach the external LLM provider during pre-labeling. Nothing today
distinguishes `person_name` on a foster-care tenant from `organization` on a resume tenant — both
are simply "an active entity type" as far as `llm_prelabel.py` and `extract_and_ground_document`
are concerned. This change introduces the classification as its own step so the masking mechanism
in the follow-up change has a stable, already-reviewable contract to build against, rather than
inventing the taxonomy and the pipeline change together.

## Goals / Non-Goals

**Goals**
- Give every entity type a `sensitivity` tier: `open`, `pattern`, or `local_only`.
- Make `pattern` carry its own detection shape by reusing the existing `validation_rule` field,
  rather than adding a second regex column.
- Ship as a purely additive, non-breaking change: no existing behavior changes.

**Non-Goals**
- Making LLM pre-labeling, or anything else, actually read or act on `sensitivity`. That is
  entirely `automated-annotation-pii-masking`'s job.
- Per-tenant enablement/rollout gating of the masking behavior — that decision belongs to the
  change that has behavior to gate.
- Retroactively reclassifying any existing tenant's entity types. Backfill is mechanical
  (`open` for every row), not judgment-based.

## Decisions

**Three tiers, not a boolean.** A plain `is_sensitive` flag can't distinguish "has a fixed shape a
regex can catch" (`pattern`: SSN, phone, email) from "free text that needs a model to find"
(`local_only`: person names, addresses). The follow-up change needs that distinction to decide
*which* local mechanism runs, so it belongs in the classification, not inferred later from the
type's other fields.

**`pattern` reuses `validation_rule` instead of a new column.** `validation_rule` already exists
as "an optional regex or type constraint" on every entity type (`entity-config` capability,
Entity Type Definition). A `pattern`-sensitivity type's detection shape and its validation shape
are the same regex — a value that doesn't match the pattern isn't a plausible SSN either way.
Rejected alternative: a dedicated `detection_pattern` column — it would duplicate a field that
already means the same thing, for no gain.

**`sensitivity` defaults to, and existing rows backfill to, `open`.** This is a data-modeling
change: adding the column must not itself change what LLM pre-labeling does today, and today it
sends every active entity type's data externally without restriction — so `open` is the value
that accurately describes the pre-existing, unchanged behavior. The safer "default unclassified
types closed" instinct is deliberately not applied at this layer; it is a policy decision about
*when masking takes effect*, which belongs to the change that implements masking, not to this
column's default (see Open Questions in proposal.md).

**`sensitivity` is mutable, unlike `provenance`.** `provenance` (added in
`2026-09-10-entity-type-provenance`) is immutable because it records history — how the type came
to exist. `sensitivity` is an ongoing policy setting a Tenant Admin may need to correct (a type
created as `open` turns out to carry PII after all), so it follows the same update-and-bump-version
path as `description` or `examples`, with no immutability constraint.

**Validated at the same point as `value_kind`.** The `pattern`-requires-`validation_rule` check
sits beside the existing "reject an unsupported `value_kind`" check in the create/update handlers
— one more field-consistency rule in the place all the others already live, not a separate
validation pass.

## Risks / Trade-offs

- **[Risk]** A Tenant Admin picks `pattern` for a type whose values don't actually follow a fixed
  shape (e.g. `case_notes`), giving the follow-up change's regex detector nothing reliable to
  find, and creating false confidence that the type is protected once masking ships.
  → **Mitigation**: this change validates that a `validation_rule` is *present*, not that it is
  well-formed for the type's real values — that judgment call belongs to whoever configures the
  type. The follow-up change's design should surface a document's actual pattern-detection hit
  count somewhere reviewable, so a `pattern` type that never matches anything is visible rather
  than silently doing nothing.
- **[Trade-off]** Every pre-existing entity type across every tenant backfills to `open`,
  including ones that, in hindsight, should be `local_only`. Accepted: correcting this is a
  one-time review a Tenant Admin performs once the classification exists to set, not something a
  migration can decide on their behalf.

## Migration Plan

Additive column with a default; no backfill logic beyond the column default itself. Rollback is a
plain column drop — no other table references `sensitivity` yet. Deploy backend, database
migration, and frontend together; no ordering constraint between them since the field is optional
on write (defaults applied server-side) and additive on read.

## Open Questions

Carried from proposal.md: whether tenant reclassification before `automated-annotation-pii-masking`
ships is a manual rollout task or a code-enforced gate is left to that change.
