from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from app.db.session import get_db
from app.core.dependencies import get_current_verified_user
from app.models.user import User, Profile
from app.models.match import Match, SafetyAlert
from app.models.guardian import GuardianLink


router = APIRouter(prefix="/guardian", tags=["Guardian (Wali)"])


# ==================== Schemas ====================

class GuardianInvite(BaseModel):
    """Invite a guardian."""
    guardian_phone: str
    relationship: str  # father, mother, brother, sister, other


class GuardianLinkResponse(BaseModel):
    """Guardian link response."""
    id: UUID
    user_id: UUID
    guardian_user_id: UUID
    relationship: str
    can_view_matches: bool
    can_view_safety_alerts: bool
    alert_on_red_zone: bool
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class GuardianDashboard(BaseModel):
    """Guardian's view of their ward's activity."""
    ward_name: str
    ward_id: UUID
    total_matches: int
    active_matches: int
    red_zone_alerts: int
    safety_status: str  # green, yellow, red
    last_active: Optional[datetime]


class GuardianAlert(BaseModel):
    """Alert visible to guardian."""
    id: UUID
    match_id: UUID
    alert_type: str
    severity: str
    description: Optional[str]
    created_at: datetime


# ==================== User Endpoints ====================

@router.post("/invite", response_model=dict)
async def invite_guardian(
    invite: GuardianInvite,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a guardian (Wali) to monitor your safety.
    Guardian must have an account with the specified phone number.
    """
    # Find guardian by phone
    guardian_result = await db.execute(
        select(User).where(User.phone == invite.guardian_phone)
    )
    guardian = guardian_result.scalar_one_or_none()

    if not guardian:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this phone number. Guardian must register first.",
        )

    if guardian.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite yourself as guardian.",
        )

    # Check if link already exists
    existing_link = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.user_id == current_user.id,
                GuardianLink.guardian_user_id == guardian.id,
            )
        )
    )
    if existing_link.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guardian link already exists.",
        )

    # Create guardian link (pending approval)
    link = GuardianLink(
        user_id=current_user.id,
        guardian_user_id=guardian.id,
        relationship=invite.relationship,
        status="pending",
    )
    db.add(link)
    await db.commit()

    return {
        "message": "Guardian invitation sent. They will need to accept.",
        "guardian_id": str(guardian.id),
        "status": "pending",
    }


@router.get("/status", response_model=List[GuardianLinkResponse])
async def get_guardian_status(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all guardian links for current user (as ward)."""
    result = await db.execute(
        select(GuardianLink).where(GuardianLink.user_id == current_user.id)
    )
    links = result.scalars().all()

    return [GuardianLinkResponse.model_validate(link) for link in links]


@router.delete("/revoke/{link_id}")
async def revoke_guardian(
    link_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a guardian's access."""
    result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.id == link_id,
                GuardianLink.user_id == current_user.id,
            )
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guardian link not found.",
        )

    link.status = "revoked"
    await db.commit()

    return {"message": "Guardian access revoked."}


# ==================== Guardian Endpoints ====================

@router.get("/pending", response_model=List[GuardianLinkResponse])
async def get_pending_invites(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending guardian invites (as guardian)."""
    result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.guardian_user_id == current_user.id,
                GuardianLink.status == "pending",
            )
        )
    )
    links = result.scalars().all()

    return [GuardianLinkResponse.model_validate(link) for link in links]


@router.post("/accept/{link_id}")
async def accept_guardian_invite(
    link_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a guardian invite."""
    result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.id == link_id,
                GuardianLink.guardian_user_id == current_user.id,
                GuardianLink.status == "pending",
            )
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found.",
        )

    link.status = "active"
    await db.commit()

    return {"message": "Guardian invite accepted. You can now view safety status."}


@router.post("/decline/{link_id}")
async def decline_guardian_invite(
    link_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Decline a guardian invite."""
    result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.id == link_id,
                GuardianLink.guardian_user_id == current_user.id,
                GuardianLink.status == "pending",
            )
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending invite not found.",
        )

    await db.delete(link)
    await db.commit()

    return {"message": "Guardian invite declined."}


@router.get("/dashboard", response_model=List[GuardianDashboard])
async def get_guardian_dashboard(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get guardian dashboard showing all wards' safety status.
    Note: Shows only safety metrics, NOT chat content (privacy preserving).
    """
    # Get all active guardian links where current user is guardian
    links_result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.guardian_user_id == current_user.id,
                GuardianLink.status == "active",
            )
        )
    )
    links = links_result.scalars().all()

    dashboards = []

    for link in links:
        # Get ward's profile
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == link.user_id)
        )
        profile = profile_result.scalar_one_or_none()

        # Get match counts
        matches_result = await db.execute(
            select(Match).where(
                or_(
                    Match.user1_id == link.user_id,
                    Match.user2_id == link.user_id,
                )
            )
        )
        matches = matches_result.scalars().all()
        total_matches = len(matches)
        active_matches = len([m for m in matches if m.status == "active"])

        # Get safety alerts
        alerts_result = await db.execute(
            select(SafetyAlert).where(SafetyAlert.flagged_user_id != link.user_id)
        )
        # Filter alerts that involve the ward's matches
        ward_match_ids = [m.id for m in matches]
        all_alerts = alerts_result.scalars().all()
        red_zone_alerts = len([a for a in all_alerts if a.match_id in ward_match_ids])

        # Determine safety status
        if red_zone_alerts > 2:
            safety_status = "red"
        elif red_zone_alerts > 0:
            safety_status = "yellow"
        else:
            safety_status = "green"

        dashboards.append(
            GuardianDashboard(
                ward_name=profile.full_name if profile else "Unknown",
                ward_id=link.user_id,
                total_matches=total_matches,
                active_matches=active_matches,
                red_zone_alerts=red_zone_alerts,
                safety_status=safety_status,
                last_active=None,  # Could track from chat metadata
            )
        )

    return dashboards


@router.get("/alerts/{ward_id}", response_model=List[GuardianAlert])
async def get_ward_alerts(
    ward_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get safety alerts for a specific ward."""
    # Verify guardian has access to this ward
    link_result = await db.execute(
        select(GuardianLink).where(
            and_(
                GuardianLink.guardian_user_id == current_user.id,
                GuardianLink.user_id == ward_id,
                GuardianLink.status == "active",
                GuardianLink.can_view_safety_alerts == True,
            )
        )
    )
    link = link_result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this ward's alerts.",
        )

    # Get ward's matches
    matches_result = await db.execute(
        select(Match).where(
            or_(
                Match.user1_id == ward_id,
                Match.user2_id == ward_id,
            )
        )
    )
    matches = matches_result.scalars().all()
    match_ids = [str(m.id) for m in matches]

    # Get alerts for these matches
    alerts_result = await db.execute(
        select(SafetyAlert).where(SafetyAlert.match_id.in_(match_ids))
    )
    alerts = alerts_result.scalars().all()

    return [
        GuardianAlert(
            id=alert.id,
            match_id=alert.match_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            description=alert.description,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]
