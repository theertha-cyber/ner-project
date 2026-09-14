## 1. Persistent two-stage layout

- [x] 1.1 Split the Tenant Admin's view into `TwoStageBatchFlow`, with a separate
      `usePrelabelBatch` query per stage (initial and large), and keep the Annotator Admin's
      single-batch review view (`ReviewOnlyBatch`) unchanged
- [x] 1.2 Stage 1 ("Initial validation batch") always shows its own picker, status, or approval
      confirmation — never replaced by stage 2's content
- [x] 1.3 Stage 2 ("Large batch") is visible once stage 1 exists: locked message before
      approval, its own picker (no cap) once unlocked, and its own status/Train-model action
      once created
- [x] 1.4 Relocate the rejected-initial-batch "Start a new validation batch" action into
      stage 1's own section
- [x] 1.5 `useCreatePrelabelBatch` invalidates the batch list query in addition to the singular
      one, so a newly created batch's stage appears without waiting on a poll

## 2. Notifications

- [x] 2.1 Toast once when the initial batch is observed to become Annotator-approved (edge
      detection via `useRef`, not fired on every render)
- [x] 2.2 Toast once when the large batch is observed to reach a completed/partially-completed
      state

## 3. Verification & Evidence

- [x] 3.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec
      Alignment and confirm all pass
- [x] 3.2 Collect functional evidence for each scenario — one entry per row in verification.md
      § Evidence Log
- [x] 3.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination
      Risk Register
- [x] 3.4 Confirm no ADR compliance steps apply (verification.md § Pattern & ADR Compliance)
- [x] 3.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer
      required — see caveat: this is the implementing agent's own re-inspection, not an
      independent human review)
- [x] 3.6 Run `openspec validate automated-batch-stage-visibility --type change --strict`
      before archive
