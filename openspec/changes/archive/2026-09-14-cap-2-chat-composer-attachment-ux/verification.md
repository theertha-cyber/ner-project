# Verification Plan

**Change:** cap-2-chat-composer-attachment-ux
**Generated:** 2026-09-14
**Status:** ðŸŸ¢ Evidence collected â€” every Section 1 row backed by real vitest output from `npm run test --workspace=src/portal` (2026-09-14; 660 passed / 18 failed, all 18 pre-existing portal UI-drift failures in components untouched by this change) and a backend regression re-run (`poetry run python -m pytest tests/test_chat_api_conversations.py â€¦`, 109 passed / 1 failed â€” the recorded pre-existing `test_chat_response_sources` baseline / 2 skipped). Per run policy (human waiver in force for this run `chat-attachment-upload-20260910`), verification is fully automated: populated evidence plus a passing test run is sufficient; no human sign-off section is required or generated.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-composer-attachments | Chat attachment staging | Stage files before first send | Given a chat composer with no message sent yet, when a user selects one or more supported files, then the files appear in a staged attachment tray and no conversation is reserved or created until send | vitest: ChatInput staging test asserting tray renders staged file names; page test asserting no fetch occurs on pick | - [x] |
| 2 | chat-composer-attachments | Chat attachment staging | Remove a staged file before send | Given files staged in the tray, when the user activates a staged file's remove control, then that file leaves the tray and the others remain | vitest: ChatInput removal test asserting tray no longer shows the removed file and still shows the rest | - [x] |
| 3 | chat-composer-attachments | Chat attachment staging | Reject an unsupported file type | Given the composer's file input, when a user selects a file outside the supported set, then the file is not staged and the user sees an indication of the supported set | vitest: ChatInput rejection test asserting tray unchanged and an inline message appears | - [x] |
| 4 | chat-composer-attachments | Attachment-bearing send interaction | Send a message with staged attachments | Given staged files and typed message text, when the user sends, then the page passes message and attachment metadata in the same request body and clears the tray on success | vitest: page test asserting the send body carries `attachments` with filename/mime_type/file_size_bytes and tray clears after success | - [x] |
| 5 | chat-composer-attachments | Attachment-bearing send interaction | Failed send preserves staged attachments | Given staged files and a message, when the send fails, then the staged files remain in the tray and an error is shown | vitest: page test mocking a failed send asserting tray unchanged and error toast present | - [x] |
| 6 | chat-composer-attachments | Accessible attachment control | Keyboard users stage and remove attachments | Given the attachment control, when a keyboard user tabs to it, activates it, selects a file, and tabs to the remove control, then every control is keyboard-operable and exposes an accessible name | vitest: ChatInput accessibility test asserting buttons have accessible names and are focusable buttons; focus-visible styling present | - [x] |
| 7 | chat-composer-attachments | Accessible attachment control | Staged attachments do not enable send with an empty message | Given staged files and no message text, when the composer evaluates the send control, then the send control remains disabled until message text is present | vitest: ChatInput send-disabled test asserting send disabled with files only, enabled with text | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Send payload contract | AI may invent a multipart/FormData send or extra fields (`file_id`, `content`) not present in the CAP-3 `AttachmentInput` contract | Compare the page's send body against `ChatRequest.attachments` (`{filename, mime_type, file_size_bytes}`) â€” any other shape is a deviation |
| 2 | Conversation reservation (FR-006) | AI may call the create-conversation endpoint or an upload endpoint at file-pick time, reserving a conversation early | Test asserts no fetch fires on file selection; code review confirms staging is pure client state |
| 3 | Accepted file set | AI may hardcode a subset (e.g. only pdf/docx) or use `accept` alone, missing CSV or allowing unsupported types | Component test asserts the exact extension set `.pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.csv` and that a rejected file is not staged |
| 4 | Tray clear semantics | AI may clear the tray on every send attempt, discarding staged files on failure | Tests for both success (clears) and failure (preserves) must exist and pass |
| 5 | Styling tokens | AI may inline literal colors/radii rather than referencing `design-system/chat-attachment-upload/tokens.css` | ui-lint P0/P1 run over the portal source tree with the tokens file; no colour literals in new component styles |
| 6 | Accessibility | AI may ship the attach control as a non-focusable element, omit accessible names, or add `outline: none` without replacement | Component tests assert native buttons/inputs with aria-labels; visual check of focus-visible ring |

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-011 | Chat attachments are conversation-owned `documents` rows; retrieval and deletion are conversation-scoped | Nothing in the composer may create, reserve, or name a conversation before the user sends | Test asserts no `POST /api/v1/chat/conversations` (or any chat API) call happens on file pick |
| ADR-012 | CSV support is a branch in the existing ingestion pipeline | `.csv` is included in the composer's accepted file set | Component test asserts `.csv` file stages successfully |
| ADR-013 | Single-environment dev/local deployment with docker compose and recreate rollout | Portal changes deploy through the existing stack; no topology change | No new deployment artifact introduced by this change; portal test suite runs against the existing workspace |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 â€” test output proving the THEN was observed in a real execution.)*

