"""Pydantic schemas for practice session and question endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# QUESTION SCHEMAS
# ============================================================================


class QuestionOption(BaseModel):
    """Multiple choice option."""

    index: int = Field(..., description="Option index (0-3)")
    text: str = Field(..., description="Option text")


class QuestionData(BaseModel):
    """Question data for practice session."""

    id: UUID = Field(..., description="Question variant ID")
    stimulus: str = Field(..., description="Question text/stem")
    options: List[str] = Field(..., description="Four answer choices")
    difficulty_estimate: Optional[Decimal] = Field(None, description="Estimated difficulty 0-1")
    topic_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class QuestionAnswer(BaseModel):
    """Student answer to a question."""

    question_id: UUID
    selected_option: int = Field(..., ge=0, le=3, description="Selected option index (0-3)")
    time_spent_ms: int = Field(..., ge=0, description="Time spent on question in milliseconds")
    is_flagged: bool = Field(default=False, description="Whether question was flagged for review")


class QuestionResult(BaseModel):
    """Result for a single question."""

    question_id: UUID
    stimulus: str
    options: List[str]
    selected_option: int
    correct_option: int
    is_correct: bool
    explanation: Optional[str] = None
    solution: Optional[str] = None
    time_spent_ms: int
    was_flagged: bool
    topic_name: Optional[str] = None
    difficulty: Optional[Decimal] = None


# ============================================================================
# SESSION CONFIGURATION SCHEMAS
# ============================================================================


class PracticeSessionConfig(BaseModel):
    """Configuration for starting a practice session."""

    subject_id: UUID = Field(..., description="AP Subject ID")
    question_count: int = Field(..., ge=5, le=50, description="Number of questions (5-50)")
    topics: Optional[List[str]] = Field(default=None, description="Specific topics to practice")
    difficulty_level: Optional[int] = Field(None, ge=1, le=5, description="Target difficulty 1-5")
    enable_timer: bool = Field(default=False, description="Enable timer for session")
    time_limit_minutes: Optional[int] = Field(None, ge=5, le=180, description="Time limit in minutes")
    session_type: str = Field(default="practice", description="Session type: practice/quiz/mock_exam")


class PracticeSessionStart(BaseModel):
    """Response when starting a practice session."""

    session_id: UUID
    subject_id: UUID
    subject_name: str
    question_count: int
    questions: List[QuestionData]
    config: PracticeSessionConfig
    started_at: datetime


# ============================================================================
# SESSION STATE SCHEMAS
# ============================================================================


class SessionAnswerSubmission(BaseModel):
    """Submit answer during practice session."""

    question_id: UUID
    selected_option: int = Field(..., ge=0, le=3)
    time_spent_ms: int = Field(..., ge=0)
    is_flagged: bool = False


class SessionProgressResponse(BaseModel):
    """Current session progress."""

    session_id: UUID
    questions_total: int
    questions_answered: int
    questions_flagged: int
    time_elapsed_ms: int
    answers: List[QuestionAnswer]


class SessionPauseResponse(BaseModel):
    """Response when pausing a session."""

    session_id: UUID
    paused_at: datetime
    progress: SessionProgressResponse


class SessionResumeResponse(BaseModel):
    """Response when resuming a session."""

    session_id: UUID
    resumed_at: datetime
    questions: List[QuestionData]
    progress: SessionProgressResponse


# ============================================================================
# SESSION COMPLETION SCHEMAS
# ============================================================================


class SessionCompletionRequest(BaseModel):
    """Request to complete a practice session."""

    answers: List[QuestionAnswer] = Field(..., description="All question answers")
    time_elapsed_minutes: int = Field(..., ge=0, description="Total time elapsed")


class TopicPerformance(BaseModel):
    """Performance breakdown by topic."""

    topic_name: str
    questions_count: int
    correct_count: int
    accuracy_percentage: Decimal
    avg_time_ms: int


class PerformanceComparison(BaseModel):
    """Performance comparison with previous sessions."""

    metric: str = Field(..., description="Metric name (accuracy/speed/etc)")
    current_value: Decimal
    previous_avg: Decimal
    change_percentage: Decimal
    trend: str = Field(..., description="up/down/stable")


class StudyRecommendation(BaseModel):
    """Study recommendation based on session results."""

    type: str = Field(..., description="Recommendation type")
    priority: int = Field(..., ge=1, le=5, description="Priority 1-5")
    title: str
    description: str
    topic: Optional[str] = None


class SessionResults(BaseModel):
    """Complete session results."""

    session_id: UUID
    subject_name: str
    session_type: str
    started_at: datetime
    completed_at: datetime
    duration_minutes: int

    # Overall performance
    questions_total: int
    questions_correct: int
    accuracy_percentage: Decimal
    avg_time_per_question_ms: int

    # Detailed results
    question_results: List[QuestionResult]

    # Analytics
    topic_performance: List[TopicPerformance]
    performance_comparison: List[PerformanceComparison]
    study_recommendations: List[StudyRecommendation]

    # Stats updates
    new_streak: int
    points_earned: int
    rank_change: Optional[str] = None


# ============================================================================
# QUESTION GENERATION SCHEMAS
# ============================================================================


class QuestionGenerationRequest(BaseModel):
    """Request to generate questions."""

    subject_id: UUID
    count: int = Field(..., ge=1, le=50)
    topics: Optional[List[str]] = None
    difficulty_range: Optional[List[float]] = Field(None, description="[min, max] difficulty 0-1")
    exclude_question_ids: Optional[List[UUID]] = Field(None, description="Recently seen questions to exclude")


class QuestionGenerationResponse(BaseModel):
    """Response with generated questions."""

    questions: List[QuestionData]
    count: int
    generation_time_ms: int
