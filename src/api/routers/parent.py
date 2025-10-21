"""Parent dashboard router - handles parent profile and monitoring endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.auth_dependencies import get_current_active_user
from ...core.database import get_db
from ...core.parent_service import ParentService
from ...models.db_models import User
from ...models.parent_schemas import (
    ChildDetailResponse,
    ChildPracticeSession,
    ChildSubjectPerformance,
    LinkedStudentResponse,
    LinkStudentRequest,
    ParentInsight,
    ParentInsightsResponse,
    ParentOverviewResponse,
    ParentProfileCreate,
    ParentProfileResponse,
    ParentProfileUpdate,
)
from ...models.auth_schemas import MessageResponse

router = APIRouter()


# ============================================================================
# PARENT PROFILE ENDPOINTS
# ============================================================================


@router.get("/profile", response_model=ParentProfileResponse)
async def get_parent_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get the current parent's profile.

    Returns profile information including notification preferences.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    profile = service.get_or_create_parent_profile(current_user.id)
    return profile


@router.put("/profile", response_model=ParentProfileResponse)
async def update_parent_profile(
    profile_data: ParentProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update the current parent's profile.

    Allows updating phone number, notification preferences, report preferences, etc.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    update_dict = profile_data.model_dump(exclude_unset=True)
    profile = service.update_parent_profile(current_user.id, update_dict)
    return profile


@router.post("/profile", response_model=ParentProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_parent_profile(
    profile_data: ParentProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create or update parent profile.

    This endpoint is idempotent - it will create a profile if none exists,
    or update the existing profile.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    profile = service.get_or_create_parent_profile(current_user.id)

    # Update with provided data
    update_dict = profile_data.model_dump(exclude_unset=True)
    if update_dict:
        profile = service.update_parent_profile(current_user.id, update_dict)

    return profile


# ============================================================================
# STUDENT LINKING ENDPOINTS
# ============================================================================


@router.get("/students", response_model=List[LinkedStudentResponse])
async def get_linked_students(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all students linked to the current parent account.

    Returns a list of linked students with basic stats.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    students = service.get_linked_students(current_user.id)
    return students


@router.post("/students/link", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def link_student(
    request: LinkStudentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Link a student to the parent account.

    Requires the student's email address. The link will be created with the
    specified relationship type and access level.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)

    try:
        link = service.link_student(
            parent_user_id=current_user.id,
            student_email=request.student_email,
            relationship_type=request.relationship_type,
            access_level=request.access_level,
        )
        return MessageResponse(
            message=f"Student successfully linked to your account",
            success=True,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/students/{student_id}", response_model=MessageResponse)
async def unlink_student(
    student_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Unlink a student from the parent account.

    This will set the link status to inactive, preserving historical data.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    success = service.unlink_student(current_user.id, student_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student link not found",
        )

    return MessageResponse(
        message="Student successfully unlinked from your account",
        success=True,
    )


# ============================================================================
# CHILD MONITORING ENDPOINTS
# ============================================================================


@router.get("/students/{student_id}/dashboard", response_model=ChildDetailResponse)
async def get_child_dashboard(
    student_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive dashboard data for a specific child.

    Includes stats, subjects, recent sessions, and weekly progress.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)

    try:
        dashboard = service.get_child_detail(current_user.id, student_id)
        return dashboard
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get("/students/{student_id}/subjects", response_model=List[ChildSubjectPerformance])
async def get_child_subjects(
    student_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get subject performance data for a specific child.

    Returns detailed performance metrics for each enrolled subject.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)

    try:
        subjects = service.get_child_subjects(current_user.id, student_id)
        return subjects
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.get("/students/{student_id}/sessions", response_model=List[ChildPracticeSession])
async def get_child_sessions(
    student_id: UUID,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get practice session history for a specific child.

    Returns a list of completed practice sessions with performance data.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)

    try:
        sessions = service.get_child_sessions(current_user.id, student_id, limit=limit)
        return sessions
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============================================================================
# OVERVIEW AND INSIGHTS ENDPOINTS
# ============================================================================


@router.get("/overview", response_model=ParentOverviewResponse)
async def get_parent_overview(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get aggregated overview of all linked children.

    Includes summary stats for all children, aggregated metrics,
    and recent alerts.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    overview = service.get_parent_overview(current_user.id)
    return overview


@router.get("/insights", response_model=ParentInsightsResponse)
async def get_parent_insights(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get AI-generated insights and recommendations for parents.

    Provides actionable insights based on children's performance patterns.
    """
    if current_user.role != "parent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents can access this endpoint",
        )

    service = ParentService(db)
    insights = service.generate_insights(current_user.id)

    from datetime import datetime
    return ParentInsightsResponse(
        insights=insights,
        generated_at=datetime.now(),
    )
