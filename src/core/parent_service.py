"""Parent service layer - business logic for parent dashboard."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
from uuid import UUID

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from ..models.db_models import (
    APSubject,
    ParentProfile,
    ParentStudentLink,
    PracticeSession,
    StudentEnrollment,
    StudentProfile,
    User,
)
from ..models.parent_schemas import (
    ChildAlert,
    ChildDashboardStats,
    ChildDetailResponse,
    ChildPracticeSession,
    ChildSubjectPerformance,
    ChildSummary,
    ChildWeeklyProgress,
    LinkedStudentResponse,
    ParentInsight,
    ParentOverviewResponse,
)
from .student_service import StudentService


class ParentService:
    """Service class for parent dashboard operations."""

    def __init__(self, db: Session):
        self.db = db
        self.student_service = StudentService(db)

    def get_or_create_parent_profile(self, user_id: UUID) -> ParentProfile:
        """Get or create parent profile for a user."""
        profile = (
            self.db.query(ParentProfile)
            .filter(ParentProfile.user_id == user_id)
            .first()
        )

        if not profile:
            # Create new profile
            profile = ParentProfile(
                user_id=user_id,
                phone_number=None,
                notification_email=True,
                notification_push=True,
                notification_frequency="daily",
                report_frequency="weekly",
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    def update_parent_profile(
        self, user_id: UUID, update_data: Dict
    ) -> ParentProfile:
        """Update parent profile."""
        profile = self.get_or_create_parent_profile(user_id)

        for key, value in update_data.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def link_student(
        self,
        parent_user_id: UUID,
        student_email: str,
        relationship_type: str,
        access_level: str = "full",
    ) -> ParentStudentLink:
        """Link a student to a parent account."""
        # Get parent profile
        parent_profile = self.get_or_create_parent_profile(parent_user_id)

        # Find student by email
        student_user = (
            self.db.query(User)
            .filter(User.email == student_email)
            .filter(User.role == "student")
            .first()
        )

        if not student_user:
            raise ValueError("Student not found with this email address")

        # Get or create student profile
        student_profile = self.student_service.get_or_create_student_profile(
            student_user.id
        )

        # Check if already linked
        existing_link = (
            self.db.query(ParentStudentLink)
            .filter(
                and_(
                    ParentStudentLink.parent_id == parent_profile.id,
                    ParentStudentLink.student_id == student_profile.id,
                )
            )
            .first()
        )

        if existing_link:
            if existing_link.status == "inactive":
                # Reactivate the link
                existing_link.status = "active"
                existing_link.linked_at = datetime.now()
                self.db.commit()
                self.db.refresh(existing_link)
                return existing_link
            else:
                raise ValueError("Student is already linked to this parent account")

        # Create new link (initially active, could be set to pending for approval flow)
        link = ParentStudentLink(
            parent_id=parent_profile.id,
            student_id=student_profile.id,
            relationship_type=relationship_type,
            access_level=access_level,
            status="active",  # Could be "pending" if requiring student approval
            approved_at=datetime.now(),  # Auto-approve for now
            approved_by=parent_user_id,
        )

        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)

        return link

    def unlink_student(self, parent_user_id: UUID, student_id: UUID) -> bool:
        """Unlink a student from parent account."""
        parent_profile = self.get_or_create_parent_profile(parent_user_id)

        link = (
            self.db.query(ParentStudentLink)
            .filter(
                and_(
                    ParentStudentLink.parent_id == parent_profile.id,
                    ParentStudentLink.student_id == student_id,
                )
            )
            .first()
        )

        if link:
            # Soft delete by setting status to inactive
            link.status = "inactive"
            self.db.commit()
            return True

        return False

    def get_linked_students(self, parent_user_id: UUID) -> List[LinkedStudentResponse]:
        """Get all students linked to a parent."""
        parent_profile = self.get_or_create_parent_profile(parent_user_id)

        links = (
            self.db.query(ParentStudentLink)
            .options(
                joinedload(ParentStudentLink.student)
                .joinedload(StudentProfile.user)
            )
            .filter(ParentStudentLink.parent_id == parent_profile.id)
            .filter(ParentStudentLink.status == "active")
            .all()
        )

        linked_students = []
        for link in links:
            student = link.student
            student_user = student.user

            linked_students.append(
                LinkedStudentResponse(
                    id=link.id,
                    parent_id=link.parent_id,
                    student_id=student.id,
                    student_user_id=student.user_id,
                    student_name=student_user.full_name,
                    student_email=student_user.email,
                    relationship_type=link.relationship_type,
                    access_level=link.access_level,
                    linked_at=link.linked_at,
                    study_streak=student.study_streak,
                    overall_accuracy=student.overall_accuracy,
                    total_study_time_minutes=student.total_study_time_minutes,
                    last_practice_date=student.last_practice_date,
                )
            )

        return linked_students

    def get_child_dashboard(
        self, parent_user_id: UUID, student_id: UUID
    ) -> ChildDashboardStats:
        """Get dashboard statistics for a specific child."""
        # Verify parent has access to this student
        self._verify_parent_access(parent_user_id, student_id)

        # Get student profile
        student = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.id == student_id)
            .first()
        )

        if not student:
            raise ValueError("Student not found")

        # Update streak
        self.student_service.calculate_study_streak(student.user_id)
        self.db.refresh(student)

        # Get enrollment count
        enrollments_count = (
            self.db.query(func.count(StudentEnrollment.id))
            .filter(StudentEnrollment.student_id == student_id)
            .scalar()
        ) or 0

        return ChildDashboardStats(
            study_streak=student.study_streak,
            longest_streak=student.longest_streak,
            total_questions=student.total_questions_answered,
            accuracy_rate=student.overall_accuracy,
            total_study_time_minutes=student.total_study_time_minutes,
            total_study_time_hours=round(student.total_study_time_minutes / 60, 1),
            topics_mastered=student.topics_mastered_count,
            enrollments_count=enrollments_count,
            last_practice_date=student.last_practice_date,
        )

    def get_child_subjects(
        self, parent_user_id: UUID, student_id: UUID
    ) -> List[ChildSubjectPerformance]:
        """Get subject performance for a child."""
        # Verify parent has access
        self._verify_parent_access(parent_user_id, student_id)

        enrollments = (
            self.db.query(StudentEnrollment)
            .options(joinedload(StudentEnrollment.subject))
            .filter(StudentEnrollment.student_id == student_id)
            .all()
        )

        subjects = []
        for enrollment in enrollments:
            subjects.append(
                ChildSubjectPerformance(
                    subject_id=enrollment.subject_id,
                    subject_name=enrollment.subject.name,
                    subject_code=enrollment.subject.code,
                    progress_percentage=enrollment.progress_percentage,
                    accuracy_rate=enrollment.accuracy_rate,
                    questions_answered=enrollment.questions_answered,
                    questions_correct=enrollment.questions_correct,
                    study_time_minutes=enrollment.study_time_minutes,
                    practice_sessions_completed=enrollment.practice_sessions_completed,
                    last_practice_date=enrollment.last_practice_date,
                )
            )

        return subjects

    def get_child_sessions(
        self, parent_user_id: UUID, student_id: UUID, limit: int = 20
    ) -> List[ChildPracticeSession]:
        """Get practice session history for a child."""
        # Verify parent has access
        self._verify_parent_access(parent_user_id, student_id)

        sessions = (
            self.db.query(PracticeSession)
            .options(joinedload(PracticeSession.subject))
            .filter(PracticeSession.student_id == student_id)
            .filter(PracticeSession.completed_at.isnot(None))
            .order_by(desc(PracticeSession.started_at))
            .limit(limit)
            .all()
        )

        session_list = []
        for session in sessions:
            session_list.append(
                ChildPracticeSession(
                    id=session.id,
                    subject_name=session.subject.name,
                    subject_code=session.subject.code,
                    session_type=session.session_type,
                    started_at=session.started_at,
                    completed_at=session.completed_at,
                    duration_minutes=session.duration_minutes,
                    questions_attempted=session.questions_attempted,
                    questions_correct=session.questions_correct,
                    accuracy_rate=session.accuracy_rate,
                )
            )

        return session_list

    def get_child_weekly_progress(
        self, parent_user_id: UUID, student_id: UUID
    ) -> List[ChildWeeklyProgress]:
        """Get weekly progress data for a child."""
        # Verify parent has access
        self._verify_parent_access(parent_user_id, student_id)

        # Get last 7 days
        today = datetime.now().date()
        week_ago = today - timedelta(days=6)

        # Query sessions grouped by date
        sessions = (
            self.db.query(
                func.date(PracticeSession.started_at).label("date"),
                func.sum(PracticeSession.questions_attempted).label("questions"),
                func.sum(PracticeSession.duration_minutes).label("minutes"),
                func.avg(PracticeSession.accuracy_rate).label("accuracy"),
            )
            .filter(PracticeSession.student_id == student_id)
            .filter(PracticeSession.completed_at.isnot(None))
            .filter(func.date(PracticeSession.started_at) >= week_ago)
            .group_by(func.date(PracticeSession.started_at))
            .all()
        )

        # Create map of date to data
        data_map = {}
        for session in sessions:
            data_map[str(session.date)] = ChildWeeklyProgress(
                date=str(session.date),
                questions_answered=session.questions or 0,
                study_minutes=session.minutes or 0,
                accuracy=Decimal(str(session.accuracy or 0)),
            )

        # Fill in missing days with zeros
        progress_data = []
        for i in range(7):
            date = week_ago + timedelta(days=i)
            date_str = str(date)
            if date_str in data_map:
                progress_data.append(data_map[date_str])
            else:
                progress_data.append(
                    ChildWeeklyProgress(
                        date=date_str,
                        questions_answered=0,
                        study_minutes=0,
                        accuracy=Decimal("0.00"),
                    )
                )

        return progress_data

    def get_child_detail(
        self, parent_user_id: UUID, student_id: UUID
    ) -> ChildDetailResponse:
        """Get comprehensive detail view for a child."""
        # Verify parent has access
        link = self._verify_parent_access(parent_user_id, student_id)

        # Get student info
        student = (
            self.db.query(StudentProfile)
            .options(joinedload(StudentProfile.user))
            .filter(StudentProfile.id == student_id)
            .first()
        )

        if not student:
            raise ValueError("Student not found")

        # Get all data
        stats = self.get_child_dashboard(parent_user_id, student_id)
        subjects = self.get_child_subjects(parent_user_id, student_id)
        sessions = self.get_child_sessions(parent_user_id, student_id, limit=10)
        weekly_progress = self.get_child_weekly_progress(parent_user_id, student_id)

        return ChildDetailResponse(
            student_id=student.id,
            student_name=student.user.full_name,
            student_email=student.user.email,
            relationship_type=link.relationship_type,
            stats=stats,
            subjects=subjects,
            recent_sessions=sessions,
            weekly_progress=weekly_progress,
        )

    def get_parent_overview(self, parent_user_id: UUID) -> ParentOverviewResponse:
        """Get aggregated overview of all children."""
        linked_students = self.get_linked_students(parent_user_id)

        children_summaries = []
        total_questions = 0
        total_correct = 0
        total_study_time = 0
        active_today = 0

        today = datetime.now().date()

        for linked_student in linked_students:
            student = (
                self.db.query(StudentProfile)
                .options(joinedload(StudentProfile.user))
                .filter(StudentProfile.id == linked_student.student_id)
                .first()
            )

            if not student:
                continue

            # Count recent activity
            recent_count = (
                self.db.query(func.count(PracticeSession.id))
                .filter(PracticeSession.student_id == student.id)
                .filter(PracticeSession.completed_at.isnot(None))
                .filter(func.date(PracticeSession.started_at) >= today - timedelta(days=7))
                .scalar()
            ) or 0

            # Check if active today
            if student.last_practice_date and student.last_practice_date.date() == today:
                active_today += 1

            # Get enrollment count
            enrollments_count = (
                self.db.query(func.count(StudentEnrollment.id))
                .filter(StudentEnrollment.student_id == student.id)
                .scalar()
            ) or 0

            children_summaries.append(
                ChildSummary(
                    student_id=student.id,
                    student_name=student.user.full_name,
                    student_email=student.user.email,
                    relationship_type=linked_student.relationship_type,
                    study_streak=student.study_streak,
                    accuracy_rate=student.overall_accuracy,
                    total_study_time_minutes=student.total_study_time_minutes,
                    enrollments_count=enrollments_count,
                    last_practice_date=student.last_practice_date,
                    recent_activity_count=recent_count,
                )
            )

            # Aggregate stats
            total_questions += student.total_questions_answered
            total_correct += student.total_questions_correct
            total_study_time += student.total_study_time_minutes

        # Calculate aggregated accuracy
        aggregated_accuracy = (
            Decimal((total_correct / total_questions) * 100) if total_questions > 0 else Decimal("0.00")
        )

        aggregated_stats = {
            "total_questions": total_questions,
            "total_correct": total_correct,
            "aggregated_accuracy": float(aggregated_accuracy),
            "total_study_time_minutes": total_study_time,
            "total_study_time_hours": round(total_study_time / 60, 1),
        }

        # Get alerts
        alerts = self._generate_alerts(parent_user_id, children_summaries)

        return ParentOverviewResponse(
            children=children_summaries,
            total_children=len(children_summaries),
            aggregated_stats=aggregated_stats,
            recent_alerts=alerts,
            total_active_today=active_today,
        )

    def _verify_parent_access(
        self, parent_user_id: UUID, student_id: UUID
    ) -> ParentStudentLink:
        """Verify that parent has access to student data."""
        parent_profile = self.get_or_create_parent_profile(parent_user_id)

        link = (
            self.db.query(ParentStudentLink)
            .filter(
                and_(
                    ParentStudentLink.parent_id == parent_profile.id,
                    ParentStudentLink.student_id == student_id,
                    ParentStudentLink.status == "active",
                )
            )
            .first()
        )

        if not link:
            raise ValueError("You do not have access to this student's data")

        return link

    def _generate_alerts(
        self, parent_user_id: UUID, children: List[ChildSummary]
    ) -> List[ChildAlert]:
        """Generate alerts based on children's performance."""
        alerts = []
        now = datetime.now()

        for child in children:
            student = (
                self.db.query(StudentProfile)
                .filter(StudentProfile.id == child.student_id)
                .first()
            )

            if not student:
                continue

            # Alert: Low performance
            if child.accuracy_rate < 60 and child.recent_activity_count > 5:
                alerts.append(
                    ChildAlert(
                        type="low_performance",
                        severity="warning",
                        title="Low Accuracy Alert",
                        message=f"{child.student_name} has an accuracy rate of {child.accuracy_rate:.1f}%. Consider reviewing study materials.",
                        student_id=child.student_id,
                        student_name=child.student_name,
                        created_at=now,
                    )
                )

            # Alert: Missed study days
            if student.last_practice_date:
                days_since_practice = (now.date() - student.last_practice_date.date()).days
                if days_since_practice >= 3:
                    alerts.append(
                        ChildAlert(
                            type="missed_study",
                            severity="critical",
                            title="Inactive Student",
                            message=f"{child.student_name} hasn't practiced in {days_since_practice} days.",
                            student_id=child.student_id,
                            student_name=child.student_name,
                            created_at=now,
                        )
                    )

            # Alert: Achievement - great streak
            if child.study_streak >= 7:
                alerts.append(
                    ChildAlert(
                        type="achievement",
                        severity="info",
                        title="Amazing Streak!",
                        message=f"{child.student_name} has a {child.study_streak}-day study streak!",
                        student_id=child.student_id,
                        student_name=child.student_name,
                        created_at=now,
                    )
                )

            # Alert: High performance
            if child.accuracy_rate >= 85 and child.recent_activity_count > 5:
                alerts.append(
                    ChildAlert(
                        type="achievement",
                        severity="info",
                        title="Excellent Performance",
                        message=f"{child.student_name} is excelling with {child.accuracy_rate:.1f}% accuracy!",
                        student_id=child.student_id,
                        student_name=child.student_name,
                        created_at=now,
                    )
                )

        # Sort by severity (critical first)
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda x: severity_order.get(x.severity, 3))

        return alerts[:10]  # Return top 10

    def generate_insights(self, parent_user_id: UUID) -> List[ParentInsight]:
        """Generate AI-powered insights for parents."""
        children = self.get_linked_students(parent_user_id)
        insights = []

        for child in children:
            student = (
                self.db.query(StudentProfile)
                .filter(StudentProfile.id == child.student_id)
                .first()
            )

            if not student:
                continue

            # Insight: Consistent practice
            if student.study_streak >= 5:
                insights.append(
                    ParentInsight(
                        type="milestone",
                        title=f"{student.user.full_name} is on a roll!",
                        description=f"Your child has maintained a {student.study_streak}-day study streak. Consistent practice leads to better retention.",
                        student_id=student.id,
                        student_name=student.user.full_name,
                        priority=4,
                        actionable=True,
                        action_text="Encourage them to keep it up!",
                    )
                )

            # Insight: Needs more practice
            if student.total_questions_answered > 0 and student.overall_accuracy < 70:
                insights.append(
                    ParentInsight(
                        type="concern",
                        title=f"{student.user.full_name} needs support",
                        description=f"Current accuracy is {student.overall_accuracy:.1f}%. Consider scheduling study time or seeking additional help.",
                        student_id=student.id,
                        student_name=student.user.full_name,
                        priority=5,
                        actionable=True,
                        action_text="Review weak topics together",
                    )
                )

            # Insight: Subject-specific performance
            enrollments = (
                self.db.query(StudentEnrollment)
                .options(joinedload(StudentEnrollment.subject))
                .filter(StudentEnrollment.student_id == student.id)
                .filter(StudentEnrollment.accuracy_rate < 65)
                .filter(StudentEnrollment.questions_answered >= 10)
                .all()
            )

            for enrollment in enrollments:
                insights.append(
                    ParentInsight(
                        type="recommendation",
                        title=f"Focus on {enrollment.subject.name}",
                        description=f"{student.user.full_name} is struggling with {enrollment.subject.name} ({enrollment.accuracy_rate:.1f}% accuracy).",
                        student_id=student.id,
                        student_name=student.user.full_name,
                        subject_name=enrollment.subject.name,
                        priority=4,
                        actionable=True,
                        action_text="Increase practice sessions in this subject",
                    )
                )

        # Sort by priority
        insights.sort(key=lambda x: x.priority, reverse=True)
        return insights[:8]  # Return top 8
