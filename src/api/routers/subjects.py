"""AP Subjects router - handles AP subject/exam management."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.db_models import APSubject
from ...models.student_schemas import APSubjectResponse

router = APIRouter()


@router.get("", response_model=List[APSubjectResponse])
async def get_all_subjects(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """
    Get all available AP subjects.

    By default, returns only active subjects. Set active_only=false to get all.
    """
    query = db.query(APSubject)

    if active_only:
        query = query.filter(APSubject.is_active == True)

    subjects = query.order_by(APSubject.name).all()
    return subjects


@router.get("/{subject_id}", response_model=APSubjectResponse)
async def get_subject_by_id(
    subject_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific AP subject by ID.
    """
    subject = db.query(APSubject).filter(APSubject.id == subject_id).first()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    return subject


@router.get("/code/{subject_code}", response_model=APSubjectResponse)
async def get_subject_by_code(
    subject_code: str,
    db: Session = Depends(get_db),
):
    """
    Get a specific AP subject by code (e.g., 'CALC_BC').
    """
    subject = db.query(APSubject).filter(APSubject.code == subject_code.upper()).first()

    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    return subject
