"""
SQLAlchemy models package.

Import all models here so Alembic and the rest of the app can
discover them through a single import.
"""

from app.models.user import User
from app.models.course import Course, Module, Lesson
from app.models.quiz import Question, Quiz, QuizQuestion
from app.models.progress import (
    Enrollment,
    QuizAttempt,
    AttemptAnswer,
    LessonProgress,
    TopicMastery,
)
from app.models.prediction import Prediction, Recommendation
from app.models.grade import FinalGrade

__all__ = [
    "User",
    "Course",
    "Module",
    "Lesson",
    "Question",
    "Quiz",
    "QuizQuestion",
    "Enrollment",
    "QuizAttempt",
    "AttemptAnswer",
    "LessonProgress",
    "TopicMastery",
    "Prediction",
    "Recommendation",
    "FinalGrade",
]
