"""Student service layer - business logic for student dashboard."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from ..models.db_models import (
    APSubject,
    PracticeSession,
    StudentEnrollment,
    StudentProfile,
    User,
)
from ..models.student_schemas import (
    DashboardDataResponse,
    DashboardStatsResponse,
    OverallProgressResponse,
    RecentActivityItem,
    RecommendationItem,
    SubjectProgressItem,
    WeeklyProgressData,
)


class StudentService:
    """Service class for student dashboard operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_student_profile(self, user_id: UUID) -> StudentProfile:
        """Get or create student profile for a user."""
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.user_id == user_id)
            .first()
        )

        if not profile:
            # Create new profile
            profile = StudentProfile(
                user_id=user_id,
                grade_level=None,
                target_ap_exams=[],
                study_goals="",
                study_streak=0,
                longest_streak=0,
                total_questions_answered=0,
                total_questions_correct=0,
                total_study_time_minutes=0,
                overall_accuracy=Decimal("0.00"),
                topics_mastered_count=0,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    def update_student_profile(
        self, user_id: UUID, update_data: Dict
    ) -> StudentProfile:
        """Update student profile."""
        profile = self.get_or_create_student_profile(user_id)

        for key, value in update_data.items():
            if hasattr(profile, key) and value is not None:
                setattr(profile, key, value)

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_enrolled_subjects(self, user_id: UUID) -> List[StudentEnrollment]:
        """Get all subjects a student is enrolled in."""
        profile = self.get_or_create_student_profile(user_id)

        enrollments = (
            self.db.query(StudentEnrollment)
            .options(joinedload(StudentEnrollment.subject))
            .filter(StudentEnrollment.student_id == profile.id)
            .all()
        )

        return enrollments

    def enroll_in_subject(
        self, user_id: UUID, subject_id: UUID, target_exam_date: Optional[datetime] = None
    ) -> StudentEnrollment:
        """Enroll student in a subject."""
        profile = self.get_or_create_student_profile(user_id)

        # Check if already enrolled
        existing = (
            self.db.query(StudentEnrollment)
            .filter(
                and_(
                    StudentEnrollment.student_id == profile.id,
                    StudentEnrollment.subject_id == subject_id,
                )
            )
            .first()
        )

        if existing:
            return existing

        # Get subject to set total_topics
        subject = self.db.query(APSubject).filter(APSubject.id == subject_id).first()
        if not subject:
            raise ValueError("Subject not found")

        enrollment = StudentEnrollment(
            student_id=profile.id,
            subject_id=subject_id,
            target_exam_date=target_exam_date,
            total_topics=subject.topics_count,
        )

        self.db.add(enrollment)
        self.db.commit()
        self.db.refresh(enrollment)

        return enrollment

    def unenroll_from_subject(self, user_id: UUID, subject_id: UUID) -> bool:
        """Unenroll student from a subject."""
        profile = self.get_or_create_student_profile(user_id)

        enrollment = (
            self.db.query(StudentEnrollment)
            .filter(
                and_(
                    StudentEnrollment.student_id == profile.id,
                    StudentEnrollment.subject_id == subject_id,
                )
            )
            .first()
        )

        if enrollment:
            self.db.delete(enrollment)
            self.db.commit()
            return True

        return False

    def get_recent_activity(
        self, user_id: UUID, limit: int = 10
    ) -> List[RecentActivityItem]:
        """Get recent practice sessions."""
        profile = self.get_or_create_student_profile(user_id)

        sessions = (
            self.db.query(PracticeSession)
            .options(joinedload(PracticeSession.subject))
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .order_by(desc(PracticeSession.started_at))
            .limit(limit)
            .all()
        )

        activities = []
        for session in sessions:
            activities.append(
                RecentActivityItem(
                    id=session.id,
                    subject_name=session.subject.name,
                    subject_code=session.subject.code,
                    session_type=session.session_type,
                    started_at=session.started_at,
                    duration_minutes=session.duration_minutes,
                    questions_attempted=session.questions_attempted,
                    questions_correct=session.questions_correct,
                    accuracy_rate=session.accuracy_rate,
                )
            )

        return activities

    def get_weekly_progress(self, user_id: UUID) -> List[WeeklyProgressData]:
        """Get progress data for the last 7 days."""
        profile = self.get_or_create_student_profile(user_id)

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
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .filter(func.date(PracticeSession.started_at) >= week_ago)
            .group_by(func.date(PracticeSession.started_at))
            .all()
        )

        # Create map of date to data
        data_map = {}
        for session in sessions:
            data_map[str(session.date)] = WeeklyProgressData(
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
                    WeeklyProgressData(
                        date=date_str,
                        questions_answered=0,
                        study_minutes=0,
                        accuracy=Decimal("0.00"),
                    )
                )

        return progress_data

    def calculate_study_streak(self, user_id: UUID) -> None:
        """Calculate and update study streak."""
        profile = self.get_or_create_student_profile(user_id)

        # Get all practice dates
        dates = (
            self.db.query(func.date(PracticeSession.started_at).label("date"))
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .distinct()
            .order_by(desc("date"))
            .all()
        )

        if not dates:
            profile.study_streak = 0
            self.db.commit()
            return

        # Calculate current streak
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        streak = 0
        last_date = None

        for date_tuple in dates:
            date = date_tuple[0]

            if last_date is None:
                # First date - check if it's today or yesterday
                if date == today or date == yesterday:
                    streak = 1
                    last_date = date
                else:
                    break
            else:
                # Check if consecutive
                expected_date = last_date - timedelta(days=1)
                if date == expected_date:
                    streak += 1
                    last_date = date
                else:
                    break

        profile.study_streak = streak
        profile.longest_streak = max(profile.longest_streak, streak)
        profile.last_streak_update = datetime.now()
        self.db.commit()

    def get_dashboard_stats(self, user_id: UUID) -> DashboardStatsResponse:
        """Get dashboard statistics."""
        profile = self.get_or_create_student_profile(user_id)

        # Update streak
        self.calculate_study_streak(user_id)
        self.db.refresh(profile)

        # Get enrollment count
        enrollments_count = (
            self.db.query(func.count(StudentEnrollment.id))
            .filter(StudentEnrollment.student_id == profile.id)
            .scalar()
        )

        return DashboardStatsResponse(
            study_streak=profile.study_streak,
            longest_streak=profile.longest_streak,
            total_questions=profile.total_questions_answered,
            accuracy_rate=profile.overall_accuracy,
            total_study_time_minutes=profile.total_study_time_minutes,
            topics_mastered=profile.topics_mastered_count,
            enrollments_count=enrollments_count or 0,
        )

    def get_recommendations(self, user_id: UUID) -> List[RecommendationItem]:
        """Generate personalized study recommendations using agent insights."""
        profile = self.get_or_create_student_profile(user_id)
        recommendations = []

        # Get enrollments with performance data
        enrollments = (
            self.db.query(StudentEnrollment)
            .options(joinedload(StudentEnrollment.subject))
            .filter(StudentEnrollment.student_id == profile.id)
            .all()
        )

        # Recommendation 1: Low accuracy subjects
        for enrollment in enrollments:
            if enrollment.accuracy_rate < 70 and enrollment.questions_answered >= 10:
                recommendations.append(
                    RecommendationItem(
                        type="weak_subject",
                        title=f"Practice {enrollment.subject.name}",
                        description=f"Your accuracy in {enrollment.subject.name} is {enrollment.accuracy_rate:.1f}%. Practice more to improve!",
                        subject_id=enrollment.subject_id,
                        subject_name=enrollment.subject.name,
                        priority=5,
                    )
                )

        # Recommendation 2: Continue streak
        if profile.study_streak > 0:
            recommendations.append(
                RecommendationItem(
                    type="maintain_streak",
                    title=f"Keep your {profile.study_streak}-day streak!",
                    description="You're doing great! Complete a practice session today to maintain your streak.",
                    priority=4,
                )
            )

        # Recommendation 3: New subjects to explore
        enrolled_subject_ids = [e.subject_id for e in enrollments]
        available_subjects = (
            self.db.query(APSubject)
            .filter(APSubject.is_active == True)
            .filter(APSubject.id.notin_(enrolled_subject_ids))
            .limit(2)
            .all()
        )

        for subject in available_subjects:
            recommendations.append(
                RecommendationItem(
                    type="new_subject",
                    title=f"Explore {subject.name}",
                    description=f"Expand your knowledge by trying {subject.name}",
                    subject_id=subject.id,
                    subject_name=subject.name,
                    priority=2,
                )
            )

        # Recommendation 4: Practice more if low activity
        if profile.total_questions_answered < 20:
            recommendations.append(
                RecommendationItem(
                    type="practice_more",
                    title="Start practicing regularly",
                    description="Consistent practice is key to success. Try to answer at least 10 questions per day.",
                    priority=5,
                )
            )

        # Recommendation 5: High performing subjects
        for enrollment in enrollments:
            if enrollment.accuracy_rate >= 85 and enrollment.questions_answered >= 20:
                recommendations.append(
                    RecommendationItem(
                        type="excellent_progress",
                        title=f"Excellent work in {enrollment.subject.name}!",
                        description=f"You're excelling with {enrollment.accuracy_rate:.1f}% accuracy. Keep it up!",
                        subject_id=enrollment.subject_id,
                        subject_name=enrollment.subject.name,
                        priority=3,
                    )
                )

        # Sort by priority (descending)
        recommendations.sort(key=lambda x: x.priority, reverse=True)

        return recommendations[:5]  # Return top 5

    def get_overall_progress(self, user_id: UUID) -> OverallProgressResponse:
        """Get comprehensive progress metrics."""
        profile = self.get_or_create_student_profile(user_id)
        self.calculate_study_streak(user_id)
        self.db.refresh(profile)

        # Get total study days
        study_days = (
            self.db.query(func.count(func.distinct(func.date(PracticeSession.started_at))))
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .scalar()
        ) or 0

        # Get completed sessions count
        completed_sessions = (
            self.db.query(func.count(PracticeSession.id))
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .scalar()
        ) or 0

        # Calculate average session duration
        avg_duration = (
            self.db.query(func.avg(PracticeSession.duration_minutes))
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.completed_at.isnot(None))
            .scalar()
        ) or 0

        # Get enrollments count
        enrollments_count = (
            self.db.query(func.count(StudentEnrollment.id))
            .filter(StudentEnrollment.student_id == profile.id)
            .scalar()
        ) or 0

        # This week stats
        week_ago = datetime.now() - timedelta(days=7)
        this_week = (
            self.db.query(
                func.sum(PracticeSession.questions_attempted).label("questions"),
                func.sum(PracticeSession.duration_minutes).label("minutes"),
            )
            .filter(PracticeSession.student_id == profile.id)
            .filter(PracticeSession.started_at >= week_ago)
            .filter(PracticeSession.completed_at.isnot(None))
            .first()
        )

        return OverallProgressResponse(
            total_study_days=study_days,
            current_streak=profile.study_streak,
            longest_streak=profile.longest_streak,
            total_questions_answered=profile.total_questions_answered,
            total_questions_correct=profile.total_questions_correct,
            overall_accuracy=profile.overall_accuracy,
            total_study_time_minutes=profile.total_study_time_minutes,
            total_study_time_hours=round(profile.total_study_time_minutes / 60, 1),
            average_session_duration=int(avg_duration),
            topics_mastered_count=profile.topics_mastered_count,
            enrolled_subjects_count=enrollments_count,
            completed_sessions_count=completed_sessions,
            this_week_questions=this_week.questions or 0 if this_week else 0,
            this_week_study_minutes=this_week.minutes or 0 if this_week else 0,
            last_practice_date=profile.last_practice_date,
        )

    def update_profile_stats_from_session(
        self, session: PracticeSession
    ) -> None:
        """Update student profile statistics when a session is completed."""
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.id == session.student_id)
            .first()
        )

        if not profile:
            return

        # Update totals
        profile.total_questions_answered += session.questions_attempted
        profile.total_questions_correct += session.questions_correct
        profile.total_study_time_minutes += session.duration_minutes or 0
        profile.last_practice_date = session.completed_at

        # Recalculate overall accuracy
        if profile.total_questions_answered > 0:
            profile.overall_accuracy = Decimal(
                (profile.total_questions_correct / profile.total_questions_answered) * 100
            )

        # Update enrollment stats
        enrollment = (
            self.db.query(StudentEnrollment)
            .filter(
                and_(
                    StudentEnrollment.student_id == session.student_id,
                    StudentEnrollment.subject_id == session.subject_id,
                )
            )
            .first()
        )

        if enrollment:
            enrollment.questions_answered += session.questions_attempted
            enrollment.questions_correct += session.questions_correct
            enrollment.study_time_minutes += session.duration_minutes or 0
            enrollment.practice_sessions_completed += 1
            enrollment.last_practice_date = session.completed_at

            # Recalculate enrollment accuracy
            if enrollment.questions_answered > 0:
                enrollment.accuracy_rate = Decimal(
                    (enrollment.questions_correct / enrollment.questions_answered) * 100
                )

        self.db.commit()
