"""
AI Coach Endpoints
New agent-based AI system using Groq/Cerebras
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.core.dependencies import get_current_verified_user
from app.models.user import User, Profile
from app.models.match import Match

# Import our new agents
from app.agents import (
    analyze_compatibility,
    analyze_conversation,
    get_coach_response,
    check_safety,
)
from app.agents.analyzer import get_user_insights
from app.agents.coach import get_auto_insight

router = APIRouter(prefix="/ai-coach", tags=["AI Coach"])


# ================== Pydantic Schemas ==================

class CoachQuestionRequest(BaseModel):
    match_id: str
    question: str

class CoachResponse(BaseModel):
    response: str
    timestamp: datetime = datetime.now()

class AutoInsightRequest(BaseModel):
    match_id: str
    last_message: str

class AutoInsightResponse(BaseModel):
    insight: str

class CompatibilityRequest(BaseModel):
    profile_a_id: str
    profile_b_id: str

class ConversationAnalysisRequest(BaseModel):
    match_id: str
    messages: list  # List of {sender_id, text, timestamp}

class SafetyCheckRequest(BaseModel):
    match_id: str
    messages: list


# ================== Endpoints ==================

@router.post("/ask", response_model=CoachResponse)
async def ask_ai_coach(
    request: CoachQuestionRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ask the AI coach a private question.
    This is the @AI mention handler - response is PRIVATE to the asking user only.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == request.match_id,
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

    # Get user's profile
    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    user_profile = profile_result.scalar_one_or_none()
    user_name = user_profile.full_name if user_profile else "User"

    # Get other user's info
    other_user_id = match.user2_id if match.user1_id == current_user.id else match.user1_id
    other_profile_result = await db.execute(
        select(Profile).where(Profile.user_id == other_user_id)
    )
    other_profile = other_profile_result.scalar_one_or_none()
    match_name = other_profile.full_name if other_profile else "Your match"

    # TODO: Get actual conversation from Firebase/DB
    # For now, using empty list - in production, fetch from chat storage
    conversation = []

    try:
        response = await get_coach_response(
            user_id=str(current_user.id),
            user_name=user_name,
            match_name=match_name,
            conversation=conversation,
            question=request.question,
            user_profile=user_profile.__dict__ if user_profile else None,
            match_profile=other_profile.__dict__ if other_profile else None,
        )

        return CoachResponse(response=response)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Coach error: {str(e)}",
        )


@router.post("/auto-insight", response_model=AutoInsightResponse)
async def get_automatic_insight(
    request: AutoInsightRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get automatic insight after receiving a message.
    Powers the auto-insights bar in the UI.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == request.match_id,
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

    # Get names
    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    user_profile = profile_result.scalar_one_or_none()
    user_name = user_profile.full_name if user_profile else "You"

    other_user_id = match.user2_id if match.user1_id == current_user.id else match.user1_id
    other_profile_result = await db.execute(
        select(Profile).where(Profile.user_id == other_user_id)
    )
    other_profile = other_profile_result.scalar_one_or_none()
    match_name = other_profile.full_name if other_profile else "Your match"

    try:
        insight = await get_auto_insight(
            user_id=str(current_user.id),
            user_name=user_name,
            match_name=match_name,
            conversation=[],  # TODO: Fetch actual conversation
            last_message_from_match=request.last_message,
        )

        return AutoInsightResponse(insight=insight)

    except Exception as e:
        # Return a default insight if AI fails
        return AutoInsightResponse(
            insight="Keep the conversation going naturally!"
        )


@router.post("/compatibility/analyze")
async def analyze_profile_compatibility(
    request: CompatibilityRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze compatibility between two profiles using AI.
    """
    # Get both profiles
    profile_a_result = await db.execute(
        select(Profile).where(Profile.id == request.profile_a_id)
    )
    profile_a = profile_a_result.scalar_one_or_none()

    profile_b_result = await db.execute(
        select(Profile).where(Profile.id == request.profile_b_id)
    )
    profile_b = profile_b_result.scalar_one_or_none()

    if not profile_a or not profile_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both profiles not found.",
        )

    try:
        analysis = await analyze_compatibility(
            profile_a=profile_a.__dict__,
            profile_b=profile_b.__dict__,
        )

        return analysis

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compatibility analysis error: {str(e)}",
        )


