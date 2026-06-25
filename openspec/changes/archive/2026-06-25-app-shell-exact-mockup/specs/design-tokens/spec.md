## ADDED Requirements

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
