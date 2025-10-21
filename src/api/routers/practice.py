"""Practice session router - handles question generation and session management."""

import time
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ...core.auth_dependencies import get_current_active_user
from ...core.database import get_db
from ...core.practice_service import PracticeService
from ...core.student_service import StudentService
from ...models.db_models import APSubject, PracticeSession, StudentEnrollment, User
from ...models.practice_schemas import (
    PracticeSessionConfig,
    PracticeSessionStart,
    QuestionData,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    SessionAnswerSubmission,
    SessionCompletionRequest,
    SessionPauseResponse,
    SessionProgressResponse,
    SessionResumeResponse,
    SessionResults,
)

router = APIRouter()


# ============================================================================
# QUESTION GENERATION ENDPOINTS
# ============================================================================


@router.post("/questions/generate", response_model=QuestionGenerationResponse)
async def generate_questions(
    request: QuestionGenerationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Generate practice questions for a subject.

    Uses existing verified questions from database, or generates new ones
    using the parametric generator if needed.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    # Verify student is enrolled in subject
    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    enrollment = (
        db.query(StudentEnrollment)
        .filter(
            StudentEnrollment.student_id == profile.id,
            StudentEnrollment.subject_id == request.subject_id,
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be enrolled in this subject to generate questions",
        )

    # Generate questions
    start_time = time.time()
    practice_service = PracticeService(db)

    try:
        difficulty_range = (
            tuple(request.difficulty_range) if request.difficulty_range else None
        )

        questions = practice_service.generate_questions(
            subject_id=request.subject_id,
            count=request.count,
            topics=request.topics,
            difficulty_range=difficulty_range,
            exclude_ids=request.exclude_question_ids,
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        return QuestionGenerationResponse(
            questions=questions,
            count=len(questions),
            generation_time_ms=generation_time_ms,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate questions: {str(e)}",
        )


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================


@router.post("/sessions/start", response_model=PracticeSessionStart, status_code=status.HTTP_201_CREATED)
async def start_practice_session(
    config: PracticeSessionConfig,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Start a new practice session.

    Creates session record and generates questions based on configuration.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify enrollment
    enrollment = (
        db.query(StudentEnrollment)
        .options(joinedload(StudentEnrollment.subject))
        .filter(
            StudentEnrollment.student_id == profile.id,
            StudentEnrollment.subject_id == config.subject_id,
        )
        .first()
    )

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must be enrolled in this subject to start a practice session",
        )

    # Generate questions
    practice_service = PracticeService(db)

    try:
        difficulty_range = None
        if config.difficulty_level:
            # Map difficulty level (1-5) to difficulty range (0-1)
            level_map = {
                1: (0.0, 0.3),
                2: (0.2, 0.5),
                3: (0.4, 0.7),
                4: (0.6, 0.9),
                5: (0.8, 1.0),
            }
            difficulty_range = level_map.get(config.difficulty_level)

        questions = practice_service.generate_questions(
            subject_id=config.subject_id,
            count=config.question_count,
            topics=config.topics,
            difficulty_range=difficulty_range,
        )

        # Create session record
        session = PracticeSession(
            student_id=profile.id,
            subject_id=config.subject_id,
            session_type=config.session_type,
            topics_covered=config.topics or [],
            difficulty_level=config.difficulty_level,
            metadata={
                "config": config.model_dump(),
                "questions": [q.model_dump(mode="json") for q in questions],
                "answers": [],
                "status": "in_progress",
                "enable_timer": config.enable_timer,
                "time_limit_minutes": config.time_limit_minutes,
                "question_count": len(questions),
            },
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        return PracticeSessionStart(
            session_id=session.id,
            subject_id=config.subject_id,
            subject_name=enrollment.subject.name,
            question_count=len(questions),
            questions=questions,
            config=config,
            started_at=session.started_at,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}",
        )


@router.get("/sessions/{session_id}/progress", response_model=SessionProgressResponse)
async def get_session_progress(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get current progress of a practice session.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

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

    practice_service = PracticeService(db)
    state = practice_service.get_session_state(session_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session state not found",
        )

    # Calculate elapsed time
    started_at = state["started_at"]
    time_elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)

    # Convert answers to QuestionAnswer objects
    from ...models.practice_schemas import QuestionAnswer

    answers = [
        QuestionAnswer(
            question_id=UUID(a["question_id"]),
            selected_option=a["selected_option"],
            time_spent_ms=a["time_spent_ms"],
            is_flagged=a.get("is_flagged", False),
        )
        for a in state["answers"]
    ]

    return SessionProgressResponse(
        session_id=session_id,
        questions_total=state["progress"]["total"],
        questions_answered=state["progress"]["answered"],
        questions_flagged=state["progress"]["flagged"],
        time_elapsed_ms=time_elapsed_ms,
        answers=answers,
    )


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: UUID,
    answer: SessionAnswerSubmission,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Submit an answer for a question in the session.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify session ownership
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

    # Save answer
    practice_service = PracticeService(db)

    from ...models.practice_schemas import QuestionAnswer

    question_answer = QuestionAnswer(
        question_id=answer.question_id,
        selected_option=answer.selected_option,
        time_spent_ms=answer.time_spent_ms,
        is_flagged=answer.is_flagged,
    )

    try:
        practice_service.save_session_answer(session_id, question_answer)
        return {"message": "Answer saved successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/sessions/{session_id}/pause", response_model=SessionPauseResponse)
async def pause_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Pause a practice session.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify session ownership
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

    practice_service = PracticeService(db)

    try:
        state = practice_service.pause_session(session_id)

        # Build progress response
        from ...models.practice_schemas import QuestionAnswer

        answers = [
            QuestionAnswer(
                question_id=UUID(a["question_id"]),
                selected_option=a["selected_option"],
                time_spent_ms=a["time_spent_ms"],
                is_flagged=a.get("is_flagged", False),
            )
            for a in state["answers"]
        ]

        time_elapsed_ms = int((datetime.now() - state["started_at"]).total_seconds() * 1000)

        progress = SessionProgressResponse(
            session_id=session_id,
            questions_total=state["progress"]["total"],
            questions_answered=state["progress"]["answered"],
            questions_flagged=state["progress"]["flagged"],
            time_elapsed_ms=time_elapsed_ms,
            answers=answers,
        )

        return SessionPauseResponse(
            session_id=session_id,
            paused_at=datetime.now(),
            progress=progress,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/sessions/{session_id}/resume", response_model=SessionResumeResponse)
async def resume_session(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Resume a paused practice session.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify session ownership
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

    practice_service = PracticeService(db)

    try:
        state = practice_service.resume_session(session_id)

        # Rebuild questions list
        questions = [QuestionData(**q) for q in state["questions"]]

        # Build progress response
        from ...models.practice_schemas import QuestionAnswer

        answers = [
            QuestionAnswer(
                question_id=UUID(a["question_id"]),
                selected_option=a["selected_option"],
                time_spent_ms=a["time_spent_ms"],
                is_flagged=a.get("is_flagged", False),
            )
            for a in state["answers"]
        ]

        time_elapsed_ms = int((datetime.now() - state["started_at"]).total_seconds() * 1000)

        progress = SessionProgressResponse(
            session_id=session_id,
            questions_total=state["progress"]["total"],
            questions_answered=state["progress"]["answered"],
            questions_flagged=state["progress"]["flagged"],
            time_elapsed_ms=time_elapsed_ms,
            answers=answers,
        )

        return SessionResumeResponse(
            session_id=session_id,
            resumed_at=datetime.now(),
            questions=questions,
            progress=progress,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/sessions/{session_id}/complete", response_model=SessionResults)
async def complete_session(
    session_id: UUID,
    completion: SessionCompletionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Complete a practice session and get results.

    Calculates performance metrics, updates student statistics,
    and provides personalized recommendations.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify session ownership
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

    if session.completed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is already completed",
        )

    practice_service = PracticeService(db)

    try:
        results = practice_service.complete_session(
            session_id=session_id,
            answers=completion.answers,
            duration_minutes=completion.time_elapsed_minutes,
        )

        return results

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete session: {str(e)}",
        )


@router.get("/sessions/{session_id}/results", response_model=SessionResults)
async def get_session_results(
    session_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get results for a completed practice session.
    """
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint",
        )

    student_service = StudentService(db)
    profile = student_service.get_or_create_student_profile(current_user.id)

    # Verify session ownership
    session = (
        db.query(PracticeSession)
        .options(joinedload(PracticeSession.subject))
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

    if not session.completed_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not completed yet",
        )

    # Reconstruct results from session data
    # This is a simplified version - in production you'd cache results
    metadata = session.metadata or {}
    answers_data = metadata.get("answers", [])

    from ...models.practice_schemas import QuestionAnswer

    answers = [
        QuestionAnswer(
            question_id=UUID(a["question_id"]),
            selected_option=a["selected_option"],
            time_spent_ms=a["time_spent_ms"],
            is_flagged=a.get("is_flagged", False),
        )
        for a in answers_data
    ]

    practice_service = PracticeService(db)

    try:
        results = practice_service.complete_session(
            session_id=session_id,
            answers=answers,
            duration_minutes=session.duration_minutes or 0,
        )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session results: {str(e)}",
        )
