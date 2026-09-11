## ADDED Requirements

### Requirement: Prove the deployed CAP-5 image and health
The verification SHALL establish that the Docker Compose portal image under test contains the CAP-5 implementation and that the portal, gateway, and annotation-service health endpoints are reachable before behavioral testing.

#### Scenario: Healthy deployment with CAP-5 provenance
- **WHEN** the Compose target is rebuilt and recreated
- **THEN** evidence records the portal image identity/provenance and HTTP health results for portal, gateway, and annotation service

### Requirement: Verify single-request gestures
The deployed annotation workspace SHALL issue at most one create-span request for each same-token click and multi-token drag; the drag evidence SHALL retain the inclusive calculated range and record whether exactly one confirmed span resulted.

#### Scenario: Same-token click
- **WHEN** an authenticated annotator performs one same-token click, including the browser mouseup sequence
- **THEN** the trace shows exactly one create-span request and exactly one confirmed span

#### Scenario: Multi-token drag
- **WHEN** an authenticated annotator drags from one token to another and releases
- **THEN** the trace shows exactly one create-span request with the inclusive range and exactly one confirmed span

### Requirement: Report unverifiable deployments as blocked
When a required health endpoint is unreachable or the running portal image cannot be shown to contain CAP-5, the evidence SHALL mark the verification blocked without claiming gesture behavior passed or failed.

#### Scenario: Missing prerequisite
- **WHEN** health or image provenance verification fails
- **THEN** the evidence distinguishes the environment/image blocker from a CAP-5 behavior failure
