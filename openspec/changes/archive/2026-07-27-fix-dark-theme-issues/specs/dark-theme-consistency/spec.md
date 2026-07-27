## ADDED Requirements

### Requirement: Dark Theme Consistency Across Portal Pages

All portal pages SHALL use CSS custom properties (design tokens) defined in `globals.css` instead of hardcoded Tailwind color classes or inline hex values, ensuring consistent dark mode support across the application.

#### Scenario: Users Page Dark Mode

- **GIVEN** a user is logged into the portal as Tenant Admin or System Admin
- **WHEN** they navigate to the Users page with dark mode enabled
- **THEN** all containers, text, borders, and status badges render with dark-appropriate colors using CSS variables

#### Scenario: Tenants Page Dark Mode

- **GIVEN** a user is logged into the portal as System Admin
- **WHEN** they navigate to the Tenants page with dark mode enabled
- **THEN** all containers, text, borders, pagination buttons, and status badges render with dark-appropriate colors using CSS variables

#### Scenario: Model Registry Page Dark Mode

- **GIVEN** a user is logged into the portal with any role
- **WHEN** they navigate to the Model Registry page with dark mode enabled
- **THEN** header text, subtitle text, and loading skeleton adapt to dark mode using CSS variables

#### Scenario: Chat Page Dark Mode

- **GIVEN** a user is logged into the portal as Business User or Tenant Admin
- **WHEN** they navigate to the Chat page with dark mode enabled
- **THEN** error toast and empty state text render with dark-appropriate colors using CSS variables

#### Scenario: Documents Page Dark Mode

- **GIVEN** a user is logged into the portal with any role
- **WHEN** they navigate to the Documents page with dark mode enabled
- **THEN** the page header text renders with dark-appropriate color using CSS variables

#### Scenario: Imported Documents Page Dark Mode

- **GIVEN** a user is logged into the portal as Tenant Admin or Annotator
- **WHEN** they navigate to the Imported Documents page with dark mode enabled
- **THEN** all headers, search fields, entity type badges, table rows, and status indicators render with dark-appropriate colors using CSS variables
