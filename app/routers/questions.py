"""
Questions router: CRUD operations for question bank questions.

Permissions:
- Only teachers (course owner) and admins can view, create, edit, or delete questions.
- Students interact with questions only via adaptive quiz sessions.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.quiz import Question
from app.schemas.quiz import QuestionCreate, QuestionUpdate, QuestionResponse
from app.services.cleanup import purge_question
from app.security import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/questions", tags=["questions"])


def _check_course_ownership(course_id: int, user: User, db: Session):
    """Ensure the user owns the course or is admin."""
    if user.role == "admin":
        return
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course or course.teacher_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage questions for this course.",
        )


@router.post("", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Create a new question in a course question bank."""
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(data.course_id, current_user, db)

    question = Question(
        course_id=data.course_id,
        topic=data.topic,
        difficulty=data.difficulty,
        text=data.text,
        options_json=data.options_json,
        correct_index=data.correct_index,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    logger.info("Question created: id=%d topic=%s in course %d", question.id, question.topic, course.id)
    return QuestionResponse.model_validate(question)


@router.get("", response_model=List[QuestionResponse])
def list_questions(
    course_id: Optional[int] = Query(None),
    topic: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None, pattern="^(easy|medium|hard)$"),
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """List questions in the question bank with optional filters."""
    query = db.query(Question)
    if course_id is not None:
        _check_course_ownership(course_id, current_user, db)
        query = query.filter(Question.course_id == course_id)
    elif current_user.role != "admin":
        # Only show questions for courses taught by this teacher
        teacher_course_ids = [c.id for c in db.query(Course.id).filter(Course.teacher_id == current_user.id).all()]
        query = query.filter(Question.course_id.in_(teacher_course_ids))

    if topic:
        query = query.filter(Question.topic == topic)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)

    questions = query.all()
    return [QuestionResponse.model_validate(q) for q in questions]


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Get full question details including correct answer (teacher/admin only)."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    _check_course_ownership(question.course_id, current_user, db)
    return QuestionResponse.model_validate(question)


@router.patch("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Update question text, topic, difficulty, options, or correct answer."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    _check_course_ownership(question.course_id, current_user, db)

    # Validate correct_index against existing options if options are not updated
    options = data.options_json if data.options_json is not None else question.options_json
    correct_idx = data.correct_index if data.correct_index is not None else question.correct_index
    if correct_idx >= len(options):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"correct_index ({correct_idx}) out of range for options length ({len(options)})",
        )

    if data.topic is not None:
        question.topic = data.topic
    if data.difficulty is not None:
        question.difficulty = data.difficulty
    if data.text is not None:
        question.text = data.text
    if data.options_json is not None:
        question.options_json = data.options_json
    if data.correct_index is not None:
        question.correct_index = data.correct_index

    db.commit()
    db.refresh(question)
    logger.info("Question updated: id=%d", question.id)
    return QuestionResponse.model_validate(question)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Delete a question from the question bank."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    _check_course_ownership(question.course_id, current_user, db)

    purge_question(db, question_id)
    db.commit()
    logger.info("Question deleted: id=%d", question_id)
