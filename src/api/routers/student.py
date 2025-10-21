"""Student dashboard router - handles student profile and dashboard endpoints."""

from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ...core.auth_dependencies import get_current_active_user
from ...core.database import get_db
from ...core.student_service import StudentService
from ...models.db_models import APSubject, PracticeSession, StudentEnrollment, User
from ...models.student_schemas import (
    APSubjectResponse,
    DashboardDataResponse,
    DashboardStatsResponse,
    OverallProgressResponse,
    PracticeSessionCreate,
    PracticeSessionResponse,
    PracticeSessionUpdate,
    RecentActivityItem,
    RecommendationItem,
    StudentEnrollmentCreate,
    StudentEnrollmentResponse,
    StudentProfileCreate,
    StudentProfileResponse,
    StudentProfileUpdate,
    SubjectProgressItem,
    WeeklyProgressData,
)

router = APIRouter()


# ============================================================================
# STUDENT PROFILE ENDPOINTS
# ============================================================================


@router.get("/profile", response_model=StudentProfileResponse)
async def get_student_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get the current student's profile.

    Returns profile information including performance metrics and study stats.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    profile = service.get_or_create_student_profile(current_user.id)
    return profile


@router.put("/profile", response_model=StudentProfileResponse)
async def update_student_profile(
    profile_data: StudentProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Update the current student's profile.

    Allows updating grade level, study goals, preferences, etc.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    update_dict = profile_data.model_dump(exclude_unset=True)
    profile = service.update_student_profile(current_user.id, update_dict)
    return profile


@router.post("/profile", response_model=StudentProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_student_profile(
    profile_data: StudentProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Create or update student profile.

    This endpoint is idempotent - it will create a profile if none exists,
    or update the existing profile.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    profile_dict = profile_data.model_dump(exclude_unset=True)
    profile = service.update_student_profile(current_user.id, profile_dict)
    return profile


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================


@router.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get complete dashboard data for the student.

    Returns:
    - Overall statistics
    - Weekly progress data
    - Enrolled subjects with progress
    - Recent activity
    - Personalized recommendations
    - Profile information
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)

    # Get all dashboard components
    stats = service.get_dashboard_stats(current_user.id)
    weekly_progress = service.get_weekly_progress(current_user.id)
    recent_activity = service.get_recent_activity(current_user.id, limit=10)
    recommendations = service.get_recommendations(current_user.id)
    profile = service.get_or_create_student_profile(current_user.id)

    # Get enrolled subjects with details
    enrollments = (
        db.query(StudentEnrollment)
        .options(joinedload(StudentEnrollment.subject))
        .filter(StudentEnrollment.student_id == profile.id)
        .all()
    )

    enrolled_subjects = [
        SubjectProgressItem(
            subject=enrollment.subject,
            enrollment=enrollment,
        )
        for enrollment in enrollments
    ]

    return DashboardDataResponse(
        stats=stats,
        weekly_progress=weekly_progress,
        enrolled_subjects=enrolled_subjects,
        recent_activity=recent_activity,
        recommendations=recommendations,
        profile=profile,
    )


@router.get("/statistics", response_model=DashboardStatsResponse)
async def get_student_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed performance statistics for the student.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    return service.get_dashboard_stats(current_user.id)


@router.get("/progress", response_model=OverallProgressResponse)
async def get_overall_progress(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive progress metrics for the student.

    Includes detailed analytics across all subjects and time periods.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    return service.get_overall_progress(current_user.id)


@router.get("/recommendations", response_model=List[RecommendationItem])
async def get_study_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized study recommendations.

    Uses AI agents and performance data to suggest focus areas,
    practice opportunities, and study strategies.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    return service.get_recommendations(current_user.id)


@router.get("/recent-activity", response_model=List[RecentActivityItem])
async def get_recent_activity(
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get recent practice sessions.

    Returns the most recent completed practice sessions with performance data.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    return service.get_recent_activity(current_user.id, limit=min(limit, 50))


# ============================================================================
# SUBJECT ENROLLMENT ENDPOINTS
# ============================================================================


@router.get("/enrolled-subjects", response_model=List[StudentEnrollmentResponse])
async def get_enrolled_subjects(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get all subjects the student is enrolled in.

    Returns enrollment details including progress and performance metrics.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    enrollments = service.get_enrolled_subjects(current_user.id)
    return enrollments


@router.post("/enroll-subject", response_model=StudentEnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_in_subject(
    enrollment_data: StudentEnrollmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Enroll in an AP subject.

    Adds the subject to the student's enrolled courses.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)

    try:
        enrollment = service.enroll_in_subject(
            current_user.id,
            enrollment_data.subject_id,
            enrollment_data.target_exam_date,
        )
        db.refresh(enrollment)

        # Load the subject relationship
        enrollment = (
            db.query(StudentEnrollment)
            .options(joinedload(StudentEnrollment.subject))
            .filter(StudentEnrollment.id == enrollment.id)
            .first()
        )

        return enrollment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/enroll-subject/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unenroll_from_subject(
    subject_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Unenroll from an AP subject.

    Removes the subject from the student's enrolled courses.
    Note: This will also delete all related practice session data.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    success = service.unenroll_from_subject(current_user.id, subject_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )


# ============================================================================
# PRACTICE SESSION ENDPOINTS
# ============================================================================


@router.post("/practice-sessions", response_model=PracticeSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_practice_session(
    session_data: PracticeSessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Start a new practice session.

    Creates a practice session record with the specified subject and parameters.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    profile = service.get_or_create_student_profile(current_user.id)

    # Verify subject exists and student is enrolled
    enrollment = (
        db.query(StudentEnrollment)
        .filter(
            StudentEnrollment.student_id == profile.id,
            StudentEnrollment.subject_id == session_data.subject_id,
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be enrolled in this subject to start a practice session",
        )

    # Create practice session
    session = PracticeSession(
        student_id=profile.id,
        subject_id=session_data.subject_id,
        session_type=session_data.session_type,
        topics_covered=session_data.topics_covered,
        difficulty_level=session_data.difficulty_level,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Load subject relationship
    session = (
        db.query(PracticeSession)
        .options(joinedload(PracticeSession.subject))
        .filter(PracticeSession.id == session.id)
        .first()
    )

    return session


@router.put("/practice-sessions/{session_id}", response_model=PracticeSessionResponse)
async def complete_practice_session(
    session_id: UUID,
    session_update: PracticeSessionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Complete a practice session.

    Updates the session with completion data and performance metrics.
    This also updates the student's overall statistics.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    profile = service.get_or_create_student_profile(current_user.id)

    # Get session and verify ownership
    session = (
        db.query(PracticeSession)
        .filter(
            PracticeSession.id == session_id,
            PracticeSession.student_id == profile.id,
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice session not found",
        )

    # Update session
    session.completed_at = session_update.completed_at
    session.duration_minutes = session_update.duration_minutes
    session.questions_attempted = session_update.questions_attempted
    session.questions_correct = session_update.questions_correct

    # Calculate accuracy
    if session.questions_attempted > 0:
        session.accuracy_rate = (
            session.questions_correct / session.questions_attempted
        ) * 100

    if session_update.metadata:
        session.metadata = session_update.metadata

    db.commit()

    # Update profile and enrollment stats
    service.update_profile_stats_from_session(session)

    db.refresh(session)

    # Load subject relationship
    session = (
        db.query(PracticeSession)
        .options(joinedload(PracticeSession.subject))
        .filter(PracticeSession.id == session.id)
        .first()
    )

    return session


@router.get("/practice-sessions", response_model=List[PracticeSessionResponse])
async def get_practice_sessions(
    subject_id: UUID = None,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get practice sessions.

    Optionally filter by subject. Returns most recent sessions first.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    service = StudentService(db)
    profile = service.get_or_create_student_profile(current_user.id)

    query = (
        db.query(PracticeSession)
        .options(joinedload(PracticeSession.subject))
        .filter(PracticeSession.student_id == profile.id)
        .order_by(PracticeSession.started_at.desc())
    )

    if subject_id:
        query = query.filter(PracticeSession.subject_id == subject_id)

    sessions = query.limit(min(limit, 100)).all()
    return sessions
