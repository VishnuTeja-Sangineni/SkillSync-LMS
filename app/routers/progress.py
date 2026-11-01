"""
Progress router: tracking student progress on lessons.

Endpoints:
- POST /progress/lesson: record or update lesson completion and time spent
- GET  /progress/lesson/{lesson_id}: get current student's progress on a lesson
- GET  /progress/course/{course_id}: get student's progress on all lessons in a course
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Lesson, Module, Course
from app.models.progress import LessonProgress, Enrollment
from app.schemas.progress import LessonProgressUpdate, LessonProgressResponse
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("/lesson", response_model=LessonProgressResponse)
def update_lesson_progress(
    data: LessonProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Record lesson completion and time spent.
    Idempotent: updates existing record or creates a new one.
    """
    lesson = db.query(Lesson).filter(Lesson.id == data.lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    module = db.query(Module).filter(Module.id == lesson.module_id).first()
    course_id = module.course_id if module else None

    # Check enrollment if user is a student
    if current_user.role == "student" and course_id:
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == course_id,
        ).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to record progress.",
            )

    lp = db.query(LessonProgress).filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id == data.lesson_id,
    ).first()

    now = datetime.now(timezone.utc)
    if lp:
        lp.completed = lp.completed or data.completed
        lp.time_spent_sec += data.time_spent_sec
        lp.last_visited = now
    else:
        lp = LessonProgress(
            student_id=current_user.id,
            lesson_id=data.lesson_id,
            completed=data.completed,
            time_spent_sec=data.time_spent_sec,
            last_visited=now,
        )
        db.add(lp)

    db.commit()
    db.refresh(lp)
    logger.info(
        "Lesson progress updated: student_id=%d lesson_id=%d completed=%s time=%ds",
        current_user.id, lp.lesson_id, lp.completed, lp.time_spent_sec,
    )
    return LessonProgressResponse.model_validate(lp)


@router.get("/lesson/{lesson_id}", response_model=Optional[LessonProgressResponse])
def get_lesson_progress(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's progress for a specific lesson."""
    lp = db.query(LessonProgress).filter(
        LessonProgress.student_id == current_user.id,
        LessonProgress.lesson_id == lesson_id,
    ).first()
    if not lp:
        return None
    return LessonProgressResponse.model_validate(lp)


@router.get("/course/{course_id}", response_model=List[LessonProgressResponse])
def get_course_lesson_progress(
    course_id: int,
    student_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get lesson progress for all lessons in a course.
    Students can view their own; teachers/admin can view any student's.
    """
    target_student_id = current_user.id
    if student_id is not None:
        if current_user.role not in ("teacher", "admin") and current_user.id != student_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        target_student_id = student_id

    # Get all lesson IDs for this course
    lessons = (
        db.query(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .filter(Module.course_id == course_id)
        .all()
    )
    lesson_ids = [l.id for l in lessons]
    if not lesson_ids:
        return []

    progress_records = (
        db.query(LessonProgress)
        .filter(
            LessonProgress.student_id == target_student_id,
            LessonProgress.lesson_id.in_(lesson_ids),
        )
        .all()
    )
    return [LessonProgressResponse.model_validate(p) for p in progress_records]
