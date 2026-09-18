## 1. Control-plane domain and migration

- [x] 1.1 Add finite Azure provider/lifecycle/evidence domain types and public tenant-bound persistence migration without secret values.
- [x] 1.2 Extend typed configuration and tenant capability resolution for only approved Azure Blob and Azure PostgreSQL connections.

## 2. Tenant-admin lifecycle API

- [x] 2.1 Implement authenticated tenant-admin create/read/update/test/activate/pause/replace/retire operations with server-derived tenant scope and safe response classes.
- [x] 2.2 Enforce typed validation, reference resolution, secure-test/evidence activation gates, and one-active-per-approved-provider limits.

## 3. Compatibility and observability

- [x] 3.1 Preserve platform-default profile and upload behavior while applying the Azure-only executable exception.
- [x] 3.2 Add declared finite structured lifecycle/test telemetry with no sensitive data.

## 4. Verification

- [x] 4.1 Add executable authorization, tenant-isolation, lifecycle, activation prerequisite, concurrent-limit, compatibility, secret-reference, and telemetry tests for every delta-spec scenario.
- [x] 4.2 Run the configured test command and record evidence in verification.md.
