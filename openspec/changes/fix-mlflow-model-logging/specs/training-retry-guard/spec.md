## ADDED Requirements

### Requirement: Prevent re-execution of completed or failed jobs

The training worker SHALL check the job's current status in the `training_jobs` table before executing any training operations. If the job has a terminal status (`completed`, `failed`, or `cancelled`), the worker SHALL abort immediately with a no-op.

#### Scenario: Job already completed is not re-executed

- **GIVEN** a Celery task for job ID `J` where `training_jobs.status = "completed"`
- **WHEN** the task begins execution
- **THEN** the worker SHALL log a warning "Job J already completed, skipping"
- **AND** the worker SHALL return without training

#### Scenario: Job already failed is not re-executed

- **GIVEN** a Celery task for job ID `J` where `training_jobs.status = "failed"`
- **WHEN** the task begins execution
- **THEN** the worker SHALL log a warning "Job J already failed, skipping"
- **AND** the worker SHALL return without training

#### Scenario: Job in non-terminal status proceeds normally

- **GIVEN** a Celery task for job ID `J` where `training_jobs.status = "approved"`
- **WHEN** the task begins execution
- **THEN** the worker SHALL proceed with the training pipeline
