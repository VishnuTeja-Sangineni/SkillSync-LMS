"""
Quizzes router: CRUD operations for quizzes and quiz question associations.

Permissions:
- Viewing quizzes: all authenticated users
- Creating, updating, deleting quizzes: teacher (course owner) or admin
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course, Module
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import Enrollment, QuizAttempt, AttemptAnswer, TopicMastery
from app.schemas.quiz import (
    QuizCreate,
    QuizUpdate,
    QuizResponse,
    QuizDetailResponse,
    QuestionResponse,
    QuestionStudentResponse,
    QuizStartResponse,
    QuizNextQuestionResponse,
    QuizAnswerRequest,
    QuizAnswerResponse,
    QuizFinishRequest,
    QuizFinishResponse,
)
from app.services.cleanup import purge_quiz
from app.services.mastery import compute_mastery_update, apply_forgetting_decay
from app.services.adaptive import select_next_question
from app.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _check_course_ownership(course_id: int, user: User, db: Session):
    """Ensure the user owns the course or is admin."""
    if user.role == "admin":
        return
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course or course.teacher_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage quizzes for this course.",
        )


@router.post("", response_model=QuizDetailResponse, status_code=status.HTTP_201_CREATED)
def create_quiz(
    data: QuizCreate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Create a new quiz and associate questions with it."""
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(data.course_id, current_user, db)

    if data.module_id is not None:
        module = db.query(Module).filter(Module.id == data.module_id, Module.course_id == data.course_id).first()
        if not module:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found in this course")

    quiz = Quiz(
        course_id=data.course_id,
        module_id=data.module_id,
        title=data.title,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)

    # Associate questions
    questions = []
    if data.question_ids:
        # Validate that all questions belong to the course
        found_questions = db.query(Question).filter(
            Question.id.in_(data.question_ids),
            Question.course_id == data.course_id,
        ).all()
        for q in found_questions:
            assoc = QuizQuestion(quiz_id=quiz.id, question_id=q.id)
            db.add(assoc)
            questions.append(QuestionResponse.model_validate(q))
        db.commit()

    logger.info("Quiz created: id=%d title=%s in course %d", quiz.id, quiz.title, quiz.course_id)
    return QuizDetailResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        module_id=quiz.module_id,
        title=quiz.title,
        questions=questions,
    )


