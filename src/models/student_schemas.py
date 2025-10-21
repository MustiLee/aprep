"""Pydantic schemas for student dashboard endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# AP SUBJECT SCHEMAS
# ============================================================================


class APSubjectBase(BaseModel):
    """Base schema for AP Subject."""

    name: str = Field(..., description="Subject name (e.g., 'AP Calculus BC')")
    code: str = Field(..., description="Subject code (e.g., 'CALC_BC')")
    description: Optional[str] = None
    difficulty_level: int = Field(..., ge=1, le=5, description="Difficulty level 1-5")
    exam_format: Optional[dict] = None
    topics_count: int = 0


class APSubjectResponse(APSubjectBase):
    """Response schema for AP Subject."""

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# STUDENT PROFILE SCHEMAS
# ============================================================================


class StudentProfileBase(BaseModel):
    """Base schema for Student Profile."""

    grade_level: Optional[int] = Field(None, ge=9, le=12, description="Grade level 9-12")
    target_ap_exams: Optional[List[str]] = Field(default_factory=list, description="List of AP exam codes")
    study_goals: Optional[str] = None
    preferred_study_time: Optional[str] = None
    daily_goal_minutes: int = Field(default=30, ge=0, description="Daily study goal in minutes")


class StudentProfileCreate(StudentProfileBase):
    """Schema for creating a student profile."""

    pass


class StudentProfileUpdate(BaseModel):
    """Schema for updating a student profile."""

    grade_level: Optional[int] = Field(None, ge=9, le=12)
    target_ap_exams: Optional[List[str]] = None
    study_goals: Optional[str] = None
    preferred_study_time: Optional[str] = None
    daily_goal_minutes: Optional[int] = Field(None, ge=0)


class StudentProfileResponse(StudentProfileBase):
    """Response schema for Student Profile."""

    id: UUID
    user_id: UUID
    study_streak: int
    longest_streak: int
    total_questions_answered: int
    total_questions_correct: int
    total_study_time_minutes: int
    overall_accuracy: Decimal
    topics_mastered_count: int
    last_practice_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# STUDENT ENROLLMENT SCHEMAS
# ============================================================================


class StudentEnrollmentBase(BaseModel):
    """Base schema for Student Enrollment."""

    subject_id: UUID
    target_exam_date: Optional[datetime] = None


class StudentEnrollmentCreate(StudentEnrollmentBase):
    """Schema for enrolling in a subject."""

    pass


class StudentEnrollmentResponse(BaseModel):
    """Response schema for Student Enrollment."""

    id: UUID
    student_id: UUID
    subject_id: UUID
    enrollment_date: datetime
    target_exam_date: Optional[datetime]
    progress_percentage: Decimal
    topics_mastered: int
    total_topics: int
    questions_answered: int
    questions_correct: int
    accuracy_rate: Decimal
    study_time_minutes: int
    practice_sessions_completed: int
    last_practice_date: Optional[datetime]
    subject: APSubjectResponse

    class Config:
        from_attributes = True


# ============================================================================
# PRACTICE SESSION SCHEMAS
# ============================================================================


class PracticeSessionBase(BaseModel):
    """Base schema for Practice Session."""

    subject_id: UUID
    session_type: str = "practice"
    topics_covered: Optional[List[str]] = Field(default_factory=list)
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)


class PracticeSessionCreate(PracticeSessionBase):
    """Schema for creating a practice session."""

    pass


class PracticeSessionUpdate(BaseModel):
    """Schema for updating a practice session (when completed)."""

    completed_at: datetime
    duration_minutes: int
    questions_attempted: int
    questions_correct: int
    metadata: Optional[dict] = None


class PracticeSessionResponse(BaseModel):
    """Response schema for Practice Session."""

    id: UUID
    student_id: UUID
    subject_id: UUID
    session_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_minutes: Optional[int]
    questions_attempted: int
    questions_correct: int
    accuracy_rate: Decimal
    topics_covered: Optional[List[str]]
    difficulty_level: Optional[int]
    subject: Optional[APSubjectResponse] = None

    class Config:
        from_attributes = True


# ============================================================================
# DASHBOARD DATA SCHEMAS
# ============================================================================


class DashboardStatsResponse(BaseModel):
    """Response schema for dashboard statistics."""

    study_streak: int
    longest_streak: int
    total_questions: int
    accuracy_rate: Decimal
    total_study_time_minutes: int
    topics_mastered: int
    enrollments_count: int


class WeeklyProgressData(BaseModel):
    """Weekly progress data for charts."""

    date: str  # Date in YYYY-MM-DD format
    questions_answered: int
    study_minutes: int
    accuracy: Decimal


class RecentActivityItem(BaseModel):
    """Recent activity item."""

    id: UUID
    subject_name: str
    subject_code: str
    session_type: str
    started_at: datetime
    duration_minutes: Optional[int]
    questions_attempted: int
    questions_correct: int
    accuracy_rate: Decimal


class SubjectProgressItem(BaseModel):
    """Subject progress item for dashboard."""

    subject: APSubjectResponse
    enrollment: StudentEnrollmentResponse


class RecommendationItem(BaseModel):
    """Study recommendation item."""

    type: str  # 'weak_topic', 'practice_more', 'new_subject', etc.
    title: str
    description: str
    subject_id: Optional[UUID] = None
    subject_name: Optional[str] = None
    priority: int  # 1-5, higher is more important


class DashboardDataResponse(BaseModel):
    """Complete dashboard data response."""

    stats: DashboardStatsResponse
    weekly_progress: List[WeeklyProgressData]
    enrolled_subjects: List[SubjectProgressItem]
    recent_activity: List[RecentActivityItem]
    recommendations: List[RecommendationItem]
    profile: StudentProfileResponse


# ============================================================================
# PROGRESS SCHEMAS
# ============================================================================


class OverallProgressResponse(BaseModel):
    """Overall student progress metrics."""

    total_study_days: int
    current_streak: int
    longest_streak: int
    total_questions_answered: int
    total_questions_correct: int
    overall_accuracy: Decimal
    total_study_time_minutes: int
    total_study_time_hours: float
    average_session_duration: int  # minutes
    topics_mastered_count: int
    enrolled_subjects_count: int
    completed_sessions_count: int
    this_week_questions: int
    this_week_study_minutes: int
    last_practice_date: Optional[datetime]


class SubjectProgressResponse(BaseModel):
    """Subject-specific progress metrics."""

    subject: APSubjectResponse
    enrollment: StudentEnrollmentResponse
    recent_sessions: List[PracticeSessionResponse]
    performance_trend: List[dict]  # Time-series performance data
