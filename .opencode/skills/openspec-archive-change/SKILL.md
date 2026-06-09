---
name: openspec-archive-change
description: Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a change after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0"
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).
   Include the schema used for each change if available.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Check artifact completion status**

   Run `openspec status --change "<name>" --json` to check artifact completion.

   Parse the JSON to understand:
   - `schemaName`: The workflow being used
   - `artifacts`: List of artifacts with their status (`done` or other)

   **If any artifacts are not `done`:**
   - Display warning listing incomplete artifacts
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

3. **Check task completion status**

   Read the tasks file (typically `tasks.md`) to check for incomplete tasks.

   Count tasks marked with `- [ ]` (incomplete) vs `- [x]` (complete).

   **If incomplete tasks found:**
   - Display warning showing count of incomplete tasks
   - Use **AskUserQuestion tool** to confirm user wants to proceed
   - Proceed if user confirms

   **If no tasks file exists:** Proceed without task-related warning.

4. **Verification gate (spec-driven-verified schema only)**

   Check if `openspec/changes/<name>/verification.md` exists. If it does:

   a. **Read verification.md** and locate **§6 Audit Record**.

   b. **Parse all checkboxes** in the "Reviewer Sign-Off" and "AI Output Review" tables.
      Count `- [x]` (checked) vs `- [ ]` (unchecked).

   c. **Check the "Archive approved by" field** — it must not be blank or contain only
      underscores/placeholder text.

   d. **Hard block if ANY of these are true:**
      - Any checkbox in §6 is unchecked (`- [ ]`)
      - "Archive approved by" is blank or placeholder
      - §5 Evidence Log has no real entries (only template placeholder rows)

      Display:
      ```
      ⛔ ARCHIVE BLOCKED — verification.md gate not satisfied.

      Audit Record: X/Y checkboxes signed off
      Evidence Log: N entries (minimum 1 per spec scenario required)
      Archive approved by: <value or "MISSING">

      The spec-driven-verified schema requires a human reviewer to:
      1. Populate §5 Evidence Log with real evidence
      2. Complete all checkboxes in §6 Audit Record
      3. Sign the "Archive approved by" field

      This gate cannot be bypassed.
      ```

      **STOP — do not proceed to archive.** Do not offer a confirmation prompt to skip.
      This is a hard gate, not a warning.

   e. **If all checks pass:** Display "✓ Verification gate passed — §6 Audit Record signed off by <name>."
      Proceed to next step.

   **If verification.md does not exist:** Proceed without this check (non-verified schemas).

5. **Assess delta spec sync state**

   Check for delta specs at `openspec/changes/<name>/specs/`. If none exist, proceed without sync prompt.

   **If delta specs exist:**
   - Compare each delta spec with its corresponding main spec at `openspec/specs/<capability>/spec.md`
   - Determine what changes would be applied (adds, modifications, removals, renames)
   - Show a combined summary before prompting

   **Prompt options:**
   - If changes needed: "Sync now (recommended)", "Archive without syncing"
   - If already synced: "Archive now", "Sync anyway", "Cancel"

   If user chooses sync, use Task tool (subagent_type: "general-purpose", prompt: "Use Skill tool to invoke openspec-sync-specs for change '<name>'. Delta spec analysis: <include the analyzed delta spec summary>"). Proceed to archive regardless of choice.

6. **Perform the archive**

   Create the archive directory if it doesn't exist:
   ```bash
   mkdir -p openspec/changes/archive
   ```

   Generate target name using current date: `YYYY-MM-DD-<change-name>`

   **Check if target already exists:**
   - If yes: Fail with error, suggest renaming existing archive or using different date
   - If no: Move the change directory to archive

   ```bash
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

7. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Whether specs were synced (if applicable)
   - Note about any warnings (incomplete artifacts/tasks)

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Specs:** ✓ Synced to main specs (or "No delta specs" or "Sync skipped")

All artifacts complete. All tasks complete.
```

**Guardrails**
- Always prompt for change selection if not provided
- Use artifact graph (openspec status --json) for completion checking
- Don't block archive on warnings (incomplete artifacts/tasks) - just inform and confirm
- **EXCEPTION**: The verification.md §6 gate is a HARD BLOCK — never allow archive bypass when verification.md exists and §6 is incomplete
- Preserve .openspec.yaml when moving to archive (it moves with the directory)
- Show clear summary of what happened
- If sync is requested, use openspec-sync-specs approach (agent-driven)
- If delta specs exist, always run the sync assessment and show the combined summary before prompting