- [x] Scenario 1: vitest output showing the staging test passes (tray renders staged file names; no conversation API call on pick)
- [x] Scenario 2: vitest output showing the removal test passes (removed file leaves tray, others remain)
- [x] Scenario 3: vitest output showing the unsupported-file rejection test passes (not staged, indication shown)
- [x] Scenario 4: vitest output showing the send test passes (body carries `attachments` metadata; tray clears on success)
- [x] Scenario 5: vitest output showing the failed-send test passes (tray preserved, error shown)
- [x] Scenario 6: vitest output showing the keyboard/accessibility test passes (accessible names, operable controls)
- [x] Scenario 7: vitest output showing the send-disabled test passes (files-only keeps send disabled)

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed â€” implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed âœ“
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigated â€” send body shape matches `ChatRequest.attachments` exactly (verified in page test assertions)
- [x] Risk 2 mitigated â€” no fetch on file pick (verified by test spy; code review)
- [x] Risk 3 mitigated â€” exact accept set asserted by component test, CSV included
- [x] Risk 4 mitigated â€” success-clear and failure-preserve both covered by passing tests
- [x] Risk 5 mitigated â€” ui-lint run reports no token violations in new component code
- [x] Risk 6 mitigated â€” keyboard/a11y test passes; focus ring uses `--focus-ring` token

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill â€” entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `ChatInput.test.tsx` "renders one tray entry per staged file plus the reserve hint (Scenario 1)" PASS and "makes no network calls when files are staged (ADR-011 / FR-006)" PASS (fetch spy not called); `page.test.tsx` "fires no additional API call when files are staged" PASS â€” vitest run 2026-09-14 | 1 | ralph (apply) | 2026-09-14 |
| 2 | Functional | `ChatInput.test.tsx` "removing a staged file leaves the other staged files (Scenario 2)" PASS â€” remove button wired to `onRemoveFile(id)`, sibling chips remain rendered | 2 | ralph (apply) | 2026-09-14 |
| 3 | Functional | `ChatInput.test.tsx` "rejects an unsupported extension with an inline alert and does not stage it (Scenario 3)" PASS and "stages only supported files from a mixed pick and alerts the rejection" PASS â€” `role="alert"` lists supported set; unsupported file not passed to `onAttach` | 3 | ralph (apply) | 2026-09-14 |
| 4 | Functional | `page.test.tsx` "sends attachment metadata with the message on the streaming path and clears the tray after success" and "â€¦on the non-streaming pathâ€¦" PASS â€” send body `attachments` deep-equals `[{filename, mime_type, file_size_bytes}]` on both `/api/v1/chat/stream` and `/api/v1/chat`; tray `region` gone after done frame / `resp.ok` | 4 | ralph (apply) | 2026-09-14 |
| 5 | Functional | `page.test.tsx` "preserves staged files and shows an error when the send fails (Scenario 5)" PASS â€” error frame â†’ toast `/Failed to get a response/`, `invoice.pdf` chip and "Staged attachments" region still present | 5 | ralph (apply) | 2026-09-14 |
| 6 | Functional | `ChatInput.test.tsx` "attach and remove controls expose accessible names and activate (Scenario 6)" PASS â€” native `<button>`s with `aria-label="Attach a file"` / `Remove <filename>` are enabled and the attach button opens the file dialog (input `.click()` spy); global `:focus-visible` ring in `globals.css` uses `--primary` outline + `--focus-ring` halo token | 6 | ralph (apply) | 2026-09-14 |
| 7 | Functional | `ChatInput.test.tsx` "keeps send disabled with files staged but no message text (Scenario 7)" PASS and "keeps send disabled while the disabled prop is set even with text" PASS | 7 | ralph (apply) | 2026-09-14 |
| 8 | Structural | Code review â€” implementation matches design.md decisions: client-side staging with zero server calls at pick, page-owned queue, `toChatAttachment` builds exactly `{filename, mime_type, file_size_bytes}`, tray clears on success only, send disabled rule unchanged, styling exclusively from `design-system/chat-attachment-upload/tokens.css` (theme entry point wired via `src/portal/src/app/layout.tsx`). No undocumented deviations | all | ralph (apply) | 2026-09-14 |
| 9 | Structural | ADR compliance â€” ADR-011: page test asserts no chat API call on pick; ADR-012: `ATTACH_ACCEPTED_EXTENSIONS` = `.pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.csv` asserted by component tests incl. `.csv` staging; ADR-013: no deployment artifact introduced. Backend regression re-run 2026-09-14: 109 passed / 1 failed (`test_chat_response_sources`, recorded pre-existing baseline) / 2 skipped | 1,3 | ralph (apply) | 2026-09-14 |
| 10 | Edge | Hallucination Risks: R1 body shape asserted exactly in page tests; R2 `fetchMock` call-count unchanged by staging in both component and page tests; R3 exact accept set asserted (CSV included); R4 success-clear (Scenario 4) and failure-preserve (Scenario 5) both pass; R5 `ui_lint.py src/portal/src --tokens design-system/chat-attachment-upload/tokens.css --include-p1` â†’ 0 findings in any CAP-2 file (11 P0 found are pre-existing in untouched components); R6 a11y tests pass + focus ring uses theme tokens | 1â€“7 | ralph (apply) | 2026-09-14 |

---

## 6. Verification Completion

> Per run policy (human waiver in force, run `chat-attachment-upload-20260910`): human
> sign-off is waived and no Audit Record / Reviewer Sign-Off section requiring a person
> to check boxes is generated. Completion is established when every Evidence item in
> Section 4 is satisfied by real test output and the portal test suite passes.