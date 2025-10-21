"""SQLAlchemy database models for PostgreSQL.

These models map to the PostgreSQL schema defined in database_schema.sql.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


# ============================================================================
# AUTHENTICATION MODELS
# ============================================================================


class User(Base):
    """User model for authentication and user management."""

    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Basic info
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)

    # User type: 'student' or 'parent'
    role = Column(String(50), nullable=False, index=True)

    # Email verification
    email_verified = Column(Boolean, default=False, index=True)
    email_verification_token = Column(String(255))
    email_verification_sent_at = Column(DateTime(timezone=True))

    # Password reset
    password_reset_token = Column(String(255))
    password_reset_expires_at = Column(DateTime(timezone=True))

    # Refresh tokens for JWT
    refresh_token = Column(String(512))
    refresh_token_expires_at = Column(DateTime(timezone=True))

    # Account status
    is_active = Column(Boolean, default=True, index=True)
    is_locked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at = Column(DateTime(timezone=True))

    # Additional metadata
    user_metadata = Column(JSON)  # For storing additional user preferences, settings, etc.

    __table_args__ = (
        CheckConstraint("role IN ('student', 'parent')"),
    )


# ============================================================================
# CORE MODELS
# ============================================================================


class Course(Base):
    """Course model (AP Calculus BC, AP Statistics, etc.)."""

    __tablename__ = "courses"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(String(100), unique=True, nullable=False, index=True)
    course_name = Column(String(255), nullable=False)
    exam_type = Column(String(50))  # 'AP', 'SAT', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    units = relationship("Unit", back_populates="course", cascade="all, delete-orphan")
    templates = relationship(
        "Template", back_populates="course", cascade="all, delete-orphan"
    )


class Unit(Base):
    """Course unit model."""

    __tablename__ = "units"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(
        PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    unit_id = Column(String(100), nullable=False, index=True)
    unit_number = Column(Integer)
    unit_name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("course_id", "unit_id"),)

    # Relationships
    course = relationship("Course", back_populates="units")
    topics = relationship("Topic", back_populates="unit", cascade="all, delete-orphan")


class Topic(Base):
    """Topic model within a unit."""

    __tablename__ = "topics"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    unit_id = Column(
        PGUUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), index=True
    )
    topic_id = Column(String(100), nullable=False, index=True)
    topic_name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("unit_id", "topic_id"),)

    # Relationships
    unit = relationship("Unit", back_populates="topics")
    learning_objectives = relationship(
        "LearningObjective", back_populates="topic", cascade="all, delete-orphan"
    )
    templates = relationship("Template", back_populates="topic")


class LearningObjective(Base):
    """Learning objective model."""

    __tablename__ = "learning_objectives"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    topic_id = Column(
        PGUUID(as_uuid=True), ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    lo_code = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=False)
    cognitive_level = Column(String(50))  # 'remember', 'understand', 'apply', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("topic_id", "lo_code"),)

    # Relationships
    topic = relationship("Topic", back_populates="learning_objectives")


# ============================================================================
# TEMPLATE MODELS
# ============================================================================


class Template(Base):
    """Question template model."""

    __tablename__ = "templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(String(255), unique=True, nullable=False, index=True)
    course_id = Column(
        PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    topic_id = Column(
        PGUUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )

    # Metadata
    created_by = Column(String(100), default="system")
    task_id = Column(String(255))
    version = Column(Integer, default=1)
    status = Column(String(50), default="active", index=True)  # 'active', 'deprecated'

    # Template content
    stem = Column(Text, nullable=False)
    solution_template = Column(Text)
    explanation_template = Column(Text)

    # Configuration
    difficulty_range = Column(JSON)  # [min, max]
    calculator_policy = Column(String(50))
    time_estimate_seconds = Column(Integer)

    # Metadata
    tags = Column(ARRAY(Text))
    template_metadata = Column(JSON)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    course = relationship("Course", back_populates="templates")
    topic = relationship("Topic", back_populates="templates")
    parameters = relationship(
        "TemplateParameter", back_populates="template", cascade="all, delete-orphan"
    )
    distractor_rules = relationship(
        "DistractorRule", back_populates="template", cascade="all, delete-orphan"
    )
    variants = relationship(
        "Variant", back_populates="template", cascade="all, delete-orphan"
    )
    statistics = relationship(
        "TemplateStatistics",
        back_populates="template",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TemplateParameter(Base):
    """Template parameter model."""

    __tablename__ = "template_parameters"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        index=True,
    )
    param_name = Column(String(100), nullable=False)
    param_type = Column(String(50), nullable=False)  # 'enum', 'range', 'expression'
    definition = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("template_id", "param_name"),)

    # Relationships
    template = relationship("Template", back_populates="parameters")


class DistractorRule(Base):
    """Distractor rule model."""

    __tablename__ = "distractor_rules"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    template_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        index=True,
    )
    rule_id = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    generation_rule = Column(Text, nullable=False)
    misconception = Column(String(255))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("template_id", "rule_id"),)

    # Relationships
    template = relationship("Template", back_populates="distractor_rules")


# ============================================================================
# VARIANT MODELS
# ============================================================================


class Variant(Base):
    """Question variant model."""

    __tablename__ = "variants"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    variant_id = Column(String(255), unique=True, nullable=False, index=True)
    template_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        index=True,
    )

    # Content
    stimulus = Column(Text, nullable=False)
    options = Column(ARRAY(Text), nullable=False)
    answer_index = Column(Integer, nullable=False)
    solution = Column(Text, nullable=False)
    explanation = Column(Text)

    __table_args__ = (
        CheckConstraint("answer_index >= 0 AND answer_index < 4"),
        CheckConstraint("array_length(options, 1) = 4"),
    )

    # Parameters
    parameter_values = Column(JSON, nullable=False)
    seed = Column(Integer)

    # Metadata
    difficulty_estimate = Column(Numeric(3, 2), index=True)
    discrimination_estimate = Column(Numeric(3, 2))
    guessing_estimate = Column(Numeric(3, 2))

    # Verification
    verification_status = Column(String(50), index=True)  # 'pending', 'pass', 'fail'
    verification_confidence = Column(Numeric(3, 2))
    verification_timestamp = Column(DateTime(timezone=True))
    verification_result = Column(JSON)

    # Usage tracking
    times_used = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    template = relationship("Template", back_populates="variants")
    verification_logs = relationship(
        "VerificationLog", back_populates="variant", cascade="all, delete-orphan"
    )
    responses = relationship(
        "Response", back_populates="variant", cascade="all, delete-orphan"
    )
    statistics = relationship(
        "VariantStatistics",
        back_populates="variant",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================================
# VERIFICATION MODELS
# ============================================================================


class VerificationLog(Base):
    """Verification log model (detailed results)."""

    __tablename__ = "verification_logs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    variant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        index=True,
    )

    verification_status = Column(String(50), nullable=False, index=True)

    # Method results
    symbolic_result = Column(JSON)
    numerical_result = Column(JSON)
    claude_result = Column(JSON)

    # Consensus
    consensus = Column(JSON)

    # Distractor analysis
    distractor_analysis = Column(JSON)

    # Issues and warnings
    issues = Column(JSON)
    warnings = Column(JSON)

    # Performance
    duration_ms = Column(Integer)
    cost_usd = Column(Numeric(10, 6))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    variant = relationship("Variant", back_populates="verification_logs")


# ============================================================================
# USAGE MODELS
# ============================================================================


class TestSession(Base):
    """Test session model (student practice/exam)."""

    __tablename__ = "test_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(String(255), unique=True, nullable=False, index=True)

    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    test_type = Column(String(50))  # 'practice', 'diagnostic', 'mock_exam'
    course_id = Column(PGUUID(as_uuid=True), ForeignKey("courses.id"), index=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)

    session_metadata = Column(JSON)

    # Relationships
    responses = relationship(
        "Response", back_populates="session", cascade="all, delete-orphan"
    )


class Response(Base):
    """Student response model."""

    __tablename__ = "responses"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("test_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    variant_id = Column(
        PGUUID(as_uuid=True), ForeignKey("variants.id"), index=True
    )

    selected_option = Column(Integer)
    is_correct = Column(Boolean, index=True)
    response_time_ms = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("selected_option >= 0 AND selected_option < 4"),
    )

    # Relationships
    session = relationship("TestSession", back_populates="responses")
    variant = relationship("Variant", back_populates="responses")


# ============================================================================
# ANALYTICS MODELS
# ============================================================================


class VariantStatistics(Base):
    """Variant statistics model (aggregated)."""

    __tablename__ = "variant_statistics"

    variant_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("variants.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Usage stats
    times_administered = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    times_incorrect = Column(Integer, default=0)

    # Performance metrics
    p_value = Column(Numeric(5, 4))  # Proportion correct
    point_biserial = Column(Numeric(5, 4))  # Discrimination

    # Option analysis
    option_frequencies = Column(JSON)  # Frequency of each option

    # IRT parameters
    irt_difficulty = Column(Numeric(5, 3))  # b parameter
    irt_discrimination = Column(Numeric(5, 3))  # a parameter
    irt_guessing = Column(Numeric(5, 3))  # c parameter
    irt_last_calibrated = Column(DateTime(timezone=True))

    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    variant = relationship("Variant", back_populates="statistics")


class TemplateStatistics(Base):
    """Template statistics model (aggregated)."""

    __tablename__ = "template_statistics"

    template_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("templates.id", ondelete="CASCADE"),
        primary_key=True,
    )

    total_variants = Column(Integer, default=0)
    verified_variants = Column(Integer, default=0)

    avg_difficulty = Column(Numeric(5, 4))
    avg_discrimination = Column(Numeric(5, 4))

    times_used = Column(Integer, default=0)

    last_updated = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    template = relationship("Template", back_populates="statistics")


# ============================================================================
# WORKFLOW MODELS
# ============================================================================


class Workflow(Base):
    """Workflow model (orchestrator tracking)."""

    __tablename__ = "workflows"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(String(255), unique=True, nullable=False, index=True)

    workflow_type = Column(String(100), index=True)
    status = Column(String(50), index=True)  # 'pending', 'running', 'completed'

    input_data = Column(JSON)
    output_data = Column(JSON)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)

    error_message = Column(Text)

    # Relationships
    agent_tasks = relationship(
        "AgentTask", back_populates="workflow", cascade="all, delete-orphan"
    )


class AgentTask(Base):
    """Agent task model (individual agent execution)."""

    __tablename__ = "agent_tasks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        index=True,
    )

    agent_name = Column(String(100), nullable=False, index=True)
    stage_number = Column(Integer)

    status = Column(String(50), index=True)
    input_data = Column(JSON)
    output_data = Column(JSON)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)

    error_message = Column(Text)

    # Relationships
    workflow = relationship("Workflow", back_populates="agent_tasks")


# ============================================================================
# SYSTEM MODELS
# ============================================================================


class APIKey(Base):
    """API key model."""

    __tablename__ = "api_keys"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)

    name = Column(String(255))
    description = Column(Text)

    scopes = Column(ARRAY(Text))  # Permissions

    rate_limit_per_hour = Column(Integer, default=1000)

    is_active = Column(Boolean, default=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))


class AuditLog(Base):
    """Audit log model."""

    __tablename__ = "audit_log"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    action = Column(String(100), nullable=False)  # 'create', 'update', 'delete'
    resource_type = Column(String(100), index=True)  # 'template', 'variant', etc.
    resource_id = Column(PGUUID(as_uuid=True), index=True)

    user_id = Column(String(255))
    api_key_id = Column(PGUUID(as_uuid=True), ForeignKey("api_keys.id"))

    changes = Column(JSON)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# ============================================================================
# STUDENT DASHBOARD MODELS
# ============================================================================


class APSubject(Base):
    """AP Subject/Exam model."""

    __tablename__ = "ap_subjects"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)  # e.g., "AP Calculus BC"
    code = Column(String(100), nullable=False, unique=True, index=True)  # e.g., "CALC_BC"
    description = Column(Text)
    difficulty_level = Column(Integer)  # 1-5 scale
    is_active = Column(Boolean, default=True, index=True)

    # Additional metadata
    exam_format = Column(JSON)  # Structure of the exam (MCQ count, FRQ count, etc.)
    topics_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("difficulty_level >= 1 AND difficulty_level <= 5"),
    )

    # Relationships
    enrollments = relationship(
        "StudentEnrollment", back_populates="subject", cascade="all, delete-orphan"
    )
    practice_sessions = relationship(
        "PracticeSession", back_populates="subject", cascade="all, delete-orphan"
    )


class StudentProfile(Base):
    """Student profile model with performance tracking."""

    __tablename__ = "student_profiles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Profile information
    grade_level = Column(Integer)  # 9-12
    target_ap_exams = Column(ARRAY(Text))  # Array of AP exam codes
    study_goals = Column(Text)

    # Performance metrics
    study_streak = Column(Integer, default=0)  # Current consecutive days studied
    longest_streak = Column(Integer, default=0)
    total_questions_answered = Column(Integer, default=0)
    total_questions_correct = Column(Integer, default=0)
    total_study_time_minutes = Column(Integer, default=0)

    # Computed metrics (updated by triggers or application logic)
    overall_accuracy = Column(Numeric(5, 2), default=0.0)  # Percentage
    topics_mastered_count = Column(Integer, default=0)

    # Study preferences
    preferred_study_time = Column(String(50))  # 'morning', 'afternoon', 'evening'
    daily_goal_minutes = Column(Integer, default=30)

    # Last activity tracking
    last_practice_date = Column(DateTime(timezone=True))
    last_streak_update = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("grade_level >= 9 AND grade_level <= 12"),
        CheckConstraint("overall_accuracy >= 0 AND overall_accuracy <= 100"),
    )

    # Relationships
    user = relationship("User")
    enrollments = relationship(
        "StudentEnrollment", back_populates="student", cascade="all, delete-orphan"
    )
    practice_sessions = relationship(
        "PracticeSession", back_populates="student", cascade="all, delete-orphan"
    )


class StudentEnrollment(Base):
    """Student enrollment in AP subjects (many-to-many relationship)."""

    __tablename__ = "student_enrollments"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("ap_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Enrollment details
    enrollment_date = Column(DateTime(timezone=True), server_default=func.now())
    target_exam_date = Column(DateTime(timezone=True))

    # Progress tracking
    progress_percentage = Column(Numeric(5, 2), default=0.0)  # 0-100
    topics_mastered = Column(Integer, default=0)
    total_topics = Column(Integer, default=0)

    # Performance metrics for this subject
    questions_answered = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    accuracy_rate = Column(Numeric(5, 2), default=0.0)  # Percentage
    study_time_minutes = Column(Integer, default=0)

    # Practice session count
    practice_sessions_completed = Column(Integer, default=0)
    last_practice_date = Column(DateTime(timezone=True))

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id"),
        CheckConstraint("progress_percentage >= 0 AND progress_percentage <= 100"),
        CheckConstraint("accuracy_rate >= 0 AND accuracy_rate <= 100"),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="enrollments")
    subject = relationship("APSubject", back_populates="enrollments")


class PracticeSession(Base):
    """Practice session tracking for students."""

    __tablename__ = "practice_sessions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    student_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("ap_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session details
    session_type = Column(String(50), default="practice")  # 'practice', 'quiz', 'mock_exam'
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)

    # Performance
    questions_attempted = Column(Integer, default=0)
    questions_correct = Column(Integer, default=0)
    accuracy_rate = Column(Numeric(5, 2), default=0.0)

    # Content covered
    topics_covered = Column(ARRAY(Text))  # Array of topic names/IDs
    difficulty_level = Column(Integer)  # Average difficulty of questions

    # Additional metadata
    practice_metadata = Column(JSON)  # Can store question IDs, time per question, etc.

    __table_args__ = (
        CheckConstraint("accuracy_rate >= 0 AND accuracy_rate <= 100"),
        CheckConstraint("difficulty_level >= 1 AND difficulty_level <= 5"),
    )

    # Relationships
    student = relationship("StudentProfile", back_populates="practice_sessions")
    subject = relationship("APSubject", back_populates="practice_sessions")


# ============================================================================
# PARENT DASHBOARD MODELS
# ============================================================================


class ParentProfile(Base):
    """Parent profile model."""

    __tablename__ = "parent_profiles"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Contact information
    phone_number = Column(String(20))

    # Notification preferences
    notification_email = Column(Boolean, default=True)
    notification_push = Column(Boolean, default=True)
    notification_frequency = Column(String(50), default="daily")  # 'daily', 'weekly', 'monthly'

    # Report preferences
    report_frequency = Column(String(50), default="weekly")  # 'weekly', 'monthly'

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("notification_frequency IN ('daily', 'weekly', 'monthly', 'instant')"),
        CheckConstraint("report_frequency IN ('weekly', 'monthly', 'quarterly')"),
    )

    # Relationships
    user = relationship("User")
    student_links = relationship(
        "ParentStudentLink", back_populates="parent", cascade="all, delete-orphan"
    )


class ParentStudentLink(Base):
    """Many-to-many relationship between parents and students."""

    __tablename__ = "parent_student_links"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    parent_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("parent_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship details
    relationship_type = Column(String(50), nullable=False)  # 'mother', 'father', 'guardian', 'tutor'
    access_level = Column(String(50), default="full")  # 'full', 'limited'

    # Status
    status = Column(String(50), default="active", index=True)  # 'active', 'pending', 'inactive'

    # Link metadata
    linked_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))
    approved_by = Column(PGUUID(as_uuid=True))  # User ID who approved (student or admin)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("parent_id", "student_id"),
        CheckConstraint("relationship_type IN ('mother', 'father', 'guardian', 'tutor', 'other')"),
        CheckConstraint("access_level IN ('full', 'limited')"),
        CheckConstraint("status IN ('active', 'pending', 'inactive')"),
    )

    # Relationships
    parent = relationship("ParentProfile", back_populates="student_links")
    student = relationship("StudentProfile", back_populates="parent_links")


# Update StudentProfile to include parent_links relationship
StudentProfile.parent_links = relationship(
    "ParentStudentLink",
    back_populates="student",
    cascade="all, delete-orphan"
)
