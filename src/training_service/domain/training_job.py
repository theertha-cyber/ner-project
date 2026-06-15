from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text
from src.gateway.models import Base


def _generate_uuid():
    import uuid
    return str(uuid.uuid4())


class TrainingJob(Base):
    __tablename__ = "training_jobs"
    __table_args__ = {"schema": "tenant_template"}

    id = Column(String, primary_key=True, default=_generate_uuid)
    tenant_id = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    hyperparams = Column(JSON, nullable=False, default={})
    current_epoch = Column(Integer, nullable=True)
    current_loss = Column(Float, nullable=True)
    metrics = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    model_version_id = Column(String, nullable=True)
    celery_task_id = Column(String, nullable=True)
    mlflow_run_id = Column(String, nullable=True)
    mlflow_run_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
