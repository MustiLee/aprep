"""Pydantic schemas for parent dashboard endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ============================================================================
# PARENT PROFILE SCHEMAS
# ============================================================================


class ParentProfileBase(BaseModel):
    """Base schema for Parent Profile."""

    phone_number: Optional[str] = Field(None, max_length=20, description="Parent phone number")
    notification_email: bool = Field(default=True, description="Email notifications enabled")
    notification_push: bool = Field(default=True, description="Push notifications enabled")
    notification_frequency: str = Field(default="daily", description="Notification frequency: daily, weekly, monthly")
    report_frequency: str = Field(default="weekly", description="Report frequency: weekly, monthly")

    @property
    def notification_preferences(self) -> dict:
        """Get notification preferences as dict."""
        return {
            "email": self.notification_email,
            "push": self.notification_push,
            "frequency": self.notification_frequency
        }


class ParentProfileCreate(ParentProfileBase):
    """Schema for creating a parent profile."""

    pass


class ParentProfileUpdate(BaseModel):
    """Schema for updating a parent profile."""

    phone_number: Optional[str] = Field(None, max_length=20)
    notification_email: Optional[bool] = None
    notification_push: Optional[bool] = None
    notification_frequency: Optional[str] = None
    report_frequency: Optional[str] = None


class ParentProfileResponse(ParentProfileBase):
    """Response schema for Parent Profile."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# PARENT-STUDENT LINK SCHEMAS
# ============================================================================


class ParentStudentLinkBase(BaseModel):
    """Base schema for Parent-Student Link."""

    relationship_type: str = Field(..., description="Relationship: mother, father, guardian, tutor")
    access_level: str = Field(default="full", description="Access level: full, limited")


class LinkStudentRequest(BaseModel):
    """Request to link a student to parent account."""

    student_email: EmailStr = Field(..., description="Student's email address")
    relationship_type: str = Field(..., description="Relationship type: mother, father, guardian, tutor")
    access_level: str = Field(default="full", description="Access level: full, limited")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "student_email": "student@example.com",
                    "relationship_type": "mother",
                    "access_level": "full"
                }
            ]
        }
    }


class UnlinkStudentRequest(BaseModel):
    """Request to unlink a student from parent account."""

    student_id: UUID = Field(..., description="Student profile ID to unlink")


class LinkedStudentResponse(BaseModel):
    """Response schema for a linked student."""

    id: UUID
    parent_id: UUID
    student_id: UUID
    student_user_id: UUID
    student_name: str
    student_email: str
    relationship_type: str
    access_level: str
    linked_at: datetime

    # Quick stats
    study_streak: int
    overall_accuracy: Decimal
    total_study_time_minutes: int
    last_practice_date: Optional[datetime]

    class Config:
        from_attributes = True


# ============================================================================
# CHILD DASHBOARD SCHEMAS
# ============================================================================


class ChildDashboardStats(BaseModel):
    """Dashboard statistics for a child."""

    study_streak: int
    longest_streak: int
    total_questions: int
    accuracy_rate: Decimal
    total_study_time_minutes: int
    total_study_time_hours: float
    topics_mastered: int
    enrollments_count: int
    last_practice_date: Optional[datetime]


class ChildSubjectPerformance(BaseModel):
    """Subject performance data for a child."""

    subject_id: UUID
    subject_name: str
    subject_code: str
    progress_percentage: Decimal
    accuracy_rate: Decimal
    questions_answered: int
    questions_correct: int
    study_time_minutes: int
    practice_sessions_completed: int
    last_practice_date: Optional[datetime]


class ChildPracticeSession(BaseModel):
    """Practice session data for a child."""

    id: UUID
    subject_name: str
    subject_code: str
    session_type: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_minutes: Optional[int]
    questions_attempted: int
    questions_correct: int
    accuracy_rate: Decimal


class ChildWeeklyProgress(BaseModel):
    """Weekly progress data for a child."""

    date: str
    questions_answered: int
    study_minutes: int
    accuracy: Decimal


class ChildDetailResponse(BaseModel):
    """Detailed view of a child's performance."""

    student_id: UUID
    student_name: str
    student_email: str
    relationship_type: str
    stats: ChildDashboardStats
    subjects: List[ChildSubjectPerformance]
    recent_sessions: List[ChildPracticeSession]
    weekly_progress: List[ChildWeeklyProgress]


class ChildAlert(BaseModel):
    """Alert notification for a child."""

    type: str  # 'low_performance', 'missed_study', 'achievement', 'goal_reached'
    severity: str  # 'info', 'warning', 'critical'
    title: str
    message: str
    student_id: UUID
    student_name: str
    subject_name: Optional[str] = None
    created_at: datetime


# ============================================================================
# PARENT OVERVIEW SCHEMAS
# ============================================================================


class ChildSummary(BaseModel):
    """Summary data for a child on parent overview."""

    student_id: UUID
    student_name: str
    student_email: str
    relationship_type: str
    study_streak: int
    accuracy_rate: Decimal
    total_study_time_minutes: int
    enrollments_count: int
    last_practice_date: Optional[datetime]
    recent_activity_count: int


class ParentOverviewResponse(BaseModel):
    """Aggregated overview of all children."""

    children: List[ChildSummary]
    total_children: int
    aggregated_stats: dict  # Combined stats across all children
    recent_alerts: List[ChildAlert]
    total_active_today: int  # Number of children who studied today


# ============================================================================
# PROGRESS REPORT SCHEMAS
# ============================================================================


class ProgressReportRequest(BaseModel):
    """Request to generate a progress report."""

    student_id: UUID
    period: str = Field(default="week", description="Report period: week, month, quarter")
    format: str = Field(default="pdf", description="Report format: pdf, email")


class ProgressReportResponse(BaseModel):
    """Response for progress report generation."""

    report_id: str
    student_id: UUID
    student_name: str
    period: str
    generated_at: datetime
    download_url: Optional[str] = None
    message: str = "Report generated successfully"


# ============================================================================
# PARENT INSIGHT SCHEMAS
# ============================================================================


class ParentInsight(BaseModel):
    """AI-generated insight for parents."""

    type: str  # 'performance', 'recommendation', 'milestone', 'concern'
    title: str
    description: str
    student_id: Optional[UUID] = None
    student_name: Optional[str] = None
    subject_name: Optional[str] = None
    priority: int  # 1-5, higher is more important
    actionable: bool = False  # Can parent take action on this
    action_text: Optional[str] = None  # "Review weak topics with your child"


class ParentInsightsResponse(BaseModel):
    """Collection of insights for parents."""

    insights: List[ParentInsight]
    generated_at: datetime
