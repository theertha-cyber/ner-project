---
name: openspec-verify-change
description: Verify implementation matches change artifacts. Use when the user wants to validate that implementation is complete, correct, and coherent before archiving. Schema-aware — if verification.md exists (spec-driven-verified schema), populates §1-§4 in-place.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.1"
  generatedBy: "1.2.0"
---

Verify that an implementation matches the change artifacts (specs, tasks, design).
If the change uses the `spec-driven-verified` schema (i.e., `verification.md` exists in the
change folder), this skill populates §1–§4 of that file in-place rather than generating
an ephemeral report.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show changes that have implementation tasks (tasks artifact exists).
   Include the schema used for each change if available.
   Mark changes with incomplete tasks as "(In Progress)".

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven-verified")
   - Which artifacts exist for this change

3. **Get the change directory and load artifacts**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns the change directory and context files. Read all available artifacts from `contextFiles`.

4. **Determine verification mode**

   Check if `openspec/changes/<name>/verification.md` exists.

   - **If YES → Schema-aware mode (steps 5A–8A)**
   - **If NO → Ephemeral report mode (steps 5B–8B)**

---

## Schema-Aware Mode (verification.md exists)

5A. **Populate §1 Spec Alignment**

   Read every spec file in `openspec/changes/<name>/specs/**/*.md`.

   For each `### Requirement:` block and each `#### Scenario:` within it:
   - Extract the capability name (parent folder name)
   - Extract the requirement name
   - Extract the scenario name
   - Compose an Acceptance Criterion by restating the GIVEN/WHEN/THEN as a single
     binary pass/fail assertion sentence

   Search the codebase for implementation evidence for each scenario:
   - Look for test files matching scenario keywords
   - Look for implementation files matching requirement keywords
   - If a test or implementation file is found, note it as the Verification Artifact

   **Write** the populated table into verification.md §1, replacing the template
   placeholder rows. Every scenario MUST appear as a row. Leave Status as `- [ ]`
   (unchecked) — the human reviewer checks these.

6A. **Populate §2 Hallucination Risk Register**

   Read `design.md` from the change folder. Identify areas of complexity:
   - New patterns or architectural choices
   - External dependencies or integrations
   - Data model changes (new fields, schemas, migrations)
   - Security controls or auth flows
   - Cross-cutting concerns (logging, error handling, retries)
   - Non-obvious edge cases from spec scenarios

   For each risk area (aim for 3–7, minimum 1 per design decision):
   - State what an AI agent might get wrong (be concrete — name specific fields,
     patterns, or behaviours that could be hallucinated)
   - State a human-checkable mitigation step

   **Proportionality rule**: For changes with ≤ 3 scenarios, 1–3 risks are sufficient.
   Do not pad with generic risks.

   **Write** the populated table into verification.md §2, replacing template rows.

7A. **Populate §3 Pattern & ADR Compliance**

   Read `design.md` and identify any references to existing ADRs (look for "ADR-"
   references, "Currently-In-Force ADRs" section, or decision constraints).

   For each referenced ADR:
   - Read the ADR file from `docs/adr/`
   - Extract the decision summary
   - State the constraint it imposes on this change
   - Define a concrete verification step (grep command, code review check, etc.)

   If no ADRs are referenced: Write "No constraining ADRs" with a single placeholder row.

   **Write** the populated table into verification.md §3, replacing template rows.

8A. **Populate §4 Evidence Requirements**

   Based on §1, §2, and §3:

   **Functional Evidence** — one checkbox item per scenario from §1:
   - Describe the specific observable proof needed (test name + expected output,
     screenshot description, or log excerpt format)

   **Structural Evidence** — keep the 4 standard items:
   - Code review completed — implementation matches design.md decisions
   - All ADR compliance steps in §3 confirmed
   - No undocumented architectural patterns introduced
   - No AI-invented requirements present in generated code

   **Edge Case Evidence** — one checkbox item per risk from §2:
   - State what the reviewer should check and what a pass looks like

   **Write** the populated items into verification.md §4, replacing template items.
   Leave all checkboxes unchecked (`- [ ]`).

9A. **Report completion**

   Display:
   ```
   ## verification.md updated

   §1 Spec Alignment: N scenarios mapped
   §2 Hallucination Risk Register: M risks identified
   §3 ADR Compliance: K ADRs checked
   §4 Evidence Requirements: P items defined

   §5 Evidence Log: ⏳ Awaiting human reviewer
   §6 Audit Record: ⏳ Awaiting human sign-off

   Next steps:
   1. Implement remaining tasks (if any)
   2. Collect evidence for each item in §4
   3. Have a human reviewer populate §5 and sign §6
   4. Run /opsx-archive when §6 is complete
   ```

