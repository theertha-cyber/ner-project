from pydantic import BaseModel, Field
from typing import Any
from datetime import datetime


class TrainingJobCreate(BaseModel):
    learning_rate: float = Field(..., gt=0, description="Learning rate for fine-tuning")
    num_epochs: int = Field(..., ge=1, le=50, description="Number of training epochs")
    batch_size: int = Field(..., ge=1, description="Training batch size")
    max_seq_length: int = Field(..., ge=32, le=512, description="Maximum sequence length for tokenization")


class TrainingJobResponse(BaseModel):
    id: str
    status: str
    hyperparams: dict | None = None
    current_epoch: int | None = None
    current_loss: float | None = None
    metrics: dict | None = None
    error_message: str | None = None
    model_version_id: str | None = None
    mlflow_run_id: str | None = None
    mlflow_run_url: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None


class TrainingJobListResponse(BaseModel):
    items: list[TrainingJobResponse]
    total: int
    page: int
    per_page: int


class ModelVersionResponse(BaseModel):
    id: str
    version_number: int
    training_job_id: str | None = None
    status: str
    metrics: dict | None = None
    artifact_path: str | None = None
    mlflow_run_id: str | None = None
    mlflow_run_url: str | None = None
    created_at: datetime | None = None
    promoted_at: datetime | None = None
    archived_at: datetime | None = None
    label_list: list[str] | None = None


class ModelVersionListResponse(BaseModel):
    items: list[ModelVersionResponse]


class ModelVersionPromoteRequest(BaseModel):
    pass


class RejectJobRequest(BaseModel):
    reason: str | None = None
