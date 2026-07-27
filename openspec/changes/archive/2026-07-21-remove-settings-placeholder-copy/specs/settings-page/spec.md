## MODIFIED Requirements

### Requirement: Settings Page Placeholder

The Settings page SHALL render a visible Settings heading without displaying generic coming-soon placeholder copy.

#### Scenario: Settings page does not show coming-soon copy

- **GIVEN** a user is logged into the portal
- **WHEN** they navigate to `/settings`
- **THEN** the page shows the "Settings" heading
- **AND** the page does not show the exact text "This screen is coming soon."