---

## Ephemeral Report Mode (no verification.md)

5B. **Verify Completeness**

   **Task Completion**:
   - If tasks.md exists in contextFiles, read it
   - Parse checkboxes: `- [ ]` (incomplete) vs `- [x]` (complete)
   - Count complete vs total tasks
   - If incomplete tasks exist:
     - Add CRITICAL issue for each incomplete task
     - Recommendation: "Complete task: <description>" or "Mark as done if already implemented"

   **Spec Coverage**:
   - If delta specs exist in `openspec/changes/<name>/specs/`:
     - Extract all requirements (marked with "### Requirement:")
     - For each requirement:
       - Search codebase for keywords related to the requirement
       - Assess if implementation likely exists
     - If requirements appear unimplemented:
       - Add CRITICAL issue: "Requirement not found: <requirement name>"
       - Recommendation: "Implement requirement X: <description>"

6B. **Verify Correctness**

   **Requirement Implementation Mapping**:
   - For each requirement from delta specs:
     - Search codebase for implementation evidence
     - If found, note file paths and line ranges
     - Assess if implementation matches requirement intent
     - If divergence detected:
       - Add WARNING: "Implementation may diverge from spec: <details>"
       - Recommendation: "Review <file>:<lines> against requirement X"

   **Scenario Coverage**:
   - For each scenario in delta specs (marked with "#### Scenario:"):
     - Check if conditions are handled in code
     - Check if tests exist covering the scenario
     - If scenario appears uncovered:
       - Add WARNING: "Scenario not covered: <scenario name>"
       - Recommendation: "Add test or implementation for scenario: <description>"

7B. **Verify Coherence**

   **Design Adherence**:
   - If design.md exists in contextFiles:
     - Extract key decisions (look for sections like "Decision:", "Approach:", "Architecture:")
     - Verify implementation follows those decisions
     - If contradiction detected:
       - Add WARNING: "Design decision not followed: <decision>"
       - Recommendation: "Update implementation or revise design.md to match reality"
   - If no design.md: Skip design adherence check, note "No design.md to verify against"

   **Code Pattern Consistency**:
   - Review new code for consistency with project patterns
   - Check file naming, directory structure, coding style
   - If significant deviations found:
     - Add SUGGESTION: "Code pattern deviation: <details>"
     - Recommendation: "Consider following project pattern: <example>"

8B. **Generate Verification Report**

   **Summary Scorecard**:
   ```
   ## Verification Report: <change-name>

   ### Summary
   | Dimension    | Status           |
   |--------------|------------------|
   | Completeness | X/Y tasks, N reqs|
   | Correctness  | M/N reqs covered |
   | Coherence    | Followed/Issues  |
   ```

   **Issues by Priority**:

   1. **CRITICAL** (Must fix before archive):
      - Incomplete tasks
      - Missing requirement implementations
      - Each with specific, actionable recommendation

   2. **WARNING** (Should fix):
      - Spec/design divergences
      - Missing scenario coverage
      - Each with specific recommendation

   3. **SUGGESTION** (Nice to fix):
      - Pattern inconsistencies
      - Minor improvements
      - Each with specific recommendation

   **Final Assessment**:
   - If CRITICAL issues: "X critical issue(s) found. Fix before archiving."
   - If only warnings: "No critical issues. Y warning(s) to consider. Ready for archive (with noted improvements)."
   - If all clear: "All checks passed. Ready for archive."

---

**Verification Heuristics**

- **Completeness**: Focus on objective checklist items (checkboxes, requirements list)
- **Correctness**: Use keyword search, file path analysis, reasonable inference - don't require perfect certainty
- **Coherence**: Look for glaring inconsistencies, don't nitpick style
- **False Positives**: When uncertain, prefer SUGGESTION over WARNING, WARNING over CRITICAL
- **Actionability**: Every issue must have a specific recommendation with file/line references where applicable

**Graceful Degradation**

- If only tasks.md exists: verify task completion only, skip spec/design checks
- If tasks + specs exist: verify completeness and correctness, skip design
- If full artifacts: verify all three dimensions
- Always note which checks were skipped and why

**Output Format**

Use clear markdown with:
- Table for summary scorecard
- Grouped lists for issues (CRITICAL/WARNING/SUGGESTION)
- Code references in format: `file.ts:123`
- Specific, actionable recommendations
- No vague suggestions like "consider reviewing"
