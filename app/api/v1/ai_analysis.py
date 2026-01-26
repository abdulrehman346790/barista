from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List
from datetime import datetime

from app.db.session import get_db
from app.core.dependencies import get_current_verified_user
from app.models.user import User, Profile, PersonalityScore
from app.models.match import Match, CompatibilityScore, ChatMetadata, SafetyAlert
from app.schemas.ai_analysis import (
    CompatibilityResponse,
    ZoneInsights,
    PersonalityResponse,
    BigFiveTraits,
    CoachingRequest,
    CoachingResponse,
    SuggestedReply,
    SafetyAlertResponse,
    SafetyCheckRequest,
    SafetyCheckResponse,
)
from app.ai.huggingface_client import (
    sentiment_analyzer,
    toxicity_detector,
    lsm_calculator,
    conversation_coach,
)


router = APIRouter(prefix="/ai", tags=["AI Analysis"])


def calculate_zone(
    lsm_score: float,
    sentiment_asymmetry: float,
    engagement_balance: float,
    toxicity_count: int,
) -> tuple[str, float]:
    """
    Calculate Red/Green Zone status.
    Returns (zone_status, overall_score).
    """
    # Safety trumps everything
    if toxicity_count > 0:
        safety_score = 0.0
    else:
        safety_score = 1.0

    # Weighted scoring
    score = (
        lsm_score * 0.30
        + (1 - sentiment_asymmetry) * 0.25
        + engagement_balance * 0.25
        + safety_score * 0.20
    ) * 100

    # Determine zone
    if toxicity_count > 0:
        zone = "red"
    elif score >= 70:
        zone = "green"
    elif score >= 40:
        zone = "yellow"
    else:
        zone = "red"

    return zone, round(score, 2)


def generate_insights(
    zone: str,
    lsm_score: float,
    sentiment_asymmetry: float,
    engagement_balance: float,
) -> ZoneInsights:
    """Generate human-readable insights based on scores."""
    strengths = []
    concerns = []
    tips = []

    # LSM insights
    if lsm_score >= 0.7:
        strengths.append("Your communication styles are well-matched")
    elif lsm_score < 0.4:
        concerns.append("Your communication styles differ significantly")
        tips.append("Try mirroring their communication style to build rapport")

    # Sentiment insights
    if sentiment_asymmetry > 0.5:
        concerns.append("There's an imbalance in emotional investment")
        tips.append("If you're more invested, give them space. If less, show more enthusiasm")
    else:
        strengths.append("Emotional investment is balanced")

    # Engagement insights
    if engagement_balance >= 0.8:
        strengths.append("Conversation is flowing naturally with balanced participation")
    elif engagement_balance < 0.4:
        concerns.append("One person is doing most of the talking")
        tips.append("Ask more questions to encourage balanced dialogue")

    # Zone-specific tips
    if zone == "green":
        tips.append("Great connection! Consider moving to deeper topics")
    elif zone == "yellow":
        tips.append("Keep building rapport through shared interests")
    elif zone == "red":
        tips.append("Consider if this match is right for you")

    return ZoneInsights(strengths=strengths, concerns=concerns, tips=tips)


@router.get("/compatibility/{match_id}", response_model=CompatibilityResponse)
async def get_compatibility_score(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated compatibility score for a match.
    Calculates Red/Green Zone based on chat metadata.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_id,
                or_(
                    Match.user1_id == current_user.id,
                    Match.user2_id == current_user.id,
                ),
            )
        )
    )
    match = match_result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    # Get other user ID
    other_user_id = (
        match.user2_id if match.user1_id == current_user.id else match.user1_id
    )

    # Get chat metadata for both users
    my_metadata_result = await db.execute(
        select(ChatMetadata).where(
            and_(
                ChatMetadata.match_id == match_id,
                ChatMetadata.user_id == current_user.id,
            )
        )
    )
    my_metadata = my_metadata_result.scalar_one_or_none()

    other_metadata_result = await db.execute(
        select(ChatMetadata).where(
            and_(
                ChatMetadata.match_id == match_id,
                ChatMetadata.user_id == other_user_id,
            )
        )
    )
    other_metadata = other_metadata_result.scalar_one_or_none()

    # Get safety alerts
    alerts_result = await db.execute(
        select(SafetyAlert).where(SafetyAlert.match_id == match_id)
    )
    toxicity_count = len(alerts_result.scalars().all())

    # Calculate scores
    lsm_score = 0.5  # Default if no data
    sentiment_asymmetry = 0.0
    engagement_balance = 0.5

    if my_metadata and other_metadata:
        # Calculate engagement balance
        total_msgs = my_metadata.total_messages + other_metadata.total_messages
        if total_msgs > 0:
            min_msgs = min(my_metadata.total_messages, other_metadata.total_messages)
            max_msgs = max(my_metadata.total_messages, other_metadata.total_messages)
            engagement_balance = min_msgs / max_msgs if max_msgs > 0 else 0.5

        # Calculate sentiment asymmetry
        if my_metadata.avg_sentiment_score is not None and other_metadata.avg_sentiment_score is not None:
            sentiment_asymmetry = abs(
                my_metadata.avg_sentiment_score - other_metadata.avg_sentiment_score
            )

    # Calculate zone and overall score
    zone, score = calculate_zone(
        lsm_score, sentiment_asymmetry, engagement_balance, toxicity_count
    )

    # Generate insights
    insights = generate_insights(zone, lsm_score, sentiment_asymmetry, engagement_balance)

    # Get or create compatibility score record
    compat_result = await db.execute(
        select(CompatibilityScore).where(CompatibilityScore.match_id == match_id)
    )
    compat_score = compat_result.scalar_one_or_none()

    if not compat_score:
        compat_score = CompatibilityScore(match_id=match_id)
        db.add(compat_score)

    # Update record
    compat_score.zone_status = zone
    compat_score.overall_score = score
    compat_score.lsm_score = lsm_score
    compat_score.sentiment_asymmetry = sentiment_asymmetry
    compat_score.engagement_balance = engagement_balance
    compat_score.insights = insights.model_dump()

    await db.commit()
    await db.refresh(compat_score)

    return CompatibilityResponse(
        match_id=compat_score.match_id,
        zone_status=zone,
        overall_score=score,
        lsm_score=lsm_score,
        sentiment_asymmetry=sentiment_asymmetry,
        engagement_balance=engagement_balance,
        insights=insights,
        updated_at=compat_score.updated_at,
    )


