## Why

The Azure Blob Storage connection detail screen spreads test, activation-evidence, and lifecycle controls across three disconnected panels in an order that doesn't match how an admin actually works the source (configure → watch it sync → manage its lifecycle), and the separate "Activation evidence" checklist asks the admin to re-attest to something the system already knows the moment the secure test passes. Creating a new connection also breaks the admin's place on the list by expanding an inline form panel instead of a focused, dismissible flow. A UI mockup (approved) resolves both: it merges the test/activation step into the Lifecycle panel as a single state-driven control, drops the redundant attestation checklist, reorders the detail panels, and moves connection creation into a modal.

## What Changes

- Reorder the connection detail panels to Connection details → Sync activity → Lifecycle (all providers; today's order is Connection facts/configuration → Lifecycle → Sync activity).
- Remove the standalone "Activation evidence" panel as its own section, and move the secure-test control and the two attestation checkboxes into the Lifecycle panel as one merged, state-driven flow: `Test connection` → `Testing…` → passed check appears, the two attestation checkboxes (`network_approved`, `governance_approved`) appear inline in the same control → `Activate` enables only once both are ticked → `Activated`. A failed test collapses the checkboxes away and returns the control to a retry state instead of exposing a disabled Activate button.
- The two attestation checkboxes are **not** removed and activation is **not** auto-submitted. `network_approved` and `governance_approved` represent real facts an admin confirms happened outside the system (network/security review, legal/residency review) — an early version of this proposal considered auto-submitting them once a test passed, but that would submit an attestation the admin never made; the requirement to explicitly tick both before Activate is preserved exactly, only their panel placement changes.
- Replace the inline "New connection" expand-in-place panel on `/settings/data-sources` with a modal dialog that lets the admin pick a provider and fill in its configuration without leaving or scrolling the list.

## Capabilities

### New Capabilities

(none — this reshapes existing portal UI behavior, it does not introduce a new capability)

### Modified Capabilities

- `tenant-data-source-portal`: connection detail panel order and lifecycle/test/activation UI consolidation (`Requirement: Safe connection lifecycle interface`); new-connection creation UI moves from inline panel to modal (`Requirement: Data source collection and navigation`).

## Impact

- Frontend only: [`src/portal/src/components/data-sources/lifecycle.tsx`](../../../src/portal/src/components/data-sources/lifecycle.tsx) (`LifecyclePanel`, `SyncActivitySummary`, `ProviderConfigForm` usage), [`src/portal/src/app/(auth)/settings/data-sources/[connectionId]/page.tsx`](../../../src/portal/src/app/(auth)/settings/data-sources/[connectionId]/page.tsx) (panel ordering), [`src/portal/src/app/(auth)/settings/data-sources/page.tsx`](../../../src/portal/src/app/(auth)/settings/data-sources/page.tsx) (New connection modal).
- No API, database, or backend change. `POST /api/v1/data-sources/{id}/activate` still requires and receives `activation_evidence: ["governance_approved", "network_approved"]`, and the admin still explicitly ticks both before the request can be sent — only their position on the page moves.
- Existing portal tests referencing the activation-evidence checkboxes, panel order, and inline create panel (`lifecycle.tsx` component tests, `[connectionId]/page.test.tsx`, `data-sources/page.test.tsx`) need updating to match the new markup.
- Azure Database for PostgreSQL connections keep the same Lifecycle panel (test/activate control, pause/replace/retire) and same panel reordering; they already omit the Sync activity schedule content per the existing safe-shape exemption.

## Open Questions

- None — UI direction was already validated against a working mockup before this proposal was written.
