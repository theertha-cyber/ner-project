# Proposal: Fix Dark Theme Issues Across Portal Pages

## Problem Statement

Multiple pages in the portal have inconsistent dark mode support. Some pages use CSS custom properties (design tokens) that respond to the dark mode toggle, while others use hardcoded Tailwind color classes (`bg-white`, `text-gray-900`, `bg-gray-50`, etc.) that remain in light theme regardless of the user's dark mode preference.

## Affected Pages

| Page | Issue | Roles Affected |
|---|---|---|
| Users | Light theme containers (hardcoded `bg-white`, `text-gray-900`, etc.) | Tenant Admin, System Admin |
| Tenants | Light theme containers (hardcoded `bg-white`, `text-gray-900`, etc.) | System Admin |
| Model Registry | Visibility issues (text colors don't adapt) | System Admin, Tenant Admin, Business User |
| Chat | Light theme container, hardcoded hex colors in inline styles | Business User, Tenant Admin |
| Document Upload | Partial dark mode (mixed CSS vars and hardcoded) | Tenant Admin, Annotator, Business User |
| Imported Docs | Search fields and containers missing dark mode | Tenant Admin, Annotator |

## Proposed Solution

Replace all hardcoded Tailwind color classes and inline style hex values with the project's existing CSS custom properties (design tokens) defined in `globals.css`. The tokens already have dark mode overrides under `:root.dark` — they just need to be referenced consistently.

## Key Tokens to Use

| Purpose | Light Token | Dark Token |
|---|---|---|
| Page background | `var(--surface)` | `var(--surface)` |
| Card/container | `var(--surface-2)` | `var(--surface-2)` |
| Subtle background | `var(--surface-3)` | `var(--surface-3)` |
| Primary text | `var(--ink)` | `var(--ink)` |
| Secondary text | `var(--ink-2)` | `var(--ink-2)` |
| Muted text | `var(--ink-3)` | `var(--ink-3)` |
| Borders | `var(--line)` | `var(--line)` |
| Hover state | `var(--surface-3)` | `var(--surface-3)` |

## Impact

- **Scope**: 6 page files in `src/portal/src/app/(auth)/`
- **Risk**: Low — CSS variables already swap correctly in dark mode; this is a find-and-replace of hardcoded colors with existing tokens
- **No new dependencies**: Uses existing CSS variables defined in `globals.css`