@router.get("", response_model=List[QuizResponse])
def list_quizzes(
    course_id: Optional[int] = Query(None),
    module_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List quizzes, optionally filtered by course or module."""
    query = db.query(Quiz)
    if course_id is not None:
        query = query.filter(Quiz.course_id == course_id)
    if module_id is not None:
        query = query.filter(Quiz.module_id == module_id)
    quizzes = query.all()
    return [QuizResponse.model_validate(q) for q in quizzes]


@router.get("/{quiz_id}")
def get_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get quiz details.
    Teachers and admins see questions with correct answers.
    Students see questions without correct answers.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    # Load associated questions
    quiz_questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
    question_ids = [qq.question_id for qq in quiz_questions]
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all() if question_ids else []

    is_privileged = current_user.role in ("teacher", "admin")

    if is_privileged:
        q_list = [QuestionResponse.model_validate(q) for q in questions]
        return {
            "id": quiz.id,
            "course_id": quiz.course_id,
            "module_id": quiz.module_id,
            "title": quiz.title,
            "questions": q_list,
        }
    else:
        q_list = [QuestionStudentResponse.model_validate(q) for q in questions]
        return {
            "id": quiz.id,
            "course_id": quiz.course_id,
            "module_id": quiz.module_id,
            "title": quiz.title,
            "questions": q_list,
        }


@router.patch("/{quiz_id}", response_model=QuizDetailResponse)
def update_quiz(
    quiz_id: int,
    data: QuizUpdate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Update quiz title, module_id, or question_ids."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    _check_course_ownership(quiz.course_id, current_user, db)

    if data.title is not None:
        quiz.title = data.title
    if data.module_id is not None:
        module = db.query(Module).filter(Module.id == data.module_id, Module.course_id == quiz.course_id).first()
        if not module:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found in this course")
        quiz.module_id = data.module_id

    if data.question_ids is not None:
        # Clear existing associations and re-add
        db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).delete()
        found_questions = db.query(Question).filter(
            Question.id.in_(data.question_ids),
            Question.course_id == quiz.course_id,
        ).all()
        for q in found_questions:
            db.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id))

    db.commit()
    db.refresh(quiz)

    # Return updated quiz with questions
    qqs = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).all()
    q_ids = [qq.question_id for qq in qqs]
    questions = db.query(Question).filter(Question.id.in_(q_ids)).all() if q_ids else []

    logger.info("Quiz updated: id=%d", quiz.id)
    return QuizDetailResponse(
        id=quiz.id,
        course_id=quiz.course_id,
        module_id=quiz.module_id,
        title=quiz.title,
        questions=[QuestionResponse.model_validate(q) for q in questions],
    )


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(
    quiz_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Delete a quiz and its question associations."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    _check_course_ownership(quiz.course_id, current_user, db)

    purge_quiz(db, quiz_id)
    db.commit()
    logger.info("Quiz deleted: id=%d", quiz_id)


# ── Adaptive Quiz Taking Endpoints ────────────────────────────────────

@router.post("/{quiz_id}/start", response_model=QuizStartResponse, status_code=status.HTTP_201_CREATED)
def start_quiz(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start a new adaptive quiz attempt.
    Students must be enrolled in the course.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    if current_user.role == "student":
        enrollment = db.query(Enrollment).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.course_id == quiz.course_id,
        ).first()
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be enrolled in this course to take this quiz.",
            )

    total_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .count()
    )

    attempt = QuizAttempt(
        student_id=current_user.id,
        quiz_id=quiz.id,
        score=0.0,
        max_score=0.0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    logger.info("Quiz attempt started: attempt_id=%d student_id=%d quiz_id=%d", attempt.id, current_user.id, quiz.id)
    return QuizStartResponse(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        student_id=attempt.student_id,
        started_at=attempt.started_at,
        total_questions=total_questions,
    )


@router.get("/{quiz_id}/next-question", response_model=QuizNextQuestionResponse)
def get_next_question(
    quiz_id: int,
    attempt_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the next adaptively selected question for an active attempt.
    Difficulty is tailored to the student's mastery in the topic.
    Returns question without correct_index.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    attempt = db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id).first()
    if not attempt or attempt.quiz_id != quiz.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found")

    if attempt.student_id != current_user.id and current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this attempt")

    if attempt.finished_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz attempt has already finished")

    total_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz.id)
        .count()
    )
    answered_count = (
        db.query(AttemptAnswer)
        .filter(AttemptAnswer.attempt_id == attempt.id)
        .count()
    )

    next_q = select_next_question(db, quiz.id, attempt.student_id, attempt.id)

    if next_q is None:
        return QuizNextQuestionResponse(
            question=None,
            attempt_id=attempt.id,
            question_number=answered_count,
            total_questions=total_questions,
            is_complete=True,
        )

    return QuizNextQuestionResponse(
        question=QuestionStudentResponse.model_validate(next_q),
        attempt_id=attempt.id,
        question_number=answered_count + 1,
        total_questions=total_questions,
        is_complete=False,
    )


@router.post("/{quiz_id}/answer", response_model=QuizAnswerResponse)
def answer_question(
    quiz_id: int,
    data: QuizAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit an answer for a question in an active quiz attempt.
    Updates attempt score, saves AttemptAnswer, and updates TopicMastery
    using the exponentially weighted formula.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    attempt = db.query(QuizAttempt).filter(QuizAttempt.id == data.attempt_id).first()
    if not attempt or attempt.quiz_id != quiz.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found")

    if attempt.student_id != current_user.id and current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this attempt")

    if attempt.finished_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quiz attempt has already finished")

    question = db.query(Question).filter(Question.id == data.question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    # Verify question belongs to this quiz
    qq = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_id == quiz.id,
        QuizQuestion.question_id == question.id,
    ).first()
    if not qq:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question does not belong to this quiz")

    # Prevent duplicate answers in the same attempt
    existing_ans = db.query(AttemptAnswer).filter(
        AttemptAnswer.attempt_id == attempt.id,
        AttemptAnswer.question_id == question.id,
    ).first()
    if existing_ans:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Question already answered in this attempt")

    is_correct = (data.selected_index == question.correct_index)

    # Record answer
    ans = AttemptAnswer(
        attempt_id=attempt.id,
        question_id=question.id,
        selected_index=data.selected_index,
        is_correct=is_correct,
        time_taken_sec=data.time_taken_sec or 0,
    )
    db.add(ans)

    # Update attempt score
    attempt.max_score += 1.0
    if is_correct:
        attempt.score += 1.0

    # Update Topic Mastery
    tm = db.query(TopicMastery).filter(
        TopicMastery.student_id == attempt.student_id,
        TopicMastery.course_id == quiz.course_id,
        TopicMastery.topic == question.topic,
    ).first()

    if tm:
        current_m = apply_forgetting_decay(tm.mastery, tm.updated_at)
        new_mastery = compute_mastery_update(current_m, is_correct, question.difficulty)
        tm.mastery = new_mastery
        tm.updated_at = datetime.now(timezone.utc)
    else:
        new_mastery = compute_mastery_update(0.5, is_correct, question.difficulty)
        tm = TopicMastery(
            student_id=attempt.student_id,
            course_id=quiz.course_id,
            topic=question.topic,
            mastery=new_mastery,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(tm)

    db.commit()

    logger.info(
        "Question answered: attempt=%d q=%d is_correct=%s new_mastery=%.4f",
        attempt.id, question.id, is_correct, new_mastery,
    )
    return QuizAnswerResponse(
        is_correct=is_correct,
        correct_index=question.correct_index,
        new_mastery=new_mastery,
        topic=question.topic,
        difficulty=question.difficulty,
    )


@router.post("/{quiz_id}/finish", response_model=QuizFinishResponse)
def finish_quiz(
    quiz_id: int,
    data: QuizFinishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finish a quiz attempt and calculate total score and duration."""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    attempt = db.query(QuizAttempt).filter(QuizAttempt.id == data.attempt_id).first()
    if not attempt or attempt.quiz_id != quiz.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found")

    if attempt.student_id != current_user.id and current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this attempt")

    if attempt.finished_at is None:
        now = datetime.now(timezone.utc)
        attempt.finished_at = now
        started = attempt.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        attempt.duration_sec = max(0, int((now - started).total_seconds()))
        db.commit()
        db.refresh(attempt)

    pct = round((attempt.score / attempt.max_score * 100.0), 2) if attempt.max_score > 0 else 0.0

    logger.info(
        "Quiz finished: attempt_id=%d score=%.1f/%.1f (%.1f%%) duration=%ds",
        attempt.id, attempt.score, attempt.max_score, pct, attempt.duration_sec or 0,
    )
    return QuizFinishResponse(
        attempt_id=attempt.id,
        quiz_id=quiz.id,
        student_id=attempt.student_id,
        score=attempt.score,
        max_score=attempt.max_score,
        percentage=pct,
        duration_sec=attempt.duration_sec or 0,
        finished_at=attempt.finished_at,
    )

