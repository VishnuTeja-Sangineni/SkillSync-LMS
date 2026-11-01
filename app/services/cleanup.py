"""
Cascade-delete helpers.

SQLite and PostgreSQL both enforce foreign keys, so deleting a parent row
(course, module, lesson, question, quiz) fails with an IntegrityError if
child rows still point at it. These helpers delete the children first, in a
safe order, and never commit: the calling router commits once at the end so
the whole delete is a single all-or-nothing transaction.
"""

from sqlalchemy.orm import Session

from app.models.course import Course, Lesson, Module
from app.models.grade import FinalGrade
from app.models.user import User
from app.models.prediction import Prediction, Recommendation
from app.models.progress import (
    AttemptAnswer,
    Enrollment,
    LessonProgress,
    QuizAttempt,
    TopicMastery,
)
from app.models.quiz import Question, Quiz, QuizQuestion


def purge_lesson(db: Session, lesson_id: int) -> None:
    """Delete a lesson and the progress rows that reference it."""
    db.query(LessonProgress).filter(LessonProgress.lesson_id == lesson_id).delete(synchronize_session=False)
    db.query(Lesson).filter(Lesson.id == lesson_id).delete(synchronize_session=False)


def purge_quiz(db: Session, quiz_id: int) -> None:
    """Delete a quiz, its question links, and all attempts (with answers)."""
    attempt_ids = [a.id for a in db.query(QuizAttempt.id).filter(QuizAttempt.quiz_id == quiz_id)]
    if attempt_ids:
        db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.query(QuizAttempt).filter(QuizAttempt.id.in_(attempt_ids)).delete(synchronize_session=False)
    db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz_id).delete(synchronize_session=False)
    db.query(Quiz).filter(Quiz.id == quiz_id).delete(synchronize_session=False)


def purge_question(db: Session, question_id: int) -> None:
    """Delete a question, removing it from quizzes and past answers first."""
    db.query(AttemptAnswer).filter(AttemptAnswer.question_id == question_id).delete(synchronize_session=False)
    db.query(QuizQuestion).filter(QuizQuestion.question_id == question_id).delete(synchronize_session=False)
    db.query(Question).filter(Question.id == question_id).delete(synchronize_session=False)


def purge_module(db: Session, module_id: int) -> None:
    """Delete a module and its lessons; quizzes in it are kept but detached."""
    lesson_ids = [l.id for l in db.query(Lesson.id).filter(Lesson.module_id == module_id)]
    for lid in lesson_ids:
        purge_lesson(db, lid)
    db.query(Quiz).filter(Quiz.module_id == module_id).update({Quiz.module_id: None}, synchronize_session=False)
    db.query(Module).filter(Module.id == module_id).delete(synchronize_session=False)


def purge_course(db: Session, course_id: int) -> None:
    """Delete a course and EVERYTHING that belongs to it."""
    for (qid,) in db.query(Quiz.id).filter(Quiz.course_id == course_id).all():
        purge_quiz(db, qid)
    for (qid,) in db.query(Question.id).filter(Question.course_id == course_id).all():
        purge_question(db, qid)
    for (mid,) in db.query(Module.id).filter(Module.course_id == course_id).all():
        purge_module(db, mid)
    db.query(Enrollment).filter(Enrollment.course_id == course_id).delete(synchronize_session=False)
    db.query(TopicMastery).filter(TopicMastery.course_id == course_id).delete(synchronize_session=False)
    db.query(Prediction).filter(Prediction.course_id == course_id).delete(synchronize_session=False)
    db.query(Recommendation).filter(Recommendation.course_id == course_id).delete(synchronize_session=False)
    db.query(FinalGrade).filter(FinalGrade.course_id == course_id).delete(synchronize_session=False)
    db.query(Course).filter(Course.id == course_id).delete(synchronize_session=False)


def purge_user(db: Session, user_id: int) -> None:
    """Delete a user and all of their learning activity (not their courses)."""
    attempt_ids = [a.id for a in db.query(QuizAttempt.id).filter(QuizAttempt.student_id == user_id)]
    if attempt_ids:
        db.query(AttemptAnswer).filter(AttemptAnswer.attempt_id.in_(attempt_ids)).delete(synchronize_session=False)
        db.query(QuizAttempt).filter(QuizAttempt.id.in_(attempt_ids)).delete(synchronize_session=False)
    for model in (LessonProgress, TopicMastery, Prediction, Recommendation, Enrollment, FinalGrade):
        db.query(model).filter(model.student_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
