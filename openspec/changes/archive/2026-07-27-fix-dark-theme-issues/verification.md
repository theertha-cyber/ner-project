# Verification Plan

**Change:** fix-dark-theme-issues
**Generated:** 2026-07-21
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Users Page Dark Mode | Given a logged-in user, when they navigate to Users page in dark mode, then all containers/text/borders use CSS variables | Visual inspection | - [ ] |
| 2 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Tenants Page Dark Mode | Given a logged-in user, when they navigate to Tenants page in dark mode, then all containers/text/borders/pagination use CSS variables | Visual inspection | - [ ] |
| 3 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Model Registry Page Dark Mode | Given a logged-in user, when they navigate to Model Registry in dark mode, then header/subtitle/loading skeleton use CSS variables | Visual inspection | - [ ] |
| 4 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Chat Page Dark Mode | Given a logged-in user, when they navigate to Chat page in dark mode, then error toast and empty state text use CSS variables | Visual inspection | - [ ] |
| 5 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Documents Page Dark Mode | Given a logged-in user, when they navigate to Documents page in dark mode, then page header text uses CSS variables | Visual inspection | - [ ] |
| 6 | dark-theme-consistency | Dark Theme Consistency Across Portal Pages | Imported Documents Page Dark Mode | Given a logged-in user, when they navigate to Imported Documents in dark mode, then headers/search fields/badges/table use CSS variables | Visual inspection | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | CSS variable naming | AI may invent CSS variable names not in globals.css | Compare all `var(--*)` references against globals.css definitions |
| 2 | Status badge colors | AI may use wrong dark mode class variants for badges | Verify `dark:bg-*` and `dark:text-*` classes match expected contrast |
| 3 | Inline style vs class | AI may inconsistently mix inline styles and Tailwind classes | Review each file for consistent approach (inline style preferred per design) |

---

## 3. Pattern & ADR Compliance

No constraining ADRs for this change — it is purely a visual styling fix.

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Users page renders correctly in dark mode with all CSS variables
- [ ] Tenants page renders correctly in dark mode with all CSS variables
- [ ] Model Registry page renders correctly in dark mode with all CSS variables
- [ ] Chat page error toast and empty state render correctly in dark mode
- [ ] Documents page header renders correctly in dark mode
- [ ] Imported Documents page renders correctly in dark mode with search fields and badges

### Structural Evidence

- [ ] Code review completed — all files use CSS variables from globals.css
- [ ] No hardcoded hex values remain in affected files
- [ ] No new dependencies introduced

### Edge Case Evidence

- [ ] CSS variable naming verified against globals.css definitions
- [ ] Status badge dark mode variants verified for proper contrast
- [ ] Inline style and class approach consistency verified

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|---|---------------------|--------------|------|
| 1 | | | | | |

---

## 6. Audit Record

**Change slug:** fix-dark-theme-issues
**Spec files reviewed:**
- specs/dark-theme-consistency/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
