## ADDED Requirements

### Requirement: Tenant Admin Dashboard Queries

The system SHALL populate the tenant_admin dashboard with real data by querying the tenant's schema tables. When data sources are unavailable, affected fields SHALL return `null` and `sources.<name>` SHALL be `false`.

#### Scenario: tenant_admin stats return real document and training counts

- **GIVEN** the tenant has 15 documents and 2 training jobs in the last 24 hours
- **WHEN** `GET /api/v1/dashboard/summary` is called by a `tenant_admin` user
- **THEN** `stats[0].value` SHALL be `"15"`
- **AND** `stats[3].value` SHALL be `"2"`
- **AND** `sources.documents` and `sources.training` SHALL be `true`

#### Scenario: tenant_admin annotation progress calculates correctly

- **GIVEN** the tenant has 20 documents, 12 of which have `status = 'annotated'`
- **WHEN** the dashboard summary is fetched
- **THEN** `stats[1].value` SHALL be `"60"` (60%)
- **AND** `stats[1].unit` SHALL be `"%"`

#### Scenario: tenant_admin active model F1 from promoted model

- **GIVEN** the tenant has a promoted model version with `metrics.f1 = 0.872`
- **WHEN** the dashboard summary is fetched
- **THEN** `stats[2].value` SHALL be `"87.2"` (displayed as percentage)
- **AND** `sources.models` SHALL be `true`

#### Scenario: tenant_admin shows pipeline activity rows

- **GIVEN** there are recent training jobs, document uploads, and extraction events
- **WHEN** the dashboard summary is fetched
- **THEN** `pRows` SHALL contain up to 4 activity rows with populated `title`, `sub`, `tag`, and `tk` fields
- **AND** each row's `go` field SHALL map to a valid route href

#### Scenario: tenant_admin graceful degradation when training service unavailable

- **GIVEN** the training_jobs table does not exist or the query fails
- **WHEN** the dashboard summary is fetched
- **THEN** `stats[3].value` SHALL be `null`
- **AND** `stats[3].sub` SHALL contain `"service unavailable"`
- **AND** `sources.training` SHALL be `false`

---

### Requirement: Annotator Dashboard Queries

The system SHALL populate the annotator dashboard with real data from annotation tasks, spans, and suggestions in the tenant schema.

#### Scenario: annotator stats return assigned task and span counts

- **GIVEN** the annotator has 8 assigned tasks with 45 confirmed spans and 12 suggestions
- **WHEN** `GET /api/v1/dashboard/summary` is called by an `annotator` user
- **THEN** `stats[0].value` SHALL be `"8"`
- **AND** `stats[1].value` SHALL be `"45"`
- **AND** `stats[2].value` SHALL be `"12"`
- **AND** `sources.annotations` SHALL be `true`

#### Scenario: annotator completion percentage

- **GIVEN** the annotator has completed 6 out of 8 assigned tasks
- **WHEN** the dashboard summary is fetched
- **THEN** `stats[3].value` SHALL be `"75"`
- **AND** `stats[3].unit` SHALL be `"%"`

#### Scenario: annotator shows task activity rows

- **GIVEN** the annotator has annotation tasks with various statuses
- **WHEN** the dashboard summary is fetched
- **THEN** `pRows` SHALL contain up to 4 activity rows, each showing task title, document name, and status tag

#### Scenario: annotator side panel shows dataset readiness

- **GIVEN** the tenant has spans and entity types defined
- **WHEN** the dashboard summary is fetched
- **THEN** `big` SHALL show the total span count toward the 500-span training threshold
- **AND** `bar` SHALL show the percentage toward that threshold
- **AND** `sideMetrics` SHALL contain doc count, entity type count, and today's span count

---

### Requirement: Business User Dashboard Queries

The system SHALL populate the business_user dashboard with real extraction data from the tenant schema.

#### Scenario: business_user stats return extraction counts and confidence

- **GIVEN** the tenant has 25 extracted documents with 340 entities and average confidence 0.89
- **WHEN** `GET /api/v1/dashboard/summary` is called by a `business_user`
- **THEN** `stats[0].value` SHALL be `"25"`
- **AND** `stats[1].value` SHALL be `"340"`
- **AND** `stats[2].value` SHALL be `"89"`
- **AND** `sources.extraction` SHALL be `true`

#### Scenario: business_user auto-cleared percentage

- **GIVEN** 200 entities have `review_status = 'auto_cleared'` out of 340 total
- **WHEN** the dashboard summary is fetched
- **THEN** `stats[3].value` SHALL be `"58.8"`
- **AND** `stats[3].unit` SHALL be `"%"`

#### Scenario: business_user shows extraction activity rows

- **GIVEN** there are recent extraction runs with varying statuses
- **WHEN** the dashboard summary is fetched
- **THEN** `pRows` SHALL contain up to 4 activity rows showing document name, entity count, confidence, and processing time

#### Scenario: business_user side panel shows active model

- **GIVEN** a promoted model version exists with metrics
- **WHEN** the dashboard summary is fetched
- **THEN** `big` SHALL show the promoted model's eval F1 score
- **AND** `sideMetrics` SHALL contain precision, recall, and loss
- **AND** `sideRows` SHALL be populated with top extracted fields by count
