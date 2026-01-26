from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ==================== Swipe Schemas ====================

class SwipeCreate(BaseModel):
    """Schema for creating a swipe."""
    swiped_id: UUID
    direction: str = Field(..., pattern="^(like|pass|super_like)$")


class SwipeResponse(BaseModel):
    """Schema for swipe response."""
    id: UUID
    swiper_id: UUID
    swiped_id: UUID
    direction: str
    created_at: datetime
    is_match: bool = False  # True if this swipe created a match

    class Config:
        from_attributes = True


# ==================== Match Schemas ====================

class MatchResponse(BaseModel):
    """Schema for match response."""
    id: UUID
    user1_id: UUID
    user2_id: UUID
    status: str
    firebase_chat_id: Optional[str]
    created_at: datetime
    unmatched_at: Optional[datetime]

    class Config:
        from_attributes = True


class MatchWithProfile(BaseModel):
    """Match with the other user's profile info."""
    match_id: UUID
    matched_user_id: UUID
    matched_user_name: str
    matched_user_photo: Optional[str]
    matched_user_age: int
    firebase_chat_id: Optional[str]
    created_at: datetime
    status: str


class MatchListResponse(BaseModel):
    """List of matches."""
    matches: List[MatchWithProfile]
    total: int


# ==================== Discover Schemas ====================

class DiscoverProfile(BaseModel):
    """Profile shown in discover/swipe deck."""
    user_id: UUID
    profile_id: UUID
    full_name: str
    age: int
    city: Optional[str]
    country: Optional[str]
    height_cm: Optional[int]
    sect: Optional[str]
    religiosity: Optional[str]
    education_level: Optional[str]
    profession: Optional[str]
    bio: Optional[str]
    photos: List[str]
    verification_status: str


class DiscoverResponse(BaseModel):
    """Response for discover endpoint."""
    profiles: List[DiscoverProfile]
    remaining_swipes: int
