## ADDED Requirements

### Requirement: Next.js workspace structure

The system SHALL provide a Next.js 14 App Router TypeScript workspace at `src/portal/` containing all portal source code, configuration files, and test infrastructure. The workspace SHALL be listed in the root `package.json` `workspaces` array so `npm install` at the repo root installs its dependencies.

#### Scenario: Workspace discoverable from repo root

- **GIVEN** the repository root contains a `package.json` with a `workspaces` field
- **WHEN** a developer runs `npm install` in the repo root
- **THEN** `src/portal/node_modules` is populated and `src/portal/package.json` scripts are runnable via `npm run <script> --workspace=src/portal`

#### Scenario: Next.js dev server starts

- **GIVEN** `src/portal/.env.local` is populated with all required service URLs
- **WHEN** a developer runs `npm run dev` inside `src/portal/`
- **THEN** the Next.js development server starts on port 3000 with no compilation errors

---

### Requirement: TypeScript strict configuration

The portal SHALL use TypeScript with `"strict": true` and `"moduleResolution": "bundler"` in `tsconfig.json`. The path alias `@/*` SHALL resolve to `src/portal/src/*`.

#### Scenario: Path alias resolves at compile time

- **GIVEN** a component imports from `@/components/ui`
- **WHEN** the TypeScript compiler checks the file
- **THEN** no TS2307 (cannot find module) error is produced

#### Scenario: Strict null checks enforced

- **GIVEN** a component assigns `null` to a variable typed as `string`
- **WHEN** the TypeScript compiler checks the file
- **THEN** a TS2322 type error is reported, confirming strict mode is active

---

### Requirement: ESLint and Prettier configuration

The portal SHALL ship an `.eslintrc.json` extending `next/core-web-vitals` and `prettier`, and a `prettier.config.js` with `semi: true`, `singleQuote: false`, `trailingComma: "all"`, `printWidth: 100`. Both SHALL be runnable via `npm run lint` and `npm run format`.

#### Scenario: Lint passes on the scaffold

- **GIVEN** the initial scaffold files are written
- **WHEN** a developer runs `npm run lint` inside `src/portal/`
- **THEN** ESLint exits with code 0 and reports no errors

#### Scenario: Format check consistent with config

- **GIVEN** all scaffold files have been formatted with Prettier
- **WHEN** a developer runs `npx prettier --check .` inside `src/portal/`
- **THEN** Prettier exits with code 0 (no files need reformatting)

---

### Requirement: Tailwind CSS integration

The portal SHALL integrate Tailwind CSS v3 via `postcss.config.js` and a `tailwind.config.ts` that includes `src/**/*.{ts,tsx}` in the content glob. The root `globals.css` SHALL include the standard `@tailwind base`, `@tailwind components`, `@tailwind utilities` directives.

#### Scenario: Tailwind classes compile without errors

- **GIVEN** a component uses a standard Tailwind class (`bg-white`, `text-sm`, etc.)
- **WHEN** the Next.js build runs
- **THEN** the compiled CSS contains the rule for that class and no PostCSS errors are reported

---

### Requirement: Environment variable interface

The portal SHALL define a `.env.local.example` file at `src/portal/` documenting six required `NEXT_PUBLIC_*` environment variables: `NEXT_PUBLIC_GATEWAY_URL`, `NEXT_PUBLIC_DOCUMENT_URL`, `NEXT_PUBLIC_ANNOTATION_URL`, `NEXT_PUBLIC_TRAINING_URL`, `NEXT_PUBLIC_MODEL_SERVING_URL`, `NEXT_PUBLIC_EXTRACTION_URL`. The file `src/portal/src/lib/api.ts` SHALL export typed constants for all six, falling back to `""` if undefined.

#### Scenario: Missing env variable does not crash at module load

- **GIVEN** `.env.local` does not define `NEXT_PUBLIC_DOCUMENT_URL`
- **WHEN** `src/portal/src/lib/api.ts` is imported in a test
- **THEN** the `DOCUMENT_URL` export resolves to `""` and no runtime exception is thrown

#### Scenario: Defined env variable is surfaced correctly

- **GIVEN** `.env.local` sets `NEXT_PUBLIC_GATEWAY_URL=http://localhost:8000`
- **WHEN** `GATEWAY_URL` is read from `src/portal/src/lib/api.ts`
- **THEN** its value equals `"http://localhost:8000"`

---

### Requirement: Root layout with provider wiring

The portal SHALL provide an `src/portal/src/app/layout.tsx` that applies the three font CSS variables to `<html>`, wraps children with `<ToastProvider>`, and conditionally adds the `dark` class to `<html>` at runtime (client-side only, to avoid SSR mismatch).

#### Scenario: Font variables present on html element

- **GIVEN** the app has rendered
- **WHEN** `document.documentElement` is inspected
- **THEN** the CSS custom properties `--font-display`, `--font-body`, and `--font-mono` are set with the Next.js font variable values

#### Scenario: ToastProvider is an ancestor of all pages

- **GIVEN** any page component calls `useToast()`
- **WHEN** the component renders
- **THEN** no "must be used within ToastProvider" context error is thrown

---

### Requirement: Vitest and Testing Library setup

The portal SHALL include Vitest with `@testing-library/react` and `@testing-library/user-event` configured in `vitest.config.ts`. Tests SHALL run via `npm test` and produce a pass/fail summary. A jsdom environment SHALL be used for component tests.

#### Scenario: Test suite runs from repo root

- **GIVEN** `src/portal/src/components/ui/*.test.tsx` files exist
- **WHEN** a developer runs `npm test --workspace=src/portal`
- **THEN** Vitest executes the tests and exits with code 0 when all pass
