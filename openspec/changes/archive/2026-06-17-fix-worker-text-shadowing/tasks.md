## 1. Fix Variable Shadowing

- [x] 1.1 In `src/extraction_service/worker.py`, rename `text = text_resp.json().get("text", "")` to `doc_text = text_resp.json().get("text", "")` (line ~120)
- [x] 1.2 Update the immediately following usage `tokens = text.split()` to `tokens = doc_text.split()` (line ~121)
- [x] 1.3 Confirm `from sqlalchemy import text, create_engine` import at the top of the file is unchanged
- [x] 1.4 Confirm every `conn.execute(text(...))` call in the file still uses the SQLAlchemy `text()` helper (no accidental renames)

## 2. Verification & Evidence

- [ ] 2.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 2.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 2.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 2.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 2.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 2.6 Run `openspec validate fix-worker-text-shadowing --type change --strict` and confirm it exits clean before archive.
