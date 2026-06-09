## 1. <!-- Task Group Name (e.g., Setup) -->

- [ ] 1.1 <!-- Task description -->
- [ ] 1.2 <!-- Task description -->

## 2. <!-- Task Group Name (e.g., Core Implementation) -->

- [ ] 2.1 <!-- Task description -->
- [ ] 2.2 <!-- Task description -->

<!-- Add more groups as needed. Keep tasks small enough to complete in one session.
     Order by dependency — what must be done first?

     For every spec scenario in verification.md § Spec Alignment, include a paired
     verification task here and fill in the "Verification Artifact" column in
     verification.md for that row. -->

## N. Verification & Evidence

<!-- Replace N with the next group number. This group is REQUIRED and must be
     the final group in every tasks.md produced by this schema. -->

- [ ] N.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [ ] N.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [ ] N.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [ ] N.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] N.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [ ] N.6 Run `openspec validate <change> --type change --strict` and confirm
         it exits clean before archive.
