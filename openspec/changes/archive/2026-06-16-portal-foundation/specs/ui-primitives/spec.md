## ADDED Requirements

### Requirement: Badge component

The portal SHALL provide a `Badge` component exported from `@/components/ui`. It SHALL accept a `variant` prop typed as a union of all entity status strings and render a coloured pill chip using the corresponding status token.

```typescript
type BadgeVariant =
  | "active" | "inactive" | "running" | "completed" | "failed"
  | "pending_approval" | "queued" | "rejected" | "cancelled" | "promoted";

interface BadgeProps {
  variant: BadgeVariant;
  label?: string; // defaults to the variant string with underscores replaced by spaces
}
```

#### Scenario: Badge renders correct colour for known variant

- **GIVEN** the design-tokens spec is satisfied (status colour tokens are declared)
- **WHEN** `<Badge variant="running" />` renders
- **THEN** the badge has a class or style resolving to `--color-status-running` and displays the text "running"

#### Scenario: Badge uses custom label when provided

- **GIVEN** `<Badge variant="pending_approval" label="Needs Review" />`
- **WHEN** the component renders
- **THEN** the displayed text is "Needs Review", not "pending approval"

#### Scenario: Unknown variant falls back gracefully

- **GIVEN** a TypeScript consumer passes a valid `BadgeVariant` string
- **WHEN** the component renders
- **THEN** no runtime error occurs (TypeScript compilation catches invalid variants at authoring time)

---

### Requirement: StatCard component

The portal SHALL provide a `StatCard` component that displays a labelled metric value with an optional unit, directional delta indicator, and subtitle.

```typescript
interface StatCardProps {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  deltaDir?: "up" | "warn" | "neutral";
  sub?: string;
}
```

#### Scenario: Delta up indicator uses success colour

- **GIVEN** `<StatCard label="F1 Score" value="0.91" delta="+0.03" deltaDir="up" />`
- **WHEN** the component renders
- **THEN** the delta text is coloured with `--color-delta-up` (green tone)

#### Scenario: Delta warn indicator uses warning colour

- **GIVEN** `<StatCard label="Errors" value="12" delta="+5" deltaDir="warn" />`
- **WHEN** the component renders
- **THEN** the delta text is coloured with `--color-delta-warn` (amber tone)

#### Scenario: Optional props render nothing when absent

- **GIVEN** `<StatCard label="Tenants" value="7" />`
- **WHEN** the component renders
- **THEN** no delta indicator or subtitle is present in the DOM

#### Scenario: Card uses shadow-card token

- **GIVEN** `<StatCard label="Models" value="3" />` renders
- **WHEN** the card element's computed style is inspected
- **THEN** `box-shadow` resolves to the value of `--shadow-card`

---

### Requirement: SlideOver component

The portal SHALL provide a `SlideOver` component that renders a right-anchored panel sliding in over the main content with a backdrop overlay. It SHALL trap focus when open and restore focus to the trigger element on close.

```typescript
interface SlideOverProps {
  open: boolean;
  onClose: () => void;
  width?: number; // pixels, default 480
  children: React.ReactNode;
}
```

#### Scenario: Panel is hidden when closed

- **GIVEN** `<SlideOver open={false} onClose={noop}><p>content</p></SlideOver>`
- **WHEN** the component renders
- **THEN** the panel is not visible (either `display: none` or translated fully off-screen)

#### Scenario: Panel is visible when open

- **GIVEN** `<SlideOver open={true} onClose={noop}><p>content</p></SlideOver>`
- **WHEN** the component renders
- **THEN** the panel and backdrop overlay are visible in the DOM

#### Scenario: onClose fires on backdrop click

- **GIVEN** `<SlideOver open={true} onClose={mockFn}>...</SlideOver>`
- **WHEN** a user clicks the backdrop overlay
- **THEN** `mockFn` is called once

#### Scenario: onClose fires on Escape key

- **GIVEN** `<SlideOver open={true} onClose={mockFn}>...</SlideOver>`
- **WHEN** the user presses the `Escape` key
- **THEN** `mockFn` is called once

---

### Requirement: MiniBar component

The portal SHALL provide a `MiniBar` component that renders a horizontal progress-bar style indicator for quota or usage visualisation.

```typescript
interface MiniBarProps {
  used: number;
  max: number;
}
```

The fill width SHALL be `(used / max) * 100%`, clamped to 0–100%. When `used / max >= 0.9`, the fill SHALL use the warning colour token.

#### Scenario: Fill width proportional to used/max

- **GIVEN** `<MiniBar used={3} max={10} />`
- **WHEN** the component renders
- **THEN** the fill element's width is 30% of the container

#### Scenario: Fill uses warning colour at 90%+ usage

- **GIVEN** `<MiniBar used={9} max={10} />`
- **WHEN** the component renders
- **THEN** the fill element's colour resolves to `--color-warning`

