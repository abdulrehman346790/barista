from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum

from app.db.session import Base


class GuardianRelationship(str, enum.Enum):
    FATHER = "father"
    MOTHER = "mother"
    BROTHER = "brother"
    SISTER = "sister"
    OTHER = "other"


class GuardianStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class GuardianLink(Base):
    """Links users with their guardians (Wali) for safety monitoring."""

    __tablename__ = "guardian_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    guardian_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    relationship = Column(String(50), nullable=False)  # father, mother, brother, sister, other

    # Permissions
    can_view_matches = Column(Boolean, default=True)
    can_view_safety_alerts = Column(Boolean, default=True)
    alert_on_red_zone = Column(Boolean, default=True)

    status = Column(String(20), default="pending")  # pending, active, revoked
    created_at = Column(DateTime(timezone=True), server_default=func.now())
