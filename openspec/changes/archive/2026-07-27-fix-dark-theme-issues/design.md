# Design: Fix Dark Theme Issues Across Portal Pages

## Architecture

The project uses a class-based dark mode via Tailwind's `darkMode: "class"` combined with CSS custom properties. All color tokens are defined in `globals.css` under `:root` (light) and `:root.dark` (dark). The `.dark` class is toggled on `<html>` by the `useDarkMode` hook.

The problem is that many pages bypass this system by using hardcoded Tailwind color classes (`bg-white`, `text-gray-900`, etc.) or inline hex values (`#fef2f2`), which don't respond to the dark mode toggle.

## Approach

### Conversion Strategy

Replace all hardcoded colors with CSS custom properties using inline `style` attributes. This is the pattern already established by dark-mode-aware pages like `training-jobs/page.tsx`.

**Why inline styles?** The Tailwind config (`tailwind.config.ts`) does map CSS variables to color utilities, but many utilities are missing (no `text-ink`, `bg-surface-2`, etc. defined as Tailwind classes). Using `style={{ color: "var(--ink)" }}` directly is more reliable and matches the existing pattern in `training-jobs/page.tsx` and `widget-keys/page.tsx`.

### Color Mapping

| Hardcoded Class/Value | CSS Variable Replacement |
|---|---|
| `text-gray-900` | `var(--ink)` |
| `text-gray-700` | `var(--ink-2)` |
| `text-gray-600` | `var(--ink-2)` |
| `text-gray-500` | `var(--ink-3)` |
| `text-gray-400` | `var(--ink-3)` |
| `bg-white` | `var(--surface-2)` |
| `bg-gray-50` | `var(--surface-3)` |
| `bg-gray-100` | `var(--surface-3)` |
| `border-gray-200` | `var(--line)` |
| `hover:bg-gray-50` | `var(--surface-3)` |
| `hover:bg-gray-300` | `var(--ink-3)` (muted hover) |
| `#9ca3af` (inline) | `var(--ink-3)` |
| `#fef2f2` (error bg inline) | `var(--bad-soft)` |
| `#991b1b` (error text inline) | `var(--bad)` |
| `#fecaca` (error border inline) | `var(--bad)` |

### Status Badges (active/inactive)

Status badges (`bg-green-100 text-green-800`, `bg-red-100 text-red-800`) need conditional dark mode styling. Since there are no dedicated badge tokens in `globals.css`, we'll use a small utility function that returns `style` objects with appropriate contrast for both modes.

Approach: Use `className` with a conditional `dark:` prefix — Tailwind will handle it because `darkMode: "class"` is enabled. Example:
```
className={`${status === "active" ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"}`}
```

### Files to Modify

1. `src/portal/src/app/(auth)/users/page.tsx` — Full conversion
2. `src/portal/src/app/(auth)/admin/tenants/page.tsx` — Full conversion
3. `src/portal/src/components/model-registry/ModelRegistryPage.tsx` — Header and text colors
4. `src/portal/src/app/(auth)/chat/page.tsx` — Inline hex values to CSS vars
5. `src/portal/src/app/(auth)/documents/page.tsx` — Header text color
6. `src/portal/src/app/(auth)/imported-documents/page.tsx` — Headers, search fields, table

### Style Convention

Convert hardcoded Tailwind classes to inline `style` attributes:
```tsx
// Before
<h1 className="text-2xl font-bold text-gray-900">Users</h1>

// After
<h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Users</h1>
```

For border-bottom patterns:
```tsx
// Before
<div className="border-b border-gray-200">

// After
<div style={{ borderBottom: "1px solid var(--line)" }}>
```

## Risks

- **Low risk**: All CSS variables already exist and swap correctly in dark mode
- **No functional changes**: Only visual styling is affected
- **No new dependencies**: Uses existing infrastructure
