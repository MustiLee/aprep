"""create student dashboard tables

Revision ID: 002
Revises: 001
Create Date: 2025-10-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Create ap_subjects table
    op.create_table(
        'ap_subjects',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('difficulty_level', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('exam_format', sa.JSON, nullable=True),
        sa.Column('topics_count', sa.Integer, default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint('difficulty_level >= 1 AND difficulty_level <= 5', name='check_difficulty_level')
    )

    # Create student_profiles table
    op.create_table(
        'student_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('grade_level', sa.Integer, nullable=True),
        sa.Column('target_ap_exams', ARRAY(sa.Text), nullable=True),
        sa.Column('study_goals', sa.Text, nullable=True),
        sa.Column('study_streak', sa.Integer, default=0, nullable=False),
        sa.Column('longest_streak', sa.Integer, default=0, nullable=False),
        sa.Column('total_questions_answered', sa.Integer, default=0, nullable=False),
        sa.Column('total_questions_correct', sa.Integer, default=0, nullable=False),
        sa.Column('total_study_time_minutes', sa.Integer, default=0, nullable=False),
        sa.Column('overall_accuracy', sa.Numeric(5, 2), default=0.0, nullable=False),
        sa.Column('topics_mastered_count', sa.Integer, default=0, nullable=False),
        sa.Column('preferred_study_time', sa.String(50), nullable=True),
        sa.Column('daily_goal_minutes', sa.Integer, default=30, nullable=False),
        sa.Column('last_practice_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_streak_update', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint('grade_level >= 9 AND grade_level <= 12', name='check_grade_level'),
        sa.CheckConstraint('overall_accuracy >= 0 AND overall_accuracy <= 100', name='check_overall_accuracy')
    )

    # Create student_enrollments table
    op.create_table(
        'student_enrollments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_id', UUID(as_uuid=True), sa.ForeignKey('ap_subjects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('enrollment_date', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('target_exam_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress_percentage', sa.Numeric(5, 2), default=0.0, nullable=False),
        sa.Column('topics_mastered', sa.Integer, default=0, nullable=False),
        sa.Column('total_topics', sa.Integer, default=0, nullable=False),
        sa.Column('questions_answered', sa.Integer, default=0, nullable=False),
        sa.Column('questions_correct', sa.Integer, default=0, nullable=False),
        sa.Column('accuracy_rate', sa.Numeric(5, 2), default=0.0, nullable=False),
        sa.Column('study_time_minutes', sa.Integer, default=0, nullable=False),
        sa.Column('practice_sessions_completed', sa.Integer, default=0, nullable=False),
        sa.Column('last_practice_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('student_id', 'subject_id', name='uq_student_subject'),
        sa.CheckConstraint('progress_percentage >= 0 AND progress_percentage <= 100', name='check_progress_percentage'),
        sa.CheckConstraint('accuracy_rate >= 0 AND accuracy_rate <= 100', name='check_accuracy_rate')
    )

    # Create practice_sessions table
    op.create_table(
        'practice_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subject_id', UUID(as_uuid=True), sa.ForeignKey('ap_subjects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_type', sa.String(50), default='practice', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer, nullable=True),
        sa.Column('questions_attempted', sa.Integer, default=0, nullable=False),
        sa.Column('questions_correct', sa.Integer, default=0, nullable=False),
        sa.Column('accuracy_rate', sa.Numeric(5, 2), default=0.0, nullable=False),
        sa.Column('topics_covered', ARRAY(sa.Text), nullable=True),
        sa.Column('difficulty_level', sa.Integer, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.CheckConstraint('accuracy_rate >= 0 AND accuracy_rate <= 100', name='check_session_accuracy_rate'),
        sa.CheckConstraint('difficulty_level >= 1 AND difficulty_level <= 5', name='check_session_difficulty_level')
    )


def downgrade():
    op.drop_table('practice_sessions')
    op.drop_table('student_enrollments')
    op.drop_table('student_profiles')
    op.drop_table('ap_subjects')
