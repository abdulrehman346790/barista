from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, not_
from typing import List, Optional
from datetime import date
import uuid

from app.db.session import get_db
from app.db.redis import RedisService
from app.core.dependencies import get_current_verified_user, get_redis_service
from app.core.firebase import firebase_service
from app.models.user import User, Profile
from app.models.match import Swipe, Match
from app.schemas.match import (
    SwipeCreate,
    SwipeResponse,
    MatchResponse,
    MatchWithProfile,
    MatchListResponse,
    DiscoverProfile,
    DiscoverResponse,
)


router = APIRouter(prefix="/matching", tags=["Matching"])


def calculate_age(birth_date: date) -> int:
    """Calculate age from date of birth."""
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


@router.get("/discover", response_model=DiscoverResponse)
async def discover_profiles(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Get profiles to swipe on (discover deck).
    Excludes:
    - Already swiped profiles
    - Already matched profiles
    - Own profile
    - Blocked users
    """
    # Check swipe limit
    can_swipe, remaining = await redis.check_swipe_limit(str(current_user.id))

    # Get current user's profile to determine gender preference
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    my_profile = result.scalar_one_or_none()

    if not my_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your profile first before discovering matches.",
        )

    if not my_profile.is_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete your profile to start discovering matches.",
        )

    # Get IDs of users already swiped
    swiped_result = await db.execute(
        select(Swipe.swiped_id).where(Swipe.swiper_id == current_user.id)
    )
    swiped_ids = [row[0] for row in swiped_result.fetchall()]

    # Get IDs of users in existing matches (active or blocked)
    matches_result = await db.execute(
        select(Match).where(
            or_(
                Match.user1_id == current_user.id,
                Match.user2_id == current_user.id,
            )
        )
    )
    matches = matches_result.scalars().all()
    matched_ids = []
    for match in matches:
        other_id = match.user2_id if match.user1_id == current_user.id else match.user1_id
        matched_ids.append(other_id)

    # Exclude own ID, swiped, and matched users
    excluded_ids = set(swiped_ids + matched_ids + [current_user.id])

    # Determine opposite gender for matching
    opposite_gender = "female" if my_profile.gender == "male" else "male"

    # Query for discoverable profiles
    query = (
        select(Profile)
        .join(User, Profile.user_id == User.id)
        .where(
            and_(
                Profile.is_complete == True,
                Profile.gender == opposite_gender,
                User.is_active == True,
                User.is_verified == True,
                not_(Profile.user_id.in_(excluded_ids)) if excluded_ids else True,
            )
        )
        .limit(limit)
    )

    result = await db.execute(query)
    profiles = result.scalars().all()

    # Convert to response format
    discover_profiles = []
    for profile in profiles:
        discover_profiles.append(
            DiscoverProfile(
                user_id=profile.user_id,
                profile_id=profile.id,
                full_name=profile.full_name,
                age=calculate_age(profile.date_of_birth),
                city=profile.city,
                country=profile.country,
                height_cm=profile.height_cm,
                sect=profile.sect,
                religiosity=profile.religiosity,
                education_level=profile.education_level,
                profession=profile.profession,
                bio=profile.bio,
                photos=profile.photos or [],
                verification_status=profile.verification_status,
            )
        )

    return DiscoverResponse(
        profiles=discover_profiles,
        remaining_swipes=remaining,
    )


@router.post("/swipe", response_model=SwipeResponse)
async def swipe(
    swipe_data: SwipeCreate,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Record a swipe (like, pass, or super_like).
    If mutual like, creates a match.
    """
    # Check swipe limit
    can_swipe, remaining = await redis.check_swipe_limit(str(current_user.id))
    if not can_swipe:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily swipe limit reached. Upgrade to premium for unlimited swipes.",
        )

    # Prevent swiping on self
    if swipe_data.swiped_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot swipe on yourself.",
        )

    # Check if already swiped
    existing_swipe = await db.execute(
        select(Swipe).where(
            and_(
                Swipe.swiper_id == current_user.id,
                Swipe.swiped_id == swipe_data.swiped_id,
            )
        )
    )
    if existing_swipe.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already swiped on this user.",
        )

    # Create swipe record
    swipe = Swipe(
        swiper_id=current_user.id,
        swiped_id=swipe_data.swiped_id,
        direction=swipe_data.direction,
    )
    db.add(swipe)

    is_match = False

    # Check for mutual like (match)
    if swipe_data.direction in ["like", "super_like"]:
        reverse_swipe = await db.execute(
            select(Swipe).where(
                and_(
                    Swipe.swiper_id == swipe_data.swiped_id,
                    Swipe.swiped_id == current_user.id,
                    Swipe.direction.in_(["like", "super_like"]),
                )
            )
        )
        if reverse_swipe.scalar_one_or_none():
            # It's a match!
            is_match = True
            match_id = str(uuid.uuid4())

            # Create match record
            match = Match(
                id=match_id,
                user1_id=current_user.id,
                user2_id=swipe_data.swiped_id,
                status="active",
                firebase_chat_id=match_id,
            )
            db.add(match)

            # Create Firebase chat room
            try:
                firebase_service.create_chat_room(
                    match_id=match_id,
                    user1_id=str(current_user.id),
                    user2_id=str(swipe_data.swiped_id),
                )
            except Exception as e:
                # Log error but don't fail the match
                print(f"Firebase chat creation failed: {e}")

    await db.commit()
    await db.refresh(swipe)

    return SwipeResponse(
        id=swipe.id,
        swiper_id=swipe.swiper_id,
        swiped_id=swipe.swiped_id,
        direction=swipe.direction,
        created_at=swipe.created_at,
        is_match=is_match,
    )


