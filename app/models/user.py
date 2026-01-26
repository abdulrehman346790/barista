from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Float, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.db.session import Base


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class Sect(str, enum.Enum):
    SUNNI = "sunni"
    SHIA = "shia"
    OTHER = "other"


class Religiosity(str, enum.Enum):
    VERY_PRACTICING = "very_practicing"
    PRACTICING = "practicing"
    MODERATE = "moderate"
    CULTURAL = "cultural"


class MaritalStatus(str, enum.Enum):
    NEVER_MARRIED = "never_married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(Base):
    """User authentication model."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    profile = relationship("Profile", back_populates="user", uselist=False)
    personality_score = relationship("PersonalityScore", back_populates="user", uselist=False)


class Profile(Base):
    """User profile/biodata model."""

    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # Basic Info
    full_name = Column(String(100), nullable=False)
    gender = Column(String(10), nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    height_cm = Column(Integer, nullable=True)

    # Location
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    willing_to_relocate = Column(Boolean, default=False)

    # Religious Info (Islamic-specific)
    sect = Column(String(50), nullable=True)
    religiosity = Column(String(20), nullable=True)
    prayer_frequency = Column(String(20), nullable=True)
    hijab_preference = Column(String(20), nullable=True)  # For women
    beard_preference = Column(String(20), nullable=True)  # For men

    # Education & Career
    education_level = Column(String(50), nullable=True)
    profession = Column(String(100), nullable=True)
    income_range = Column(String(50), nullable=True)

    # Family
    marital_status = Column(String(20), nullable=True)
    has_children = Column(Boolean, default=False)
    wants_children = Column(String(20), nullable=True)

    # Bio & Media
    bio = Column(Text, nullable=True)
    photos = Column(JSONB, default=list)  # Array of photo URLs

    # Profile Status
    is_complete = Column(Boolean, default=False)
    verification_status = Column(String(20), default="pending")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="profile")


class PersonalityScore(Base):
    """Big Five personality traits inferred from chat analysis."""

    __tablename__ = "personality_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)

    # Big Five traits (0.0 to 1.0)
    openness = Column(Float, nullable=True)
    conscientiousness = Column(Float, nullable=True)
    extraversion = Column(Float, nullable=True)
    agreeableness = Column(Float, nullable=True)
    neuroticism = Column(Float, nullable=True)

    # Confidence metrics
    sample_size = Column(Integer, default=0)  # Number of messages analyzed
    confidence_score = Column(Float, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="personality_score")