@router.post("/conversation/analyze")
async def analyze_match_conversation(
    request: ConversationAnalysisRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a conversation and get private insights.
    Returns ONLY the insights meant for the requesting user.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == request.match_id,
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

    # Get user names
    user_a_id = str(match.user1_id)
    user_b_id = str(match.user2_id)

    profile_a_result = await db.execute(
        select(Profile).where(Profile.user_id == match.user1_id)
    )
    profile_a = profile_a_result.scalar_one_or_none()

    profile_b_result = await db.execute(
        select(Profile).where(Profile.user_id == match.user2_id)
    )
    profile_b = profile_b_result.scalar_one_or_none()

    user_a_name = profile_a.full_name if profile_a else "User A"
    user_b_name = profile_b.full_name if profile_b else "User B"

    try:
        # Get full analysis
        analysis = await analyze_conversation(
            messages=request.messages,
            user_a_id=user_a_id,
            user_a_name=user_a_name,
            user_b_id=user_b_id,
            user_b_name=user_b_name,
        )

        # Filter to only show this user's private insights
        user_key = "user_a" if str(current_user.id) == user_a_id else "user_b"
        private_insights = get_user_insights(analysis, user_key)

        return {
            "analysis": private_insights,
            "conversation_health": analysis.get("conversation_health", {}),
            "suggested_topics": analysis.get("suggested_topics", []),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversation analysis error: {str(e)}",
        )


@router.post("/safety/analyze")
async def analyze_safety(
    request: SafetyCheckRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze conversation for safety concerns.
    Detects scams, catfishing, manipulation, etc.
    """
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == request.match_id,
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

    # Get other user's info
    other_user_id = match.user2_id if match.user1_id == current_user.id else match.user1_id

    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    user_profile = profile_result.scalar_one_or_none()
    user_name = user_profile.full_name if user_profile else "You"

    other_profile_result = await db.execute(
        select(Profile).where(Profile.user_id == other_user_id)
    )
    other_profile = other_profile_result.scalar_one_or_none()
    other_name = other_profile.full_name if other_profile else "Other user"

    try:
        analysis = await check_safety(
            messages=request.messages,
            user_id=str(current_user.id),
            user_name=user_name,
            other_user_name=other_name,
            other_user_profile=other_profile.__dict__ if other_profile else None,
        )

        return analysis

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety analysis error: {str(e)}",
        )


@router.get("/health")
async def ai_health_check():
    """
    Check if AI services are working.
    Tests connection to Groq/Cerebras.
    """
    from app.agents.config import groq_client, cerebras_client

    status_report = {
        "groq": "unknown",
        "cerebras": "unknown",
        "overall": "unknown",
    }

    # Test Groq
    try:
        # Simple test call
        response = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=5,
        )
        status_report["groq"] = "healthy"
    except Exception as e:
        status_report["groq"] = f"error: {str(e)[:50]}"

    # Test Cerebras
    try:
        response = await cerebras_client.chat.completions.create(
            model="llama3.1-8b",
            messages=[{"role": "user", "content": "Say 'ok'"}],
            max_tokens=5,
        )
        status_report["cerebras"] = "healthy"
    except Exception as e:
        status_report["cerebras"] = f"error: {str(e)[:50]}"

    # Overall status
    if status_report["groq"] == "healthy" or status_report["cerebras"] == "healthy":
        status_report["overall"] = "healthy"
    else:
        status_report["overall"] = "degraded"

    return status_report
