## MODIFIED Requirements

### Requirement: Dashboard Data Shape

The system SHALL define a `DashboardData` TypeScript type that mirrors the mockup's `dashData(role)` shape. Every role's dashboard SHALL include: `kicker` (string), `title` (string), `line` (string), `stats` (array of 4 `StatItem`), `pTitle` (string), `pMeta` (string), `pRows` (array of 4 `ActivityRow`), `sideTop` (string), `sideMeta` (string), `big` (string), `bigUnit` (string), `bar` (number 0–100), `sideMetrics` (array of 3 `{k, v}`), `sideBot` (string), `sideRows` (array of `{label, val, pct, c}`). Numeric values that cannot be fetched from an unavailable service SHALL be `null`; the component SHALL render `—` in place of `null`. For `tenant_admin`, the type additionally includes an optional `responseQuality` object (see the Response Quality Card requirement below); `sideBot`/`sideRows` are empty for this role — they are no longer used to carry feedback data.

For `tenant_admin`, `sideTop`/`sideMeta`/`big`/`bigUnit`/`bar`/`sideMetrics` continue to show the active model's eval F1/precision/recall/loss exactly as before this change, unaffected by feedback data.

#### Scenario: system_admin data shape

- **GIVEN** the authenticated user has role `system_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains `kicker: "Platform control plane"`, 4 stats (Active tenants, Documents, Pending approvals, Avg model F1), `pTitle: "Approval queue"` with 4 training job rows, and a side panel titled "Platform health" with SLA, latency, error rate, and GPU metrics
- **AND** the `sideRows` section contains storage usage by tenant (label, val, pct, colour)

#### Scenario: tenant_admin data shape carries a responseQuality card, not quota-usage sideRows

- **GIVEN** the authenticated user has role `tenant_admin`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 pipeline stats (Documents, Annotation %, Active model F1, Training count), `pTitle: "Pipeline activity"` with 4 activity rows (training run, dataset approval, document processing, model promotion), and a side panel titled "Active model" with eval F1, precision, recall, loss
- **AND** `sideBot` SHALL be `""` and `sideRows` SHALL be `[]` (not "Quota usage" with Documents/Storage/Model versions rows, and not a generic "Response quality" row list either)
- **AND** `responseQuality` SHALL be present with `status`, `satisfactionPct`, `positive`, `negative`, `rated`, `total`, and `recommendation`
- **AND** the `sideTop`/`big`/`bigUnit`/`sideMetrics` fields SHALL be unchanged, still reporting eval F1/precision/recall/loss

#### Scenario: annotator data shape

- **GIVEN** the authenticated user has role `annotator`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Assigned tasks, Spans confirmed, Suggestions, Completion %), `pTitle: "My tasks"` with 4 task rows (showing document name, status, span/suggestion count), and a side panel titled "Dataset readiness" with span progress bar toward 500-span threshold, doc/type/today metrics, and span-by-entity-type breakdown

#### Scenario: business_user data shape

- **GIVEN** the authenticated user has role `business_user`
- **WHEN** `GET /api/v1/dashboard/summary` is called
- **THEN** the response contains 4 stats (Docs extracted, Entities found, Avg confidence, Auto-cleared %), `pTitle: "Recent extractions"` with 4 extraction rows (document name, entity count, confidence, processing time), and a side panel titled "Active model" with eval F1, precision, recall, loss, and top extracted fields chart

#### Scenario: partial service failure degrades gracefully

- **GIVEN** the training service is unavailable when the dashboard is fetched
- **WHEN** the dashboard renders
- **THEN** stat cards whose values depend on the training service show `—` instead of a number
- **AND** stat cards that depend only on available services show their real values
- **AND** no full-page error screen is shown

## ADDED Requirements

### Requirement: Response Quality Card

The Tenant Admin dashboard SHALL render a dedicated "Response Quality" card (a new component, not the generic side-panel row list) so a first-time Tenant Admin can judge model health and whether retraining is warranted within a few seconds, without interpreting several independent numbers themselves. The card SHALL render only when `responseQuality` is present in the dashboard response.

The card SHALL display, top to bottom:
- A header reading `"Response Quality"` with a status badge showing one of `"Healthy"`, `"Monitor"`, `"Needs Attention"`, or `"Not Enough Data"` (mapped from `responseQuality.status`), colour-coded green/amber/red/neutral respectively.
- A headline showing `responseQuality.satisfactionPct` as a rounded whole-number percentage followed by the label `"Positive Feedback"` (or a no-data indicator, e.g. `"—"`, when `status = "no_data"`), with a subtext sentence stating how many of the reviewed responses were positive (e.g. `"46 of 50 reviewed responses were positive"`), or a "no responses reviewed yet" sentence when there is no data.
- A single visual bar (not four independent bars) whose fill is split between the positive share and the negative share of `rated` responses, so the two counts below are visually connected to the headline percentage rather than presented as unrelated numbers.
- A "Business User Feedback" section explicitly labelling the source of the ratings as Business Users, showing a thumbs-up icon with `responseQuality.positive` and a thumbs-down icon with `responseQuality.negative`, followed by a sentence surfacing sample size in the form `"<rated> of <total> AI responses reviewed"` — using the terms "AI responses" and "reviewed" rather than the ambiguous "Total responses"/"Rated" labels of the prior design.
- A "Recommendation" section with an icon and `responseQuality.recommendation`, interpreting the metric for the Tenant Admin (e.g. advising retraining, monitoring, or that no action is needed) rather than leaving them to infer an action from raw numbers.

#### Scenario: Healthy status renders a positive recommendation

- **GIVEN** `responseQuality = {status:"healthy", satisfactionPct:92, positive:46, negative:4, rated:50, total:320, recommendation:"No retraining recommended. Business users are consistently rating responses positively."}`
- **WHEN** the Tenant Admin dashboard renders
- **THEN** the card SHALL show a green "Healthy" badge, `"92%"` with `"Positive Feedback"`, the subtext `"46 of 50 reviewed responses were positive"`, thumbs-up count 46 and thumbs-down count 4, the sentence `"50 of 320 AI responses reviewed"`, and the recommendation text advising no retraining is needed

#### Scenario: Needs Attention status renders a retraining recommendation

- **GIVEN** `responseQuality = {status:"needs_attention", satisfactionPct:33, positive:1, negative:2, rated:3, total:70, recommendation:"Consider retraining the model. Business users are reporting low response quality."}`
- **WHEN** the Tenant Admin dashboard renders
- **THEN** the card SHALL show a red "Needs Attention" badge, `"33%"` with `"Positive Feedback"`, the subtext `"1 of 3 reviewed responses were positive"`, thumbs-up count 1 and thumbs-down count 2, the sentence `"3 of 70 AI responses reviewed"`, and the recommendation text advising retraining be considered

#### Scenario: Monitor status renders a watch-and-gather-more-feedback recommendation

- **GIVEN** `responseQuality.status = "monitor"` (satisfaction percentage between 60 and 79 inclusive)
- **WHEN** the Tenant Admin dashboard renders
- **THEN** the card SHALL show an amber "Monitor" badge and a recommendation advising the Tenant Admin to watch performance and gather more feedback, distinct from both the healthy and needs-attention recommendations

#### Scenario: No-data status avoids a misleading percentage

- **GIVEN** `responseQuality = {status:"no_data", satisfactionPct:null, positive:0, negative:0, rated:0, total:12, recommendation:"Not enough feedback yet to assess model performance."}`
- **WHEN** the Tenant Admin dashboard renders
- **THEN** the card SHALL show a neutral "Not Enough Data" badge, a no-data indicator instead of a percentage, the sentence `"0 of 12 AI responses reviewed"`, and the recommendation text stating there isn't enough feedback yet
