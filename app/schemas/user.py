from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
import re


# ==================== Auth Schemas ====================

class UserRegister(BaseModel):
    """Schema for user registration."""
    phone: str = Field(..., min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=100)
    email: Optional[EmailStr] = None

    @validator("phone")
    def validate_phone(cls, v):
        # Remove spaces and dashes
        cleaned = re.sub(r"[\s\-]", "", v)
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if not re.match(r"^\+\d{10,15}$", cleaned):
            raise ValueError("Invalid phone number format. Use international format: +1234567890")
        return cleaned


class UserLogin(BaseModel):
    """Schema for user login."""
    phone: str
    password: str


class OTPVerify(BaseModel):
    """Schema for OTP verification."""
    phone: str
    otp: str = Field(..., min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Schema for token refresh."""
    refresh_token: str


# ==================== Profile Schemas ====================

class ProfileBase(BaseModel):
    """Base profile fields."""
    full_name: str = Field(..., min_length=2, max_length=100)
    gender: str = Field(..., pattern="^(male|female)$")
    date_of_birth: date
    height_cm: Optional[int] = Field(None, ge=100, le=250)

    # Location
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    willing_to_relocate: bool = False

    # Religious Info
    sect: Optional[str] = Field(None, pattern="^(sunni|shia|other)$")
    religiosity: Optional[str] = Field(
        None, pattern="^(very_practicing|practicing|moderate|cultural)$"
    )
    prayer_frequency: Optional[str] = Field(
        None, pattern="^(five_daily|some|occasionally|rarely)$"
    )
    hijab_preference: Optional[str] = Field(None, pattern="^(wears|sometimes|no)$")
    beard_preference: Optional[str] = Field(None, pattern="^(full|trimmed|clean)$")

    # Education & Career
    education_level: Optional[str] = Field(None, max_length=50)
    profession: Optional[str] = Field(None, max_length=100)
    income_range: Optional[str] = Field(None, max_length=50)

    # Family
    marital_status: Optional[str] = Field(
        None, pattern="^(never_married|divorced|widowed)$"
    )
    has_children: bool = False
    wants_children: Optional[str] = Field(None, pattern="^(yes|no|maybe)$")

    # Bio
    bio: Optional[str] = Field(None, max_length=1000)


class ProfileCreate(ProfileBase):
    """Schema for creating a profile."""
    pass


class ProfileUpdate(BaseModel):
    """Schema for updating a profile (all fields optional)."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    height_cm: Optional[int] = Field(None, ge=100, le=250)
    city: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    willing_to_relocate: Optional[bool] = None
    sect: Optional[str] = None
    religiosity: Optional[str] = None
    prayer_frequency: Optional[str] = None
    hijab_preference: Optional[str] = None
    beard_preference: Optional[str] = None
    education_level: Optional[str] = None
    profession: Optional[str] = None
    income_range: Optional[str] = None
    marital_status: Optional[str] = None
    has_children: Optional[bool] = None
    wants_children: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=1000)


class ProfileResponse(ProfileBase):
    """Schema for profile response."""
    id: UUID
    user_id: UUID
    photos: List[str] = []
    is_complete: bool
    verification_status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfilePublic(BaseModel):
    """Public profile visible to other users."""
    id: UUID
    full_name: str
    gender: str
    age: int  # Calculated from date_of_birth
    height_cm: Optional[int]
    city: Optional[str]
    country: Optional[str]
    sect: Optional[str]
    religiosity: Optional[str]
    education_level: Optional[str]
    profession: Optional[str]
    bio: Optional[str]
    photos: List[str]
    verification_status: str


# ==================== User Response ====================

class UserResponse(BaseModel):
    """Schema for user response."""
    id: UUID
    phone: str
    email: Optional[str]
    is_verified: bool
    is_active: bool
    created_at: datetime
    profile: Optional[ProfileResponse] = None

    class Config:
        from_attributes = True
