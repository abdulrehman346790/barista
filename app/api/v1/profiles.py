from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import date

from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_verified_user
from app.models.user import User, Profile
from app.schemas.user import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfilePublic,
)


router = APIRouter(prefix="/profiles", tags=["Profiles"])


def calculate_age(birth_date: date) -> int:
    """Calculate age from date of birth."""
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile."""
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please create a profile first.",
        )

    return profile


@router.post("/me", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    profile_data: ProfileCreate,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Create profile for current user."""
    # Check if profile already exists
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    existing_profile = result.scalar_one_or_none()

    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists. Use PUT to update.",
        )

    # Validate age (must be 18+)
    age = calculate_age(profile_data.date_of_birth)
    if age < 18:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be at least 18 years old to create a profile.",
        )

    # Create profile
    profile = Profile(
        user_id=current_user.id,
        **profile_data.model_dump(),
    )

    # Check if profile is complete (has required fields)
    required_fields = ["full_name", "gender", "date_of_birth", "city", "country"]
    profile.is_complete = all(
        getattr(profile, field) is not None for field in required_fields
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile


@router.put("/me", response_model=ProfileResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create a profile first.",
        )

    # Update only provided fields
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    # Re-check if profile is complete
    required_fields = ["full_name", "gender", "date_of_birth", "city", "country"]
    profile.is_complete = all(
        getattr(profile, field) is not None for field in required_fields
    )

    await db.commit()
    await db.refresh(profile)

    return profile


@router.get("/{user_id}", response_model=ProfilePublic)
async def get_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get another user's public profile."""
    result = await db.execute(
        select(Profile).where(Profile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    # Calculate age for public profile
    age = calculate_age(profile.date_of_birth)

    return ProfilePublic(
        id=profile.id,
        full_name=profile.full_name,
        gender=profile.gender,
        age=age,
        height_cm=profile.height_cm,
        city=profile.city,
        country=profile.country,
        sect=profile.sect,
        religiosity=profile.religiosity,
        education_level=profile.education_level,
        profession=profile.profession,
        bio=profile.bio,
        photos=profile.photos or [],
        verification_status=profile.verification_status,
    )


@router.post("/me/photos", response_model=ProfileResponse)
async def add_photo(
    photo_url: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a photo URL to profile.
    Note: In production, implement file upload to cloud storage (S3, Firebase Storage).
    For now, accepts direct URLs.
    """
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create a profile first.",
        )

    # Limit to 6 photos
    if profile.photos and len(profile.photos) >= 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 6 photos allowed.",
        )

    # Add photo URL
    photos = profile.photos or []
    photos.append(photo_url)
    profile.photos = photos

    await db.commit()
    await db.refresh(profile)

    return profile


@router.delete("/me/photos/{photo_index}", response_model=ProfileResponse)
async def delete_photo(
    photo_index: int,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a photo by index."""
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    if not profile.photos or photo_index >= len(profile.photos):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid photo index.",
        )

    # Remove photo
    photos = profile.photos.copy()
    photos.pop(photo_index)
    profile.photos = photos

    await db.commit()
    await db.refresh(profile)

    return profile


@router.post("/me/verify", response_model=dict)
async def request_verification(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Request profile verification.
    In production, this would trigger a manual review process.
    """
    result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    if not profile.is_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complete your profile before requesting verification.",
        )

    if profile.verification_status == "verified":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is already verified.",
        )

    # Mark as pending verification
    profile.verification_status = "pending"
    await db.commit()

    return {
        "message": "Verification request submitted. You will be notified once reviewed.",
        "status": "pending",
    }
