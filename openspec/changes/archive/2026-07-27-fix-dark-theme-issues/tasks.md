# Tasks: Fix Dark Theme Issues Across Portal Pages

## Overview

Replace hardcoded Tailwind color classes and inline hex values with CSS custom properties (design tokens) so all pages respond to the dark mode toggle correctly.

---

## Task 1: Fix Users Page ✓

**File**: `src/portal/src/app/(auth)/users/page.tsx`

**What to change**:
- Replace `text-gray-900` → inline `style={{ color: "var(--ink)" }}`
- Replace `text-gray-700` → inline `style={{ color: "var(--ink-2)" }}`
- Replace `text-gray-600` → inline `style={{ color: "var(--ink-2)" }}`
- Replace `text-gray-500` → inline `style={{ color: "var(--ink-3)" }}`
- Replace `bg-white` → inline `style={{ background: "var(--surface-2)" }}`
- Replace `bg-gray-50` → inline `style={{ background: "var(--surface-3)" }}`
- Replace `border-gray-200` → inline `style={{ borderColor: "var(--line)" }}`
- Replace `hover:bg-gray-50` → inline `style={{ background: "var(--surface-3)" }}` with hover
- Replace `bg-gray-200 hover:bg-gray-300` → inline dark mode compatible styles
- Fix status badge colors: add `dark:` Tailwind variants for `bg-green-100 text-green-800` and `bg-red-100 text-red-800`
- Replace `text-red-600 hover:text-red-800` → use `dark:text-red-400` variant

**Acceptance Criteria**:
- All containers, text, and borders in the Users page use CSS variables
- Status badges have dark mode variants
- Page looks correct in both light and dark mode

---

## Task 2: Fix Tenants Page ✓

**File**: `src/portal/src/app/(auth)/admin/tenants/page.tsx`

**What to change**:
- Replace `text-gray-900` → inline `style={{ color: "var(--ink)" }}`
- Replace `text-gray-500` → inline `style={{ color: "var(--ink-3)" }}`
- Replace `bg-white` → inline `style={{ background: "var(--surface-2)" }}`
- Replace `bg-gray-50` → inline `style={{ background: "var(--surface-3)" }}`
- Replace `divide-gray-200` → inline `style={{ borderColor: "var(--line)" }}`
- Replace `border-gray-200` → inline `style={{ borderColor: "var(--line)" }}`
- Replace `hover:bg-gray-50` → inline `style={{ background: "var(--surface-3)" }}`
- Fix status badge colors: add `dark:` Tailwind variants
- Fix pagination buttons: `bg-white` → `var(--surface-2)`

**Acceptance Criteria**:
- All containers, text, borders, and pagination use CSS variables
- Status badges have dark mode variants
- Page looks correct in both light and dark mode

---

## Task 3: Fix Model Registry Page ✓

**File**: `src/portal/src/components/model-registry/ModelRegistryPage.tsx`

**What to change**:
- Replace `text-gray-400` → inline `style={{ color: "var(--ink-3)" }}`
- Replace `text-gray-900` → inline `style={{ color: "var(--ink)" }}`
- Replace `text-gray-500` → inline `style={{ color: "var(--ink-3)" }}`
- Replace `bg-gray-100` (loading skeleton) → inline `style={{ background: "var(--surface-3)" }}`

**Acceptance Criteria**:
- Header text and subtitle use CSS variables
- Loading skeleton adapts to dark mode
- Page looks correct in both light and dark mode

---

## Task 4: Fix Chat Page ✓

**File**: `src/portal/src/app/(auth)/chat/page.tsx`

**What to change**:
- Replace inline `background: "#fef2f2"` → `background: "var(--bad-soft)"`
- Replace inline `color: "#991b1b"` → `color: "var(--bad)"`
- Replace inline `border: "1px solid #fecaca"` → `border: "1px solid var(--bad)"`
- Replace inline `color: "#9ca3af"` (empty state text) → `color: "var(--ink-3)"`

**Acceptance Criteria**:
- Error toast adapts to dark mode
- Empty state text adapts to dark mode
- Page looks correct in both light and dark mode

---

## Task 5: Fix Documents Page ✓

**File**: `src/portal/src/app/(auth)/documents/page.tsx`

**What to change**:
- Replace `text-gray-900` → inline `style={{ color: "var(--ink)" }}`

**Acceptance Criteria**:
- Page header text adapts to dark mode

---

## Task 6: Fix Imported Documents Page ✓

**File**: `src/portal/src/app/(auth)/imported-documents/page.tsx`

**What to change**:
- Replace `text-gray-900` → inline `style={{ color: "var(--ink)" }}`
- Replace `text-gray-500` → inline `style={{ color: "var(--ink-3)" }}`
- Replace `hover:bg-gray-50` → inline `style={{ background: "var(--surface-3)" }}` with hover
- Replace `bg-white` (token display area) → inline `style={{ background: "var(--surface-2)" }}`
- Replace `text-gray-700` → inline `style={{ color: "var(--ink-2)" }}`
- Fix status text colors: add `dark:` variants for `text-green-600` and `text-amber-600`
- Fix entity type badges: add `dark:` variants for `bg-blue-100 text-blue-700`
- Fix search input fields: ensure background/text colors work in dark mode

**Acceptance Criteria**:
- All headers, text, containers, and badges use CSS variables
- Entity type badges and status indicators adapt to dark mode
- Search fields have proper dark mode styling
- Page looks correct in both light and dark mode

---

## Verification

After all tasks are complete:
1. Run `npm run lint` from `src/portal/` to check for lint errors
2. Run `npm run build` from `src/portal/` to verify no build errors
3. Visually verify each page in both light and dark mode