#### Scenario: Fill is clamped to 100% when used exceeds max

- **GIVEN** `<MiniBar used={15} max={10} />`
- **WHEN** the component renders
- **THEN** the fill element's width is 100% and does not overflow the container

---

### Requirement: SegmentControl component

The portal SHALL provide a `SegmentControl` component that renders a set of pill-style toggle buttons allowing single selection from a list of labelled options.

```typescript
interface SegmentOption {
  label: string;
  value: string;
}

interface SegmentControlProps {
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
}
```

#### Scenario: Selected option is visually distinguished

- **GIVEN** `<SegmentControl options={[{label:"A",value:"a"},{label:"B",value:"b"}]} value="a" onChange={noop} />`
- **WHEN** the component renders
- **THEN** the "A" button has an active style (background or text colour) not applied to "B"

#### Scenario: Clicking an option calls onChange

- **GIVEN** the same SegmentControl as above
- **WHEN** a user clicks the "B" button
- **THEN** `onChange` is called with `"b"`

#### Scenario: Component is keyboard navigable

- **GIVEN** focus is on the "A" button
- **WHEN** the user presses the right arrow key
- **THEN** focus moves to the "B" button

---

### Requirement: Spinner component

The portal SHALL provide a `Spinner` component that renders an animated loading indicator in two sizes.

```typescript
interface SpinnerProps {
  size?: "sm" | "md"; // default "md"
}
```

#### Scenario: Spinner renders with default size

- **GIVEN** `<Spinner />`
- **WHEN** the component renders
- **THEN** the spinner element is present in the DOM with the md size class

#### Scenario: Spinner renders sm variant

- **GIVEN** `<Spinner size="sm" />`
- **WHEN** the component renders
- **THEN** the spinner element has the sm size class (smaller than md)

---

### Requirement: PlaceholderScreen component

The portal SHALL provide a `PlaceholderScreen` component used for routes not yet implemented in a given wave. It SHALL display a centred message with the given title and a generic "coming soon" or "not yet available" sub-text.

```typescript
interface PlaceholderScreenProps {
  title: string;
}
```

#### Scenario: Title is displayed

- **GIVEN** `<PlaceholderScreen title="Model Registry" />`
- **WHEN** the component renders
- **THEN** the text "Model Registry" is present in the DOM

#### Scenario: Component renders without additional props

- **GIVEN** `<PlaceholderScreen title="Documents" />`
- **WHEN** the component renders
- **THEN** no runtime error occurs

---

### Requirement: authFetch stub

The portal SHALL provide `src/portal/src/lib/auth-fetch.ts` exporting an `authFetch` function with the following signature:

```typescript
export async function authFetch(
  url: string,
  init?: RequestInit
): Promise<Response>
```

In this change (SP-01), the implementation SHALL be a pass-through to the native `fetch(url, init)`. SP-02 SHALL replace the body with real token injection and refresh logic without changing the export signature.

#### Scenario: authFetch pass-through calls native fetch

- **GIVEN** the authFetch stub is imported
- **WHEN** `authFetch("http://localhost:8000/health")` is called in a test where `fetch` is mocked
- **THEN** the mocked `fetch` is called with `"http://localhost:8000/health"` and the response is returned

#### Scenario: Import path is stable across SP-01 and SP-02

- **GIVEN** a component imports `authFetch` from `@/lib/auth-fetch`
- **WHEN** SP-02 replaces the implementation
- **THEN** the import path and function signature remain unchanged (no consumer update required)

---

### Requirement: Primitive barrel export

All eight primitives SHALL be re-exported from a single `src/portal/src/components/ui/index.ts` barrel file. Consumers SHALL import from `@/components/ui` without specifying individual file paths.

#### Scenario: All primitives importable from barrel

- **GIVEN** `import { Badge, StatCard, SlideOver, MiniBar, SegmentControl, Spinner, PlaceholderScreen } from "@/components/ui"`
- **WHEN** the TypeScript compiler checks the import
- **THEN** all named exports resolve without error

---

### Requirement: Unit test coverage for all primitives

Each primitive component SHALL have a co-located test file (`*.test.tsx`) under `src/portal/src/components/ui/`. Each test file SHALL cover at minimum the scenarios defined in this spec. Tests SHALL use Vitest and `@testing-library/react`.

#### Scenario: Test files present for all primitives

- **GIVEN** the `src/portal/src/components/ui/` directory
- **WHEN** the directory is listed
- **THEN** each of the following test files exists: `badge.test.tsx`, `stat-card.test.tsx`, `slide-over.test.tsx`, `mini-bar.test.tsx`, `segment-control.test.tsx`, `spinner.test.tsx`, `placeholder-screen.test.tsx`

#### Scenario: All tests pass

- **GIVEN** the portal is correctly configured per project-scaffold spec
- **WHEN** `npm test --workspace=src/portal` runs
- **THEN** all primitive tests pass with no failures
