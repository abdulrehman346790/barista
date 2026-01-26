from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.redis import RedisService
from app.core.dependencies import get_current_user, get_redis_service
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    generate_otp,
)
from app.models.user import User
from app.schemas.user import (
    UserRegister,
    UserLogin,
    OTPVerify,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Register a new user.
    Sends OTP to phone for verification.
    """
    # Check if phone already exists
    result = await db.execute(select(User).where(User.phone == user_data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    # Check if email already exists (if provided)
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Create user
    user = User(
        phone=user_data.phone,
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate and store OTP
    otp = generate_otp()
    await redis.store_otp(user_data.phone, otp)

    # In production, send OTP via SMS
    # For development, return it in response
    return {
        "message": "Registration successful. Please verify your phone.",
        "user_id": str(user.id),
        "otp_sent": True,
        # Remove this in production!
        "debug_otp": otp,
    }


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    otp_data: OTPVerify,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Verify OTP and mark user as verified.
    Returns access and refresh tokens.
    """
    # Verify OTP
    is_valid = await redis.verify_otp(otp_data.phone, otp_data.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    # Get user
    result = await db.execute(select(User).where(User.phone == otp_data.phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Mark as verified
    user.is_verified = True
    await db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token in Redis
    await redis.store_refresh_token(str(user.id), refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Login with phone and password.
    Returns access and refresh tokens.
    """
    # Get user
    result = await db.execute(select(User).where(User.phone == login_data.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store refresh token
    await redis.store_refresh_token(str(user.id), refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_data: RefreshTokenRequest,
    redis: RedisService = Depends(get_redis_service),
):
    """
    Refresh access token using refresh token.
    """
    # Verify refresh token
    token_payload = verify_refresh_token(token_data.refresh_token)
    user_id = token_payload.user_id

    # Check if refresh token is still valid in Redis
    stored_token = await redis.get_refresh_token(user_id)
    if stored_token != token_data.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Generate new tokens
    access_token = create_access_token(data={"sub": user_id})
    new_refresh_token = create_refresh_token(data={"sub": user_id})

    # Update refresh token in Redis
    await redis.store_refresh_token(user_id, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Logout user by invalidating refresh token.
    """
    await redis.delete_refresh_token(str(current_user.id))
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user information.
    """
    return current_user


@router.post("/resend-otp")
async def resend_otp(
    phone: str,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Resend OTP to phone number.
    """
    # Check if user exists
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone already verified",
        )

    # Generate and store new OTP
    otp = generate_otp()
    await redis.store_otp(phone, otp)

    # In production, send OTP via SMS
    return {
        "message": "OTP sent successfully",
        # Remove this in production!
        "debug_otp": otp,
    }
