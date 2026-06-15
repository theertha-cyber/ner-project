from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from src.gateway.models import Base


def _generate_uuid():
    import uuid
    return str(uuid.uuid4())


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = {"schema": "tenant_template"}

    id = Column(String, primary_key=True, default=_generate_uuid)
    tenant_id = Column(String, nullable=False)
    version_number = Column(Integer, nullable=False)
    training_job_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False, default="training")
    metrics = Column(JSON, nullable=True)
    artifact_path = Column(Text, nullable=True)
    mlflow_run_id = Column(String, nullable=True)
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
