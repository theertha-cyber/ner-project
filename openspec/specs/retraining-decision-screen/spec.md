# retraining-decision-screen Specification

## Purpose
TBD - created by archiving change automated-retraining-destepped. Update Purpose after archive.

## Requirements

### Requirement: Retraining Page Framing

The `/annotate/automated/retrain` page's intro SHALL state that there is no schedule and no
required order — the tenant admin may return to check accumulated evidence at any time, and
retrain only when they decide it is worth it. The page presents two evidence sections that
answer different questions and SHALL NOT be presented in a way that lets their numbers appear to
contradict each other.

The "production-review" section (spans confirmed through the review queue since the serving
model was trained) SHALL be labelled distinctly from any other accumulation measure and SHALL
carry a short explanation that it counts only production-review confirmations — not manual
annotation, automated batches, or imports.

The "training-eligible and waiting" section (new material from any workflow not yet consumed by
a training run) SHALL carry a short explanation that it is a separate count from the
production-review figure above it.

#### Scenario: The page states there is no schedule or required order

- **GIVEN** a Tenant Admin views `/annotate/automated/retrain`
- **WHEN** the page's intro is read
- **THEN** it SHALL state that there is no schedule and no required order

#### Scenario: The production-review section explains what it counts

- **GIVEN** a Tenant Admin views `/annotate/automated/retrain` for a tenant with a trained model
- **WHEN** the production-review section renders
- **THEN** it SHALL state that the figure counts only spans confirmed through production review
- **AND** it SHALL state that manual annotation, automated batches, and imports are counted
  separately

#### Scenario: The training-eligible section explains it is a separate count

- **GIVEN** a Tenant Admin views `/annotate/automated/retrain`
- **WHEN** the "training-eligible and waiting" section renders
- **THEN** it SHALL state that it is a separate count from the production-review figure above it
