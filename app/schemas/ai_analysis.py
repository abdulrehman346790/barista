from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ==================== Compatibility Schemas ====================

class ZoneInsights(BaseModel):
    """AI-generated insights for a match."""
    strengths: List[str] = []
    concerns: List[str] = []
    tips: List[str] = []


class CompatibilityResponse(BaseModel):
    """Compatibility score for a match."""
    match_id: UUID
    zone_status: str  # green, yellow, red
    overall_score: float  # 0-100
    lsm_score: Optional[float]  # Language Style Matching
    sentiment_asymmetry: Optional[float]
    engagement_balance: Optional[float]
    insights: ZoneInsights
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Personality Schemas ====================

class BigFiveTraits(BaseModel):
    """Big Five personality traits."""
    openness: Optional[float] = Field(None, ge=0, le=1)
    conscientiousness: Optional[float] = Field(None, ge=0, le=1)
    extraversion: Optional[float] = Field(None, ge=0, le=1)
    agreeableness: Optional[float] = Field(None, ge=0, le=1)
    neuroticism: Optional[float] = Field(None, ge=0, le=1)


class PersonalityResponse(BaseModel):
    """User's personality profile."""
    user_id: UUID
    traits: BigFiveTraits
    sample_size: int  # Number of messages analyzed
    confidence_score: Optional[float]
    interpretation: Optional[str]  # Human-readable personality summary
    updated_at: datetime


# ==================== Coaching Schemas ====================

class CoachingRequest(BaseModel):
    """Request for AI reply suggestions."""
    match_id: UUID
    last_messages: List[str] = Field(..., min_length=1, max_length=10)
    context: Optional[str] = None  # Additional context


class SuggestedReply(BaseModel):
    """A suggested reply with explanation."""
    text: str
    tone: str  # friendly, curious, playful, serious
    explanation: str


class CoachingResponse(BaseModel):
    """AI-generated reply suggestions."""
    suggestions: List[SuggestedReply]
    conversation_tip: Optional[str]


# ==================== Safety Schemas ====================

class SafetyAlertResponse(BaseModel):
    """Safety alert for a match."""
    id: UUID
    match_id: UUID
    alert_type: str  # toxicity, harassment, off_platform, explicit
    severity: str  # low, medium, high, critical
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SafetyCheckRequest(BaseModel):
    """Request to check text for safety issues."""
    text: str


class SafetyCheckResponse(BaseModel):
    """Result of safety check."""
    is_safe: bool
    toxicity_score: float  # 0-1
    flags: List[str]  # List of detected issues
