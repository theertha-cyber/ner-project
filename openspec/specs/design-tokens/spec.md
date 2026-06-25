# Spec: Design Tokens

## Purpose

Defines the portal's design token system — CSS custom properties for colour, typography, spacing, radius, and shadow — ensuring a consistent visual language across all components with full dark-mode support.

## Requirements

### Requirement: CSS custom-property token declarations

The portal's `src/portal/src/app/globals.css` SHALL declare all design tokens as CSS custom properties on the `:root` selector. A complementary `:root.dark` block SHALL override the colour tokens to their dark-mode counterparts. No component SHALL hardcode colour hex values; all colour usage SHALL reference a token.

#### Scenario: Token file is the single source of colour truth

- **GIVEN** `globals.css` declares `--color-brand-primary`
- **WHEN** a developer searches the portal source for hardcoded hex values matching the brand blue
- **THEN** no match is found outside of `globals.css`

#### Scenario: Dark overrides activate via class

- **GIVEN** `document.documentElement` has the `dark` class
- **WHEN** any element styled with `bg-surface` is rendered
- **THEN** the computed background colour matches the dark-mode `--color-surface` value

---

### Requirement: Colour palette tokens

The portal SHALL define at minimum the following colour token groups in `globals.css`:

- **Brand**: `--color-brand-primary` (active blue), `--color-brand-hover`
- **Surface**: `--color-surface` (card/panel background), `--color-surface-raised`, `--color-surface-overlay`
- **Text**: `--color-text-primary`, `--color-text-secondary`, `--color-text-disabled`
- **Border**: `--color-border`, `--color-border-focus`
- **Status**: `--color-status-active`, `--color-status-inactive`, `--color-status-running`, `--color-status-completed`, `--color-status-failed`, `--color-status-pending`, `--color-status-queued`, `--color-status-rejected`, `--color-status-cancelled`, `--color-status-promoted`
- **Feedback**: `--color-success`, `--color-warning`, `--color-error`, `--color-info`
- **Delta**: `--color-delta-up`, `--color-delta-warn`, `--color-delta-neutral`

Each status colour SHALL correspond to a `Badge` variant of the same name.

#### Scenario: Status token maps to Badge variant

- **GIVEN** `--color-status-running` is defined in `:root`
- **WHEN** `<Badge variant="running" />` renders
- **THEN** the badge's background or text colour resolves to the value of `--color-status-running`

#### Scenario: All status tokens have dark overrides

- **GIVEN** the `:root.dark` block in `globals.css`
- **WHEN** each status token name from the light `:root` block is checked against `:root.dark`
- **THEN** every status token has a corresponding override entry

---

### Requirement: Typography tokens

The portal SHALL define CSS custom properties for the three-font stack:

- `--font-display`: Hanken Grotesk (headings, nav labels)
- `--font-body`: Inter (body text, form inputs)
- `--font-mono`: JetBrains Mono (entity type chips, confidence scores)

Each font variable SHALL be set to the CSS variable injected by `next/font/google` in `layout.tsx`.

#### Scenario: Font variable is present after hydration

- **GIVEN** the portal has hydrated in a browser
- **WHEN** `getComputedStyle(document.documentElement).getPropertyValue("--font-display")` is called
- **THEN** the value is a non-empty string referencing the loaded Hanken Grotesk font

---

### Requirement: Radius and shadow tokens

The portal SHALL define:

- **Radius**: `--radius-sm` (4px), `--radius-md` (8px), `--radius-lg` (12px), `--radius-xl` (16px), `--radius-full` (9999px)
- **Shadow**: `--shadow-card` (the glassmorphism drop shadow used on dashboard cards), `--shadow-overlay` (slide-over panel shadow)

#### Scenario: Card shadow token used on dashboard stat cards

- **GIVEN** `--shadow-card` is declared in `:root`
- **WHEN** `<StatCard />` renders
- **THEN** the element's `box-shadow` CSS property matches the value of `--shadow-card`

---

### Requirement: Tailwind config token references

The portal's `tailwind.config.ts` SHALL extend the default theme to include Tailwind utility classes that reference each token via `var(--token-name)`. The extension SHALL cover at minimum:

- `colors`: one Tailwind colour key per colour token
- `fontFamily`: `display`, `body`, `mono` referencing the font tokens
- `borderRadius`: `sm`, `md`, `lg`, `xl`, `full` referencing the radius tokens
- `boxShadow`: `card`, `overlay` referencing the shadow tokens

#### Scenario: Tailwind class resolves to token

- **GIVEN** `tailwind.config.ts` maps `colors.brand-primary` to `var(--color-brand-primary)`
- **WHEN** a component uses the class `text-brand-primary`
- **THEN** the generated CSS rule sets `color: var(--color-brand-primary)`

---

### Requirement: Page enter animation keyframe

The portal's `globals.css` SHALL declare a `@keyframes ner-fade-up` animation that transitions a screen wrapper from `transform: translateY(8px); opacity: 0` to `transform: translateY(0); opacity: 1`. This keyframe SHALL be registered in `tailwind.config.ts` as the `animate-fade-up` utility class with duration `0.35s` and easing `ease`. The `ner-fade-up` prefix avoids collision with any Tailwind-native animation names.

Every authenticated screen's root content wrapper (the top-level `<div>` inside each `page.tsx` under `app/(auth)/`) SHALL apply `className="animate-fade-up"` so that navigating to or reloading any authenticated route produces the enter animation.

#### Scenario: animate-fade-up class is registered in Tailwind config

- **GIVEN** `tailwind.config.ts` is loaded
- **WHEN** the `animation` extension key is inspected
- **THEN** an entry for `fade-up` exists mapping to `ner-fade-up 0.35s ease both`

#### Scenario: screen root div receives the animation class

- **GIVEN** the user navigates to `/dashboard`
- **WHEN** the page component mounts
- **THEN** the root `<div>` of the dashboard page has the `animate-fade-up` class applied
- **AND** the element transitions from partially transparent and offset to fully opaque at its natural position

#### Scenario: animation fires on each route change

- **GIVEN** the user is on the Documents screen
- **WHEN** the user navigates via the sidebar to the Annotation screen
- **THEN** the Annotation page's root element plays the `fadeUp` animation on mount
