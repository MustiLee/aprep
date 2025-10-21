"""create parent tables

Revision ID: 003
Revises: 002
Create Date: 2025-10-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create parent_profiles table
    op.create_table(
        'parent_profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('phone_number', sa.String(20), nullable=True),
        sa.Column('notification_email', sa.Boolean, default=True, nullable=False),
        sa.Column('notification_push', sa.Boolean, default=True, nullable=False),
        sa.Column('notification_frequency', sa.String(50), default='daily', nullable=False),
        sa.Column('report_frequency', sa.String(50), default='weekly', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "notification_frequency IN ('daily', 'weekly', 'monthly', 'instant')",
            name='check_notification_frequency'
        ),
        sa.CheckConstraint(
            "report_frequency IN ('weekly', 'monthly', 'quarterly')",
            name='check_report_frequency'
        )
    )
    op.create_index('ix_parent_profiles_user_id', 'parent_profiles', ['user_id'])

    # Create parent_student_links table
    op.create_table(
        'parent_student_links',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_id', UUID(as_uuid=True), sa.ForeignKey('parent_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('student_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(50), nullable=False),
        sa.Column('access_level', sa.String(50), default='full', nullable=False),
        sa.Column('status', sa.String(50), default='active', nullable=False),
        sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('parent_id', 'student_id', name='uq_parent_student'),
        sa.CheckConstraint(
            "relationship_type IN ('mother', 'father', 'guardian', 'tutor', 'other')",
            name='check_relationship_type'
        ),
        sa.CheckConstraint(
            "access_level IN ('full', 'limited')",
            name='check_access_level'
        ),
        sa.CheckConstraint(
            "status IN ('active', 'pending', 'inactive')",
            name='check_link_status'
        )
    )
    op.create_index('ix_parent_student_links_parent_id', 'parent_student_links', ['parent_id'])
    op.create_index('ix_parent_student_links_student_id', 'parent_student_links', ['student_id'])
    op.create_index('ix_parent_student_links_status', 'parent_student_links', ['status'])


def downgrade():
    # Drop parent_student_links table
    op.drop_index('ix_parent_student_links_status', 'parent_student_links')
    op.drop_index('ix_parent_student_links_student_id', 'parent_student_links')
    op.drop_index('ix_parent_student_links_parent_id', 'parent_student_links')
    op.drop_table('parent_student_links')

    # Drop parent_profiles table
    op.drop_index('ix_parent_profiles_user_id', 'parent_profiles')
    op.drop_table('parent_profiles')
