## Context

The connection detail route (`src/portal/src/app/(auth)/settings/data-sources/[connectionId]/page.tsx`) renders, in order: connection facts, an optional configuration-edit form, `LifecyclePanel` (secure test, activation-evidence checklist, pause/replace/retire), then `SyncActivitySummary`. `LifecyclePanel` gates activation on `testPassed && evidenceComplete`, where `evidenceComplete` is derived from two checkboxes (`network_approved`, `governance_approved`) that the admin must tick by hand. Per `docs/design/tenant-self-service-data-sources.md:80`, these two values are not UI busywork: `network_approved` represents validated private connectivity or an approved public-egress path, and `governance_approved` represents a reviewed data-residency/retention determination — real facts a human confirms happened outside the system, which `service.py` enforces exactly (rejects any `activation_evidence` that isn't precisely both values, once each, per ADR-011). What is disjointed is the checklist's *placement*, not its requirement: it sits in its own panel, sandwiched between the test control above and lifecycle actions below, when test → attest → activate is really one sequential flow the admin currently has to visually stitch together across a separate panel. The new-connection flow on `/settings/data-sources` toggles a `creating` boolean that expands `ProviderConfigForm` inline below the toolbar, pushing the table down and leaving no way to abandon the draft without manually re-collapsing the panel.

A working mockup (`azure-blob-mockup.html`, reviewed and approved after a first draft that incorrectly proposed auto-submitting the attestations was corrected) established the target UI: Connection details → Sync activity → Lifecycle ordering, a single merged Test/Attest/Activate control inside Lifecycle where the two attestation checkboxes appear inline once the test passes and remain a required, explicit tick before Activate enables, and a modal for new-connection creation. This design translates that mockup into the existing component structure.

## Goals / Non-Goals

**Goals:**

- Reorder detail-page sections to Connection details → Sync activity → Lifecycle for both providers.
- Merge the secure-test control and the attestation checklist into one stateful, sequential control living in the Lifecycle panel, replacing the separate Activation-evidence panel — without removing or weakening the attestation requirement itself.
- Preserve the existing activation contract exactly: `POST .../activate` still sends `activation_evidence: ["governance_approved", "network_approved"]`, activation still requires a passed test, and the admin still must explicitly tick both `network_approved` and `governance_approved` before Activate is reachable — only their panel placement changes, not their presence or their gating behavior.
- Replace the inline create-connection panel with a modal (reusing the existing `SlideOver` primitive already used for lifecycle confirmations) so creating a connection doesn't reflow the list.

**Non-Goals:**

- No API, schema, or lifecycle state-machine change. `useDataSourceMutation`, `useDataSource`, `useManualSyncMutation`, and every hook contract in `use-data-sources.ts` are untouched.
- No change to PostgreSQL's schedule/sync exemption or to schema-contract screens.
- No change to what the two evidence keys mean, how the backend validates them, or whether the admin must explicitly confirm them — this is a client-side layout change only. Removing or auto-submitting the attestation requirement was considered and explicitly rejected (see Decision 1); it would be a compliance-policy change requiring its own proposal, design, and ADR supersession, not something bundled into a UI reorganization.
- Not re-theming the portal or introducing new design tokens; the mockup deliberately reused `tokens.css` values already in `design-system/ner-portal/tokens.css`.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-011 Tenant-Scoped Azure Connection Control Plane | Activation requires a passed secure test plus recorded governance/network attestations before a connection can serve traffic. | The Activate action must still be gated on an admin explicitly confirming both attestations, and must still be unreachable without a passed test — this design changes only where and how that confirmation is presented, not whether it happens. |
| ADR-012 Durable Azure Blob Source Synchronization | Blob sync runs on a durable schedule/lease independent of the portal UI. | Sync activity panel keeps its existing data contract (`schedule`, `last_sync`, manual `Sync now`); only its position on the page and its container change. |

## Decisions

### Decision 1: Merge test, attestation, and activation into one sequential control — attestation checkboxes stay, no auto-submission

**Choice:** `LifecyclePanel` tracks a local `testOutcome: "untested" | "testing" | "passed" | "failed"` derived from `connection.last_test` on mount and from the `test` mutation's pending/success/error transitions thereafter, plus local `networkApproved`/`governanceApproved` boolean state for the two checkboxes. The merged control renders as:
- `untested`/`failed` → button reads "Test connection" (or "Retry test" after a failure), `onClick` fires the existing `test` action; attestation checkboxes are not rendered.
- `testing` → button disabled, reads "Testing…"; attestation checkboxes are not rendered.
- `passed` and connection not yet `active` → the passed check renders inline, and the two attestation checkboxes (`network_approved`, `governance_approved`) render directly below it in the same control, each with the explanatory text of what it confirms (private-connectivity/egress approval; residency/retention review). The "Activate" button renders but stays disabled until both checkboxes are checked; `onClick` (once enabled) fires the existing `activate` action with `activation_evidence: [...REQUIRED_ACTIVATION_EVIDENCE].sort()` — unchanged payload, sent only after the admin has explicitly ticked both boxes in this session.
- connection `active` → button disabled, reads "Activated"; checkboxes render checked and disabled as a record of what was confirmed.

A test failure (including a later retest that fails) collapses the attestation checkboxes away and resets their checked state, returning the control to the retry state — an admin can never activate on stale attestations paired with a test that no longer reflects "passed."

**Rationale:** The redundancy in the current UI is the checklist's *panel placement* — disconnected from the test result right above it — not its existence: `network_approved`/`governance_approved` are real, backend-enforced facts about external review that the system cannot infer from a passed test, so the admin's explicit tick is the only place that information can come from. An earlier version of this design proposed auto-submitting both values once a test passed, reasoning that the old code always sent the full evidence set on click regardless of which box was ticked; that reasoning was wrong — it looked at the payload shape, not at what the click itself represents; a click after ticking two labeled checkboxes is the actual attestation act. Keeping the transition sequential and state-driven (test → attest → activate, one control) still gets the presentational win the mockup was reviewed for — no separate panel, no re-deriving where you left off — without the admin's tick being system-inferred.

**Alternatives considered:**
- Keep two separate panels (Secure test; Activation evidence + Activate), just visually adjacent — ruled out: doesn't resolve the fragmentation the proposal is about, and doesn't match the reviewed mockup.
- Auto-submit `activation_evidence` once a test passes, no checkboxes — ruled out (see Rationale): submits an attestation the admin never made, which is a compliance-policy regression, not a UI simplification, and is out of scope for this change.
- Single confirmation dialog on Activate click, listing both attestation statements with one "Confirm and activate" button, instead of persistent inline checkboxes — considered and available as a lighter-weight alternative, but the inline-checkbox approach was selected because it keeps both attestation statements visible (not hidden behind a second click) while the admin decides, and matches the reviewed mockup.

### Decision 2: Reorder via straight JSX reordering in `DetailContent`, not a new layout abstraction

**Choice:** In `[connectionId]/page.tsx`, move the `<LifecyclePanel .../>` render call to after `<SyncActivitySummary .../>`. `SafeFacts` (connection details) already renders first and needs no change; drop its "Activation" row (`connection.activation.outcome · reason_code`) since that state now surfaces inline in the merged Lifecycle control instead of duplicating it in two places.

**Rationale:** The three sections are already independent, self-contained components (`SafeFacts`/config form, `SyncActivitySummary`, `LifecyclePanel`); no shared layout state depends on their order, so reordering is a one-line move with no structural risk.

**Alternatives considered:**
- Introduce a generic `<DetailSection order={...}>` wrapper — ruled out: three fixed, always-present sections don't need a configurable ordering abstraction; it would add indirection for a one-time reorder.

### Decision 3: New-connection modal reuses `SlideOver`'s internals as a centered dialog, not a right-edge panel

**Choice:** `/settings/data-sources` keeps its `creating` boolean state but instead of inline-rendering `ProviderConfigForm` in a `<section>`, it opens a new `CreateConnectionModal` component. Visually the mockup uses a centered dialog (not a right-edge slide-over) because the form is short and a centered modal reads as a discrete, focused task rather than a persistent side panel — but it reuses `SlideOver`'s accessibility internals (focus trap, `Escape` to close, restore focus to the trigger button, `role="dialog"`/`aria-modal`) via a small shared hook (`useFocusTrap`) extracted from `SlideOver` rather than duplicating that logic. `ProviderConfigForm` itself (provider select, field set, validation, submit) is reused unchanged inside the modal body.

**Rationale:** `SlideOver`'s behavior (focus trap, escape handling, portal render) is exactly what a modal needs and already exists and is tested; only its visual chrome (right-edge slide vs. centered) differs from the mockup, so extracting the reusable behavior avoids writing a second focus-trap implementation.

**Alternatives considered:**
- Use `SlideOver` as-is (right-edge panel) for the create flow — ruled out: doesn't match the reviewed mockup, and a right-edge panel is a better fit for an existing record's confirmation (its current use) than for starting a new one.
- Build a fully separate modal component with no code sharing — ruled out: would duplicate focus-trap/escape/portal logic that already exists and is tested in `SlideOver`.

## Risks / Trade-offs

- [Merging attestation into the same control as test/activate could visually read as one step and tempt a future edit to collapse it into an auto-submit, repeating the mistake this design corrected.] → Mitigation: the attestation checkboxes are explicit, separately labeled, individually required inputs inside the merged control, not an implicit side effect of the test passing; Decision 1's rationale and the Non-Goals section record explicitly why auto-submission was rejected, for future reference.
- [Extracting `useFocusTrap` from `SlideOver` touches a shared, tested component.] → Mitigation: extraction preserves `SlideOver`'s existing public API and behavior exactly (verified by its existing test suite continuing to pass unmodified); the hook is additive, not a rewrite.
- [Existing tests assert the old checklist panel, the old panel order, and the inline create panel.] → Mitigation: enumerated in tasks.md; each test file is updated in the same change, not left red.

## Migration Plan

1. Extract `useFocusTrap` from `SlideOver` (behavior-preserving refactor, existing `slide-over.test.tsx` must still pass unmodified).
2. Update `LifecyclePanel`: remove the standalone Activation-evidence panel, add the merged test → attest → activate sequential control (attestation checkboxes preserved, Activate gated on both being checked), update its unit tests.
3. Reorder `DetailContent` in `[connectionId]/page.tsx` (Connection details → Sync activity → Lifecycle) and drop the now-redundant `Activation` row from `SafeFacts`; update `page.test.tsx`.
4. Build `CreateConnectionModal` using `useFocusTrap` + existing `ProviderConfigForm`; wire it into `/settings/data-sources` in place of the inline panel; update `data-sources/page.test.tsx`.
5. Manual verification against the approved mockup states (draft → testing → tested-awaiting-attestation → activate-enabled → active) in a running portal, plus `npm test` for the touched files.

No backend deploy, no data migration, no feature flag — this is a same-release frontend change. Rollback is a plain revert of the frontend commit(s); no server-side or schema coordination is required either direction.

## Open Questions

None. No in-force ADR needs revisiting — ADR-011's activation gate and ADR-012's sync scheduling are both preserved as-is.
