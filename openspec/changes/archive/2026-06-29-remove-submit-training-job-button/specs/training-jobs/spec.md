## ADDED Requirements

### Requirement: Hide submit job action for non-tenant-admin roles

The Training Queue UI SHALL only render the submit job button and submit job slideover for users with the `tenant_admin` role. Users with any other role (including `system_admin`, `annotator`, `business_user`) SHALL NOT see the submit job button or have access to the submit job slideover on the Training Queue page.

#### Scenario: Submit button visible for tenant_admin

- **GIVEN** an authenticated user with the `tenant_admin` role
- **WHEN** the user navigates to the Training Queue page (`/training-jobs`)
- **THEN** the `+ Submit Job` button SHALL be visible in the page header

#### Scenario: Submit button hidden for system_admin

- **GIVEN** an authenticated user with the `system_admin` role
- **WHEN** the user navigates to the Training Queue page (`/training-jobs`)
- **THEN** the `+ Submit Job` button SHALL NOT be rendered on the page
- **AND** the submit job slideover SHALL NOT be rendered on the page

#### Scenario: Submit slideover not accessible for system_admin

- **GIVEN** an authenticated user with the `system_admin` role on the Training Queue page
- **WHEN** the user inspects the page
- **THEN** no mechanism to open the submit job slideover SHALL exist in the DOM
