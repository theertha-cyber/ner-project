# Spec: Utility Hooks

## Purpose

Defines the portal's shared React hooks — dark-mode persistence and imperative toast notifications — along with their barrel export and unit test coverage requirements.

## Requirements

### Requirement: useDarkMode hook

The portal SHALL provide a `useDarkMode` hook exported from `@/hooks/use-dark-mode`. The hook SHALL return `{ dark: boolean, toggle: () => void }`. On mount it SHALL read the persisted value from `localStorage` under the key `"portal-theme"` (`"dark"` or `"light"`); if absent it SHALL default to `"light"`. On each `toggle` call it SHALL flip the `dark` boolean, update `localStorage`, and add or remove the `"dark"` class on `document.documentElement`.

```typescript
interface UseDarkModeReturn {
  dark: boolean;
  toggle: () => void;
}

export function useDarkMode(): UseDarkModeReturn
```

#### Scenario: Initialises from localStorage dark preference

- **GIVEN** `localStorage.setItem("portal-theme", "dark")` before the hook mounts
- **WHEN** `useDarkMode()` initialises
- **THEN** `dark` is `true` and `document.documentElement` has the `"dark"` class

#### Scenario: Initialises to light when localStorage is absent

- **GIVEN** `localStorage` has no entry for `"portal-theme"`
- **WHEN** `useDarkMode()` initialises
- **THEN** `dark` is `false` and `document.documentElement` does not have the `"dark"` class

#### Scenario: toggle flips dark state and updates DOM

- **GIVEN** `useDarkMode()` has initialised with `dark = false`
- **WHEN** `toggle()` is called
- **THEN** `dark` becomes `true` and `document.documentElement` has the `"dark"` class

#### Scenario: toggle persists preference to localStorage

- **GIVEN** `useDarkMode()` has initialised with `dark = false`
- **WHEN** `toggle()` is called
- **THEN** `localStorage.getItem("portal-theme")` returns `"dark"`

#### Scenario: Second toggle reverts to light

- **GIVEN** `dark` is currently `true`
- **WHEN** `toggle()` is called again
- **THEN** `dark` becomes `false`, the `"dark"` class is removed, and `localStorage` stores `"light"`

---

### Requirement: useToast hook and ToastProvider

The portal SHALL provide a `useToast` hook and a `ToastProvider` component, both exported from `@/hooks/use-toast`. `ToastProvider` SHALL be mounted once in `layout.tsx` as a global ancestor. `useToast()` SHALL return a `toast(message, kind?)` function that imperatively enqueues a notification banner. Banners SHALL auto-dismiss after 4 seconds. A maximum of 3 banners SHALL be displayed simultaneously; excess calls SHALL replace the oldest.

```typescript
type ToastKind = "ok" | "bad";

interface UseToastReturn {
  toast: (message: string, kind?: ToastKind) => void;
}

export function useToast(): UseToastReturn
export function ToastProvider({ children }: { children: React.ReactNode }): JSX.Element
```

#### Scenario: Toast appears on call

- **GIVEN** `ToastProvider` wraps the component tree
- **WHEN** `toast("Operation succeeded", "ok")` is called
- **THEN** a banner with the text "Operation succeeded" is visible in the DOM

#### Scenario: ok kind uses success colour

- **GIVEN** `toast("Saved", "ok")` is called
- **WHEN** the banner renders
- **THEN** the banner's background or accent resolves to `--color-success`

#### Scenario: bad kind uses error colour

- **GIVEN** `toast("Failed to save", "bad")` is called
- **WHEN** the banner renders
- **THEN** the banner's background or accent resolves to `--color-error`

#### Scenario: Banner auto-dismisses after 4 seconds

- **GIVEN** `toast("Processing…")` is called with fake timers active
- **WHEN** 4000 ms elapse
- **THEN** the banner is removed from the DOM

#### Scenario: Fourth toast replaces oldest when 3 are visible

- **GIVEN** three banners are currently visible
- **WHEN** a fourth `toast()` call is made
- **THEN** the oldest banner is removed and the new one appears, keeping the visible count at 3

#### Scenario: Calling useToast outside ToastProvider throws

- **GIVEN** a component calls `useToast()` without `ToastProvider` as an ancestor
- **WHEN** the component renders
- **THEN** a descriptive error is thrown: `"useToast must be used within ToastProvider"`

---

### Requirement: Hook barrel export

Both `useDarkMode` and `useToast`/`ToastProvider` SHALL be re-exported from `src/portal/src/hooks/index.ts`. Consumers SHALL import from `@/hooks` without specifying individual file paths.

#### Scenario: Hooks importable from barrel

- **GIVEN** `import { useDarkMode, useToast, ToastProvider } from "@/hooks"`
- **WHEN** the TypeScript compiler checks the import
- **THEN** all named exports resolve without error

---

### Requirement: Unit test coverage for hooks

Each hook SHALL have a test file under `src/portal/src/hooks/` (`use-dark-mode.test.ts`, `use-toast.test.tsx`). Tests SHALL use Vitest with `renderHook` from `@testing-library/react` and cover all scenarios defined in this spec.

#### Scenario: Hook tests exist and pass

- **GIVEN** the portal is configured per project-scaffold spec
- **WHEN** `npm test --workspace=src/portal` runs
- **THEN** `use-dark-mode.test.ts` and `use-toast.test.tsx` are executed with no failures
