"""
AI Coach Endpoints
New agent-based AI system using Groq/Cerebras with RAG support
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID as PyUUID
import traceback

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

# Import RAG service
from app.services.rag_service import (
    index_chat_message,
    index_chat_history,
    get_relevant_context,
    format_context_for_ai,
)

router = APIRouter(prefix="/ai-coach", tags=["AI Coach"])


def model_to_dict(obj) -> dict:
    """Convert SQLAlchemy model to dict without internal attributes."""
    if obj is None:
        return None
    result = {}
    for c in obj.__table__.columns:
        val = getattr(obj, c.name)
        # Convert UUID and datetime to string for JSON serialization
        if hasattr(val, 'hex'):  # UUID
            result[c.name] = str(val)
        elif hasattr(val, 'isoformat'):  # datetime
            result[c.name] = val.isoformat()
        else:
            result[c.name] = val
    return result


# ================== Pydantic Schemas ==================

class HistoryMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str

class CoachQuestionRequest(BaseModel):
    match_id: str
    question: str
    history: list[HistoryMessage] = []  # Previous conversation for context

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


# RAG-related schemas
class ChatMessage(BaseModel):
    sender_id: str
    sender_name: str
    content: str
    timestamp: Optional[str] = None

class IndexMessagesRequest(BaseModel):
    match_id: str
    messages: List[ChatMessage]

class IndexMessageRequest(BaseModel):
    match_id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: Optional[str] = None


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
    # Convert match_id to UUID
    try:
        match_uuid = PyUUID(request.match_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid match_id format. Must be a valid UUID.",
        )

    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_uuid,
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

    # Convert history to the format expected by coach
    coach_history = [{"role": h.role, "content": h.content} for h in request.history]

    # Get RAG context for this match
    try:
        rag_context = get_relevant_context(
            match_id=request.match_id,
            query=request.question,
            top_k=5,
            include_recent=15
        )
        conversation_context = format_context_for_ai(rag_context)
    except Exception as e:
        print(f"RAG context retrieval warning: {e}")
        conversation_context = ""

    try:
        response = await get_coach_response(
            user_id=str(current_user.id),
            user_name=user_name,
            match_name=match_name,
            conversation=[],  # Legacy param - kept for compatibility
            question=request.question,
            user_profile=model_to_dict(user_profile),
            match_profile=model_to_dict(other_profile),
            coach_history=coach_history,  # Previous AI coach conversation
            rag_context=conversation_context,  # NEW: RAG context
        )

        return CoachResponse(response=response)

    except Exception as e:
        print(f"AI Coach Error: {str(e)}")
        print(traceback.format_exc())
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
                Match.id == PyUUID(request.match_id),
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
        select(Profile).where(Profile.id == PyUUID(request.profile_a_id))
    )
    profile_a = profile_a_result.scalar_one_or_none()

    profile_b_result = await db.execute(
        select(Profile).where(Profile.id == PyUUID(request.profile_b_id))
    )
    profile_b = profile_b_result.scalar_one_or_none()

    if not profile_a or not profile_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both profiles not found.",
        )

    try:
        analysis = await analyze_compatibility(
            profile_a=model_to_dict(profile_a),
            profile_b=model_to_dict(profile_b),
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
                Match.id == PyUUID(request.match_id),
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
                Match.id == PyUUID(request.match_id),
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
            other_user_profile=model_to_dict(other_profile),
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


# ================== RAG Endpoints ==================

@router.post("/rag/index-message")
async def index_single_message(
    request: IndexMessageRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Index a single chat message into RAG for context retrieval.
    Call this when a new message is sent/received.
    """
    # Verify user is part of this match
    try:
        match_uuid = PyUUID(request.match_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid match_id format.",
        )

    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_uuid,
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

    try:
        added = index_chat_message(
            match_id=request.match_id,
            sender_id=request.sender_id,
            sender_name=request.sender_name,
            content=request.content,
            timestamp=request.timestamp,
        )

        return {
            "success": True,
            "added": added,
            "message": "Message indexed" if added else "Message already exists"
        }

    except Exception as e:
        print(f"RAG index error: {e}")
        # Don't fail the request - RAG is optional enhancement
        return {
            "success": False,
            "added": False,
            "message": f"RAG indexing failed: {str(e)}"
        }


@router.post("/rag/index-history")
async def index_chat_history_endpoint(
    request: IndexMessagesRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Index multiple chat messages at once.
    Call this to sync existing chat history into RAG.
    """
    # Verify user is part of this match
    try:
        match_uuid = PyUUID(request.match_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid match_id format.",
        )

    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_uuid,
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

    try:
        # Convert Pydantic models to dicts
        messages = [msg.dict() for msg in request.messages]
        count = index_chat_history(request.match_id, messages)

        return {
            "success": True,
            "indexed_count": count,
            "total_sent": len(request.messages),
            "message": f"Indexed {count} new messages"
        }

    except Exception as e:
        print(f"RAG batch index error: {e}")
        return {
            "success": False,
            "indexed_count": 0,
            "message": f"RAG indexing failed: {str(e)}"
        }


@router.get("/rag/context/{match_id}")
async def get_rag_context(
    match_id: str,
    query: str = "conversation context",
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get RAG context for a match.
    Useful for debugging or showing conversation insights.
    """
    # Verify user is part of this match
    try:
        match_uuid = PyUUID(match_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid match_id format.",
        )

    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_uuid,
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

    try:
        context = get_relevant_context(
            match_id=match_id,
            query=query,
            top_k=5,
            include_recent=10
        )

        return {
            "success": True,
            "context": context,
            "formatted": format_context_for_ai(context)
        }

    except Exception as e:
        print(f"RAG context error: {e}")
        return {
            "success": False,
            "context": None,
            "message": f"Failed to get context: {str(e)}"
        }
