import re
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, JSON, ForeignKey, Enum as SAEnum,
    UniqueConstraint, Text, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class TenantStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class UserRole(str, enum.Enum):
    system_admin = "system_admin"
    tenant_admin = "tenant_admin"
    business_user = "business_user"
    annotator = "annotator"


def generate_uuid():
    return str(uuid.uuid4())


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
    return slug[:63] if slug else uuid.uuid4().hex[:8]


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(63), unique=True, nullable=False, index=True)
    status = Column(SAEnum(TenantStatus), default=TenantStatus.active, nullable=False)
    max_users = Column(Integer, default=10, nullable=False)
    max_documents = Column(Integer, default=1000, nullable=False)
    max_storage_gb = Column(Integer, default=5, nullable=False)
    max_model_versions = Column(Integer, default=10, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TenantUser(Base):
    __tablename__ = "tenant_users"
    __table_args__ = {"schema": "public"}

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("public.tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", backref="users")

    __table_args__ = (
        UniqueConstraint("email", "tenant_id", name="uq_email_per_tenant"),
        {"schema": "public"},
    )


class EntityDefinition(Base):
    __tablename__ = "entity_definitions"
    __table_args__ = {"schema": "public"}

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("public.tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    examples = Column(JSON, nullable=True)
    validation_rule = Column(String(500), nullable=True)
    target_table = Column(String(255), nullable=True)
    base_label_mapping = Column(JSON, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    required_flag = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", backref="entity_definitions")


VALID_BASE_LABELS = {"PER", "ORG", "LOC", "MISC"}


def validate_base_label_mapping(mapping: dict | None) -> str | None:
    if not mapping:
        return None
    for key in mapping:
        if key not in VALID_BASE_LABELS:
            return f"Invalid base model label '{key}'. Must be one of: {', '.join(sorted(VALID_BASE_LABELS))}"
    return None
