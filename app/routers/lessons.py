"""
Lessons router: CRUD operations for lessons.

Permissions:
- Viewing a lesson: all authenticated users
- Creating, updating, deleting a lesson: teacher (owner) or admin
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course, Module, Lesson
from app.schemas.course import LessonCreate, LessonUpdate, LessonResponse
from app.services.cleanup import purge_lesson
from app.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lessons", tags=["lessons"])


def _check_module_ownership(module: Module, user: User, db: Session):
    """Ensure the user is the course owner or admin."""
    if user.role == "admin":
        return
    course = db.query(Course).filter(Course.id == module.course_id).first()
    if not course or course.teacher_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify lessons in this course.",
        )


@router.post("", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
def create_lesson(
    data: LessonCreate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Create a new lesson within a module."""
    module = db.query(Module).filter(Module.id == data.module_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    _check_module_ownership(module, current_user, db)

    lesson = Lesson(
        module_id=data.module_id,
        title=data.title,
        content=data.content,
        topic=data.topic,
        est_minutes=data.est_minutes,
        order=data.order,
    )
    db.add(lesson)
    db.commit()
    db.refresh(lesson)
    logger.info("Lesson created: id=%d title=%s in module %d", lesson.id, lesson.title, module.id)
    return LessonResponse.model_validate(lesson)


@router.get("/{lesson_id}", response_model=LessonResponse)
def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get lesson content and metadata."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    return LessonResponse.model_validate(lesson)


@router.patch("/{lesson_id}", response_model=LessonResponse)
def update_lesson(
    lesson_id: int,
    data: LessonUpdate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Update a lesson's title, content, topic, est_minutes, or order."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    module = db.query(Module).filter(Module.id == lesson.module_id).first()
    if module:
        _check_module_ownership(module, current_user, db)

    if data.title is not None:
        lesson.title = data.title
    if data.content is not None:
        lesson.content = data.content
    if data.topic is not None:
        lesson.topic = data.topic
    if data.est_minutes is not None:
        lesson.est_minutes = data.est_minutes
    if data.order is not None:
        lesson.order = data.order

    db.commit()
    db.refresh(lesson)
    logger.info("Lesson updated: id=%d", lesson.id)
    return LessonResponse.model_validate(lesson)


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson(
    lesson_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Delete a lesson."""
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")

    module = db.query(Module).filter(Module.id == lesson.module_id).first()
    if module:
        _check_module_ownership(module, current_user, db)

    purge_lesson(db, lesson_id)
    db.commit()
    logger.info("Lesson deleted: id=%d", lesson_id)
