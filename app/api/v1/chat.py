from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.core.dependencies import get_current_verified_user
from app.core.firebase import firebase_service
from app.models.user import User
from app.models.match import Match, ChatMetadata


router = APIRouter(prefix="/chat", tags=["Chat"])


# ==================== Schemas ====================

class FirebaseTokenResponse(BaseModel):
    """Firebase custom token for client authentication."""
    token: str
    expires_in: int = 3600  # 1 hour


class ChatMetadataResponse(BaseModel):
    """Chat statistics for AI analysis."""
    match_id: str
    user_id: str
    total_messages: int
    total_words: int
    avg_response_time_seconds: Optional[int]
    message_ratio: Optional[float]
    avg_sentiment_score: Optional[float]
    questions_asked: int
    emojis_used: int
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMetadataUpdate(BaseModel):
    """Update chat metadata from client."""
    total_messages: int
    total_words: int
    avg_response_time_seconds: Optional[int] = None
    questions_asked: int = 0
    emojis_used: int = 0
    avg_sentiment_score: Optional[float] = None


# ==================== Endpoints ====================

@router.get("/token", response_model=FirebaseTokenResponse)
async def get_firebase_token(
    current_user: User = Depends(get_current_verified_user),
):
    """
    Get a Firebase custom token for client-side authentication.
    Use this token to authenticate with Firebase Realtime Database.
    """
    try:
        token = firebase_service.get_custom_token(str(current_user.id))
        return FirebaseTokenResponse(token=token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Firebase token: {str(e)}",
        )


@router.get("/{match_id}/metadata", response_model=ChatMetadataResponse)
async def get_chat_metadata(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chat metadata/statistics for a match."""
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_id,
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

    # Get or create chat metadata for this user
    metadata_result = await db.execute(
        select(ChatMetadata).where(
            and_(
                ChatMetadata.match_id == match_id,
                ChatMetadata.user_id == current_user.id,
            )
        )
    )
    metadata = metadata_result.scalar_one_or_none()

    if not metadata:
        # Create initial metadata
        metadata = ChatMetadata(
            match_id=match_id,
            user_id=current_user.id,
            total_messages=0,
            total_words=0,
            questions_asked=0,
            emojis_used=0,
        )
        db.add(metadata)
        await db.commit()
        await db.refresh(metadata)

    return metadata


@router.post("/{match_id}/metadata", response_model=ChatMetadataResponse)
async def update_chat_metadata(
    match_id: str,
    metadata_update: ChatMetadataUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update chat metadata from client.
    Called by mobile app after analyzing messages locally (Edge AI).
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

    # Get or create chat metadata
    metadata_result = await db.execute(
        select(ChatMetadata).where(
            and_(
                ChatMetadata.match_id == match_id,
                ChatMetadata.user_id == current_user.id,
            )
        )
    )
    metadata = metadata_result.scalar_one_or_none()

    if not metadata:
        metadata = ChatMetadata(
            match_id=match_id,
            user_id=current_user.id,
        )
        db.add(metadata)

    # Update metadata
    metadata.total_messages = metadata_update.total_messages
    metadata.total_words = metadata_update.total_words
    metadata.avg_response_time_seconds = metadata_update.avg_response_time_seconds
    metadata.questions_asked = metadata_update.questions_asked
    metadata.emojis_used = metadata_update.emojis_used
    metadata.avg_sentiment_score = metadata_update.avg_sentiment_score

    # Calculate message ratio if both users have metadata
    other_user_id = (
        match.user2_id if match.user1_id == current_user.id else match.user1_id
    )
    other_metadata_result = await db.execute(
        select(ChatMetadata).where(
            and_(
                ChatMetadata.match_id == match_id,
                ChatMetadata.user_id == other_user_id,
            )
        )
    )
    other_metadata = other_metadata_result.scalar_one_or_none()

    if other_metadata and (metadata.total_messages + other_metadata.total_messages) > 0:
        total = metadata.total_messages + other_metadata.total_messages
        metadata.message_ratio = metadata.total_messages / total
        other_metadata.message_ratio = other_metadata.total_messages / total

    await db.commit()
    await db.refresh(metadata)

    return metadata


@router.post("/{match_id}/read")
async def mark_messages_read(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all messages in a chat as read."""
    # Verify user is part of this match
    match_result = await db.execute(
        select(Match).where(
            and_(
                Match.id == match_id,
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

    # Update Firebase read status
    try:
        firebase_service.mark_messages_read(match_id, str(current_user.id))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update read status: {str(e)}",
        )

    return {"message": "Messages marked as read."}
