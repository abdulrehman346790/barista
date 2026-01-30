from fastapi import APIRouter, Depends, HTTPException, status, Request
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
from app.config import settings


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # First IP in the list is the client's IP
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Register a new user.
    Sends OTP to phone for verification.
    If user exists but is not verified, allow re-registration.
    Rate limited: 3 registrations per hour per IP.
    """
    # Rate limiting check
    client_ip = get_client_ip(request)
    is_allowed, remaining, reset_seconds = await redis.check_register_rate_limit(client_ip)

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Try again in {reset_seconds // 60} minutes.",
            headers={"Retry-After": str(reset_seconds)},
        )

    # Check if phone already exists
    result = await db.execute(select(User).where(User.phone == user_data.phone))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number already registered. Please login instead.",
            )
        else:
            # User exists but not verified - update password and resend OTP
            existing_user.password_hash = get_password_hash(user_data.password)
            if user_data.email:
                existing_user.email = user_data.email
            await db.commit()
            await db.refresh(existing_user)
            user = existing_user
    else:
        # Check if email already exists (if provided)
        if user_data.email:
            result = await db.execute(select(User).where(User.email == user_data.email))
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        # Create new user
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

    # In production, send OTP via SMS service (Twilio, etc.)
    # TODO: Implement SMS sending

    response = {
        "message": "Registration successful. Please verify your phone.",
        "user_id": str(user.id),
        "otp_sent": True,
    }

    # Only include debug OTP in development mode
    if settings.DEBUG and settings.ENVIRONMENT == "development":
        response["debug_otp"] = otp

    return response


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    otp_data: OTPVerify,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Verify OTP and mark user as verified.
    Returns access and refresh tokens.
    Rate limited: 5 attempts per 10 minutes per phone.
    """
    # Rate limiting check
    is_allowed, remaining, reset_seconds = await redis.check_otp_rate_limit(otp_data.phone)

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many OTP verification attempts. Try again in {reset_seconds // 60} minutes.",
            headers={"Retry-After": str(reset_seconds)},
        )

    # Verify OTP
    is_valid = await redis.verify_otp(otp_data.phone, otp_data.otp)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or expired OTP. {remaining} attempts remaining.",
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: RedisService = Depends(get_redis_service),
):
    """
    Login with phone and password.
    Returns access and refresh tokens.
    Rate limited: 5 attempts per 15 minutes per phone/IP.
    """
    # Rate limiting check - by phone number
    is_allowed, remaining, reset_seconds = await redis.check_login_rate_limit(login_data.phone)

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {reset_seconds // 60} minutes.",
            headers={"Retry-After": str(reset_seconds)},
        )

    # Also check by IP to prevent distributed attacks
    client_ip = get_client_ip(request)
    ip_allowed, _, ip_reset = await redis.check_login_rate_limit(f"ip:{client_ip}")

    if not ip_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts from this IP. Try again in {ip_reset // 60} minutes.",
            headers={"Retry-After": str(ip_reset)},
        )

    # Get user
    result = await db.execute(select(User).where(User.phone == login_data.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid phone or password. {remaining} attempts remaining.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Reset rate limits on successful login
    await redis.reset_rate_limit(login_data.phone, "login")
    await redis.reset_rate_limit(f"ip:{client_ip}", "login")

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
    Rate limited: 3 resends per 30 minutes per phone.
    """
    # Rate limiting check
    is_allowed, remaining, reset_seconds = await redis.check_otp_resend_rate_limit(phone)

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many OTP resend requests. Try again in {reset_seconds // 60} minutes.",
            headers={"Retry-After": str(reset_seconds)},
        )

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

    # In production, send OTP via SMS service (Twilio, etc.)
    # TODO: Implement SMS sending

    response = {
        "message": "OTP sent successfully",
        "remaining_resends": remaining,
    }

    # Only include debug OTP in development mode
    if settings.DEBUG and settings.ENVIRONMENT == "development":
        response["debug_otp"] = otp

    return response
