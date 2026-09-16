## 1. Make the large-batch upload repeatable

- [x] 1.1 Show the document picker whenever `largeUnlocked`, regardless of whether a previous
      `large` batch exists
- [x] 1.2 Label the most recent `large` batch's status section distinctly ("Most recent large
      batch") so it reads as history, not a blocker
- [x] 1.3 Disable the submit button (with an explanatory message) only while the most recent
      `large` batch is queued or processing

## 2. Verification & Evidence

- [x] 2.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec
      Alignment and confirm all pass
- [x] 2.2 Collect functional evidence for each scenario — one entry per row in verification.md
      § Evidence Log
- [x] 2.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination
      Risk Register
- [x] 2.4 Confirm no ADR compliance steps apply
- [x] 2.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer
      required — see caveat: this is the implementing agent's own re-inspection, not an
      independent human review)
- [x] 2.6 Run `openspec validate large-batch-repeatable-upload --type change --strict` before
      archive