@router.get("/matches", response_model=MatchListResponse)
async def get_matches(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active matches for current user."""
    # Get matches where user is either user1 or user2
    result = await db.execute(
        select(Match).where(
            and_(
                or_(
                    Match.user1_id == current_user.id,
                    Match.user2_id == current_user.id,
                ),
                Match.status == "active",
            )
        )
    )
    matches = result.scalars().all()

    # Build response with matched user profiles
    match_list = []
    for match in matches:
        # Get the other user's ID
        other_user_id = (
            match.user2_id if match.user1_id == current_user.id else match.user1_id
        )

        # Get their profile
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == other_user_id)
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            match_list.append(
                MatchWithProfile(
                    match_id=match.id,
                    matched_user_id=other_user_id,
                    matched_user_name=profile.full_name,
                    matched_user_photo=profile.photos[0] if profile.photos else None,
                    matched_user_age=calculate_age(profile.date_of_birth),
                    firebase_chat_id=match.firebase_chat_id,
                    created_at=match.created_at,
                    status=match.status,
                )
            )

    return MatchListResponse(
        matches=match_list,
        total=len(match_list),
    )


@router.delete("/matches/{match_id}")
async def unmatch(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Unmatch from a user."""
    result = await db.execute(
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
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    # Update match status
    match.status = "unmatched"
    from datetime import datetime
    match.unmatched_at = datetime.utcnow()

    # Delete Firebase chat room
    try:
        firebase_service.delete_chat_room(match.firebase_chat_id)
    except Exception as e:
        print(f"Firebase chat deletion failed: {e}")

    await db.commit()

    return {"message": "Successfully unmatched."}


@router.post("/matches/{match_id}/block")
async def block_user(
    match_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Block a matched user."""
    result = await db.execute(
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
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    # Update match status to blocked
    match.status = "blocked"
    from datetime import datetime
    match.unmatched_at = datetime.utcnow()

    # Delete Firebase chat room
    try:
        firebase_service.delete_chat_room(match.firebase_chat_id)
    except Exception as e:
        print(f"Firebase chat deletion failed: {e}")

    await db.commit()

    return {"message": "User blocked successfully."}