@router.get("/personality/me", response_model=PersonalityResponse)
async def get_my_personality(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current user's personality profile.
    Based on Big Five traits inferred from chat history.
    """
    result = await db.execute(
        select(PersonalityScore).where(PersonalityScore.user_id == current_user.id)
    )
    personality = result.scalar_one_or_none()

    if not personality or personality.sample_size < 10:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not enough chat data to generate personality profile. Keep chatting!",
        )

    # Generate interpretation
    interpretation = generate_personality_interpretation(personality)

    return PersonalityResponse(
        user_id=current_user.id,
        traits=BigFiveTraits(
            openness=personality.openness,
            conscientiousness=personality.conscientiousness,
            extraversion=personality.extraversion,
            agreeableness=personality.agreeableness,
            neuroticism=personality.neuroticism,
        ),
        sample_size=personality.sample_size,
        confidence_score=personality.confidence_score,
        interpretation=interpretation,
        updated_at=personality.updated_at,
    )


def generate_personality_interpretation(personality: PersonalityScore) -> str:
    """Generate human-readable personality interpretation."""
    traits = []

    if personality.openness and personality.openness > 0.6:
        traits.append("creative and open to new experiences")
    elif personality.openness and personality.openness < 0.4:
        traits.append("practical and traditional")

    if personality.extraversion and personality.extraversion > 0.6:
        traits.append("outgoing and energetic")
    elif personality.extraversion and personality.extraversion < 0.4:
        traits.append("reflective and reserved")

    if personality.agreeableness and personality.agreeableness > 0.6:
        traits.append("compassionate and cooperative")

    if personality.conscientiousness and personality.conscientiousness > 0.6:
        traits.append("organized and dependable")

    if traits:
        return f"Based on your conversations, you appear to be {', '.join(traits)}."
    return "Keep chatting to reveal more about your personality!"


@router.post("/coaching/suggest", response_model=CoachingResponse)
async def get_reply_suggestions(
    request: CoachingRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated reply suggestions based on conversation context.
    Uses Huggingface LLM for contextual suggestions.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == str(request.match_id),
                or_(
                    Match.user1_id == current_user.id,
                    Match.user2_id == current_user.id,
                ),
                Match.status == "active",
            )
        )
    )
    match = match_result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found or not active.",
        )

    # Get profile for personalization
    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()
    user_name = profile.full_name if profile else "User"

    # Generate suggestions using AI
    suggestions_raw = conversation_coach.suggest_replies(
        last_messages=request.last_messages,
        user_name=user_name,
        context=request.context,
    )

    suggestions = [
        SuggestedReply(
            text=s["text"],
            tone=s["tone"],
            explanation=s["explanation"],
        )
        for s in suggestions_raw
    ]

    # Generate conversation tip
    tip = "Remember to be genuine and ask follow-up questions to show interest."

    return CoachingResponse(
        suggestions=suggestions,
        conversation_tip=tip,
    )


@router.get("/safety/{match_id}", response_model=List[SafetyAlertResponse])
async def get_safety_alerts(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get safety alerts for a match."""
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_id,
                or_(
                    Match.user1_id == current_user.id,
                    Match.user2_id == current_user.id,
                ),
            )
        )
    )
    if not match_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    # Get alerts
    alerts_result = await db.execute(
        select(SafetyAlert).where(SafetyAlert.match_id == match_id)
    )
    alerts = alerts_result.scalars().all()

    return [SafetyAlertResponse.model_validate(alert) for alert in alerts]


@router.post("/safety/check", response_model=SafetyCheckResponse)
async def check_text_safety(
    request: SafetyCheckRequest,
    current_user: User = Depends(get_current_verified_user),
):
    """
    Check text for safety issues (toxicity, harassment, etc.).
    Can be called by client before sending a message.
    """
    result = toxicity_detector.detect(request.text)

    return SafetyCheckResponse(
        is_safe=not result["is_toxic"],
        toxicity_score=result["toxicity_score"],
        flags=result["flags"],
    )
