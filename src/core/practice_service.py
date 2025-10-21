"""Practice session service layer - business logic for practice sessions and questions."""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload

from ..agents.parametric_generator import ParametricGenerator
from ..models.db_models import (
    APSubject,
    PracticeSession,
    StudentEnrollment,
    StudentProfile,
    Template,
    Topic,
    Variant,
)
from ..models.practice_schemas import (
    PerformanceComparison,
    QuestionAnswer,
    QuestionData,
    QuestionResult,
    SessionResults,
    StudyRecommendation,
    TopicPerformance,
)
from .student_service import StudentService


class PracticeService:
    """Service class for practice session operations."""

    def __init__(self, db: Session):
        self.db = db
        self.student_service = StudentService(db)
        self.parametric_generator = ParametricGenerator()

    # ============================================================================
    # QUESTION GENERATION
    # ============================================================================

    def generate_questions(
        self,
        subject_id: UUID,
        count: int,
        topics: Optional[List[str]] = None,
        difficulty_range: Optional[Tuple[float, float]] = None,
        exclude_ids: Optional[List[UUID]] = None,
    ) -> List[QuestionData]:
        """
        Generate or retrieve practice questions.

        Args:
            subject_id: AP Subject ID
            count: Number of questions to generate
            topics: Optional list of topic names to filter
            difficulty_range: Optional (min, max) difficulty range
            exclude_ids: Recently seen question IDs to exclude

        Returns:
            List of QuestionData objects
        """
        # Get subject
        subject = self.db.query(APSubject).filter(APSubject.id == subject_id).first()
        if not subject:
            raise ValueError("Subject not found")

        # First, try to get existing verified variants from database
        query = (
            self.db.query(Variant)
            .join(Template)
            .filter(Template.course_id.isnot(None))  # Has course association
            .filter(Variant.verification_status == "pass")
        )

        # Filter by difficulty if specified
        if difficulty_range:
            min_diff, max_diff = difficulty_range
            query = query.filter(
                and_(
                    Variant.difficulty_estimate >= min_diff,
                    Variant.difficulty_estimate <= max_diff,
                )
            )

        # Exclude recently seen questions
        if exclude_ids:
            query = query.filter(Variant.id.notin_(exclude_ids))

        # Get variants
        variants = query.order_by(func.random()).limit(count * 2).all()

        questions = []
        for variant in variants[:count]:
            questions.append(
                QuestionData(
                    id=variant.id,
                    stimulus=variant.stimulus,
                    options=variant.options,
                    difficulty_estimate=variant.difficulty_estimate,
                    topic_id=None,  # TODO: Add topic tracking
                    metadata={
                        "template_id": str(variant.template_id),
                        "verification_confidence": float(variant.verification_confidence or 0),
                    },
                )
            )

        # If we don't have enough from database, generate new ones
        if len(questions) < count:
            needed = count - len(questions)
            generated = self._generate_new_questions(subject_id, needed, difficulty_range)
            questions.extend(generated)

        return questions[:count]

    def _generate_new_questions(
        self,
        subject_id: UUID,
        count: int,
        difficulty_range: Optional[Tuple[float, float]] = None,
    ) -> List[QuestionData]:
        """
        Generate new questions using parametric generator.

        Args:
            subject_id: Subject ID
            count: Number to generate
            difficulty_range: Optional difficulty range

        Returns:
            List of QuestionData
        """
        # Get templates for subject
        templates = (
            self.db.query(Template)
            .filter(Template.status == "active")
            .order_by(func.random())
            .limit(min(count, 10))
            .all()
        )

        if not templates:
            # Return placeholder questions if no templates available
            return [
                QuestionData(
                    id=UUID("00000000-0000-0000-0000-000000000000"),
                    stimulus=f"Sample question {i+1} (templates not available yet)",
                    options=[
                        "Option A",
                        "Option B",
                        "Option C",
                        "Option D",
                    ],
                    difficulty_estimate=Decimal("0.5"),
                )
                for i in range(count)
            ]

        questions = []
        variants_per_template = max(1, count // len(templates))

        for template in templates:
            # Convert template to dict for parametric generator
            template_dict = {
                "template_id": template.template_id,
                "course_id": str(template.course_id),
                "stem": template.stem,
                "solution_template": template.solution_template,
                "params": {},  # TODO: Load from TemplateParameter
                "distractor_rules": [],  # TODO: Load from DistractorRule
                "difficulty_range": template.difficulty_range or [0.4, 0.7],
            }

            # Generate variants
            try:
                variants = self.parametric_generator.generate_batch(
                    template_dict,
                    count=variants_per_template,
                    seed_start=random.randint(0, 10000),
                )

                for variant in variants:
                    questions.append(
                        QuestionData(
                            id=UUID("00000000-0000-0000-0000-000000000000"),  # Temporary ID
                            stimulus=variant.get("stimulus", ""),
                            options=variant.get("options", []),
                            difficulty_estimate=Decimal(
                                str(variant.get("metadata", {}).get("difficulty_est", 0.5))
                            ),
                        )
                    )

                    if len(questions) >= count:
                        break

            except Exception as e:
                # Log error and continue with next template
                print(f"Error generating from template {template.template_id}: {e}")
                continue

            if len(questions) >= count:
                break

        return questions[:count]

    # ============================================================================
    # SESSION STATE MANAGEMENT
    # ============================================================================

    def get_session_state(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get current state of practice session.

        Args:
            session_id: Practice session ID

        Returns:
            Session state dictionary with answers, progress, etc.
        """
        session = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.id == session_id)
            .first()
        )

        if not session:
            return None

        # Get session state from metadata
        metadata = session.metadata or {}
        return {
            "session_id": session_id,
            "started_at": session.started_at,
            "answers": metadata.get("answers", []),
            "questions": metadata.get("questions", []),
            "config": metadata.get("config", {}),
            "progress": {
                "total": metadata.get("question_count", 0),
                "answered": len(metadata.get("answers", [])),
                "flagged": len(
                    [a for a in metadata.get("answers", []) if a.get("is_flagged")]
                ),
            },
        }

    def save_session_answer(
        self, session_id: UUID, answer: QuestionAnswer
    ) -> Dict[str, Any]:
        """
        Save an answer to the session.

        Args:
            session_id: Practice session ID
            answer: Question answer

        Returns:
            Updated session state
        """
        session = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.id == session_id)
            .first()
        )

        if not session:
            raise ValueError("Session not found")

        # Get current metadata
        metadata = session.metadata or {}
        answers = metadata.get("answers", [])

        # Add or update answer
        answer_dict = {
            "question_id": str(answer.question_id),
            "selected_option": answer.selected_option,
            "time_spent_ms": answer.time_spent_ms,
            "is_flagged": answer.is_flagged,
            "answered_at": datetime.now().isoformat(),
        }

        # Remove existing answer for this question if present
        answers = [a for a in answers if a.get("question_id") != str(answer.question_id)]
        answers.append(answer_dict)

        metadata["answers"] = answers
        session.metadata = metadata

        self.db.commit()

        return self.get_session_state(session_id)

    def pause_session(self, session_id: UUID) -> Dict[str, Any]:
        """
        Pause a practice session.

        Args:
            session_id: Practice session ID

        Returns:
            Session state at pause time
        """
        session = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.id == session_id)
            .first()
        )

        if not session:
            raise ValueError("Session not found")

        metadata = session.metadata or {}
        metadata["paused_at"] = datetime.now().isoformat()
        metadata["status"] = "paused"
        session.metadata = metadata

        self.db.commit()

        return self.get_session_state(session_id)

    def resume_session(self, session_id: UUID) -> Dict[str, Any]:
        """
        Resume a paused session.

        Args:
            session_id: Practice session ID

        Returns:
            Session state
        """
        session = (
            self.db.query(PracticeSession)
            .filter(PracticeSession.id == session_id)
            .first()
        )

        if not session:
            raise ValueError("Session not found")

        metadata = session.metadata or {}
        metadata["resumed_at"] = datetime.now().isoformat()
        metadata["status"] = "in_progress"
        session.metadata = metadata

        self.db.commit()

        return self.get_session_state(session_id)

    # ============================================================================
    # SESSION COMPLETION & RESULTS
    # ============================================================================

    def complete_session(
        self,
        session_id: UUID,
        answers: List[QuestionAnswer],
        duration_minutes: int,
    ) -> SessionResults:
        """
        Complete a practice session and calculate results.

        Args:
            session_id: Practice session ID
            answers: List of all answers
            duration_minutes: Total session duration

        Returns:
            SessionResults with complete analysis
        """
        session = (
            self.db.query(PracticeSession)
            .options(joinedload(PracticeSession.subject))
            .filter(PracticeSession.id == session_id)
            .first()
        )

        if not session:
            raise ValueError("Session not found")

        metadata = session.metadata or {}
        questions = metadata.get("questions", [])

        # Calculate results
        correct_count = 0
        question_results = []
        total_time_ms = 0

        for answer in answers:
            # Find question
            question = next(
                (q for q in questions if q.get("id") == str(answer.question_id)),
                None,
            )

            if not question:
                continue

            # Get correct answer
            variant = (
                self.db.query(Variant)
                .filter(Variant.id == answer.question_id)
                .first()
            )

            if variant:
                is_correct = answer.selected_option == variant.answer_index
                if is_correct:
                    correct_count += 1

                question_results.append(
                    QuestionResult(
                        question_id=answer.question_id,
                        stimulus=variant.stimulus,
                        options=variant.options,
                        selected_option=answer.selected_option,
                        correct_option=variant.answer_index,
                        is_correct=is_correct,
                        explanation=variant.explanation,
                        solution=variant.solution,
                        time_spent_ms=answer.time_spent_ms,
                        was_flagged=answer.is_flagged,
                        difficulty=variant.difficulty_estimate,
                    )
                )

                total_time_ms += answer.time_spent_ms

        # Calculate accuracy
        questions_total = len(answers)
        accuracy = (
            Decimal(correct_count / questions_total * 100) if questions_total > 0 else Decimal(0)
        )
        avg_time = total_time_ms // questions_total if questions_total > 0 else 0

        # Update session record
        session.completed_at = datetime.now()
        session.duration_minutes = duration_minutes
        session.questions_attempted = questions_total
        session.questions_correct = correct_count
        session.accuracy_rate = accuracy

        self.db.commit()

        # Update student profile stats
        self.student_service.update_profile_stats_from_session(session)

        # Generate analytics
        topic_performance = self._calculate_topic_performance(question_results)
        performance_comparison = self._calculate_performance_comparison(
            session.student_id, session.subject_id, accuracy
        )
        recommendations = self._generate_session_recommendations(
            question_results, topic_performance
        )

        # Get updated streak
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.id == session.student_id)
            .first()
        )
        new_streak = profile.study_streak if profile else 0

        return SessionResults(
            session_id=session_id,
            subject_name=session.subject.name,
            session_type=session.session_type,
            started_at=session.started_at,
            completed_at=session.completed_at,
            duration_minutes=duration_minutes,
            questions_total=questions_total,
            questions_correct=correct_count,
            accuracy_percentage=accuracy,
            avg_time_per_question_ms=avg_time,
            question_results=question_results,
            topic_performance=topic_performance,
            performance_comparison=performance_comparison,
            study_recommendations=recommendations,
            new_streak=new_streak,
            points_earned=correct_count * 10,  # Simple point system
        )

    def _calculate_topic_performance(
        self, question_results: List[QuestionResult]
    ) -> List[TopicPerformance]:
        """Calculate performance breakdown by topic."""
        # Group by topic
        topic_map: Dict[str, Dict[str, Any]] = {}

        for result in question_results:
            topic = result.topic_name or "General"

            if topic not in topic_map:
                topic_map[topic] = {
                    "correct": 0,
                    "total": 0,
                    "total_time": 0,
                }

            topic_map[topic]["total"] += 1
            topic_map[topic]["total_time"] += result.time_spent_ms
            if result.is_correct:
                topic_map[topic]["correct"] += 1

        # Convert to list
        performance = []
        for topic, data in topic_map.items():
            accuracy = (
                Decimal(data["correct"] / data["total"] * 100)
                if data["total"] > 0
                else Decimal(0)
            )
            avg_time = data["total_time"] // data["total"] if data["total"] > 0 else 0

            performance.append(
                TopicPerformance(
                    topic_name=topic,
                    questions_count=data["total"],
                    correct_count=data["correct"],
                    accuracy_percentage=accuracy,
                    avg_time_ms=avg_time,
                )
            )

        return performance

    def _calculate_performance_comparison(
        self, student_id: UUID, subject_id: UUID, current_accuracy: Decimal
    ) -> List[PerformanceComparison]:
        """Compare current performance with previous sessions."""
        # Get last 5 completed sessions
        previous_sessions = (
            self.db.query(PracticeSession)
            .filter(
                and_(
                    PracticeSession.student_id == student_id,
                    PracticeSession.subject_id == subject_id,
                    PracticeSession.completed_at.isnot(None),
                )
            )
            .order_by(desc(PracticeSession.completed_at))
            .limit(6)
            .all()
        )

        # Skip current session (first one)
        previous_sessions = previous_sessions[1:] if len(previous_sessions) > 1 else []

        if not previous_sessions:
            return []

        # Calculate average accuracy
        avg_accuracy = sum(s.accuracy_rate for s in previous_sessions) / len(
            previous_sessions
        )

        change = current_accuracy - avg_accuracy
        trend = "up" if change > 1 else "down" if change < -1 else "stable"
        change_pct = (change / avg_accuracy * 100) if avg_accuracy > 0 else Decimal(0)

        return [
            PerformanceComparison(
                metric="accuracy",
                current_value=current_accuracy,
                previous_avg=avg_accuracy,
                change_percentage=change_pct,
                trend=trend,
            )
        ]

    def _generate_session_recommendations(
        self,
        question_results: List[QuestionResult],
        topic_performance: List[TopicPerformance],
    ) -> List[StudyRecommendation]:
        """Generate study recommendations based on session results."""
        recommendations = []

        # Find weak topics
        weak_topics = [
            t for t in topic_performance if t.accuracy_percentage < 70 and t.questions_count >= 2
        ]

        for topic in weak_topics[:2]:  # Top 2 weak topics
            recommendations.append(
                StudyRecommendation(
                    type="weak_topic",
                    priority=5,
                    title=f"Review {topic.topic_name}",
                    description=f"You scored {topic.accuracy_percentage:.0f}% on {topic.topic_name}. Review the concepts and try more practice questions.",
                    topic=topic.topic_name,
                )
            )

        # Check for slow questions
        slow_questions = [q for q in question_results if q.time_spent_ms > 180000]  # 3 min
        if len(slow_questions) >= 2:
            recommendations.append(
                StudyRecommendation(
                    type="time_management",
                    priority=3,
                    title="Work on time management",
                    description=f"You spent over 3 minutes on {len(slow_questions)} questions. Practice working through problems more efficiently.",
                )
            )

        # Check for flagged questions
        flagged = [q for q in question_results if q.was_flagged]
        if flagged:
            recommendations.append(
                StudyRecommendation(
                    type="review_flagged",
                    priority=4,
                    title="Review flagged questions",
                    description=f"You flagged {len(flagged)} questions. Review these carefully to understand what made them challenging.",
                )
            )

        # Positive reinforcement for good performance
        strong_topics = [t for t in topic_performance if t.accuracy_percentage >= 85]
        if strong_topics:
            topic = strong_topics[0]
            recommendations.append(
                StudyRecommendation(
                    type="strength",
                    priority=2,
                    title=f"Excellent work on {topic.topic_name}!",
                    description=f"You scored {topic.accuracy_percentage:.0f}% on {topic.topic_name}. Keep up the great work!",
                    topic=topic.topic_name,
                )
            )

        return sorted(recommendations, key=lambda x: x.priority, reverse=True)[:5]
