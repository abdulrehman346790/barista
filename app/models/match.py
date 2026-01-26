from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.db.session import Base


class SwipeDirection(str, enum.Enum):
    LIKE = "like"
    PASS = "pass"
    SUPER_LIKE = "super_like"


class MatchStatus(str, enum.Enum):
    ACTIVE = "active"
    UNMATCHED = "unmatched"
    BLOCKED = "blocked"


class ZoneStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class AlertType(str, enum.Enum):
    TOXICITY = "toxicity"
    HARASSMENT = "harassment"
    OFF_PLATFORM = "off_platform"
    EXPLICIT = "explicit"


class AlertSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Swipe(Base):
    """Record of swipes between users."""

    __tablename__ = "swipes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    swiper_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    swiped_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # like, pass, super_like
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("swiper_id", "swiped_id", name="unique_swipe"),)


class Match(Base):
    """Matched pairs of users."""

    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="active")  # active, unmatched, blocked
    firebase_chat_id = Column(String(100), nullable=True)  # Firebase Realtime DB reference
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    unmatched_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    compatibility_score = relationship("CompatibilityScore", back_populates="match", uselist=False)
    chat_metadata = relationship("ChatMetadata", back_populates="match")
    safety_alerts = relationship("SafetyAlert", back_populates="match")


class CompatibilityScore(Base):
    """AI-generated compatibility scores for a match."""

    __tablename__ = "compatibility_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), unique=True)

    # Zone Status
    zone_status = Column(String(10), nullable=True)  # green, yellow, red
    overall_score = Column(Float, nullable=True)  # 0-100

    # Component Scores
    lsm_score = Column(Float, nullable=True)  # Language Style Matching
    sentiment_asymmetry = Column(Float, nullable=True)  # Difference in emotional investment
    engagement_balance = Column(Float, nullable=True)  # Message ratio balance
    topic_alignment = Column(Float, nullable=True)  # Shared interests detected

    # AI Insights
    insights = Column(JSONB, default=dict)  # {"strengths": [], "concerns": [], "tips": []}

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    match = relationship("Match", back_populates="compatibility_score")


class ChatMetadata(Base):
    """Aggregated chat statistics for AI analysis."""

    __tablename__ = "chat_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Aggregated stats
    total_messages = Column(Integer, default=0)
    total_words = Column(Integer, default=0)
    avg_response_time_seconds = Column(Integer, nullable=True)
    message_ratio = Column(Float, nullable=True)  # User's % of conversation

    # Sentiment
    avg_sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_variance = Column(Float, nullable=True)

    # Engagement
    questions_asked = Column(Integer, default=0)
    emojis_used = Column(Integer, default=0)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    match = relationship("Match", back_populates="chat_metadata")


class SafetyAlert(Base):
    """Safety alerts triggered by AI analysis."""

    __tablename__ = "safety_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    flagged_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    alert_type = Column(String(50), nullable=False)  # toxicity, harassment, off_platform, explicit
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=True)

    # Guardian notification
    guardian_notified = Column(String(5), default="false")
    guardian_notified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    match = relationship("Match", back_populates="safety_alerts")
