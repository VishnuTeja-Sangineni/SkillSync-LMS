"""
Progress tracking models: enrollments, quiz attempts, answers,
lesson progress, and topic mastery.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Index, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Enrollment(Base):
    """
    Tracks which students are enrolled in which courses.
    """
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    student = relationship("User", back_populates="enrollments")
    course = relationship("Course", back_populates="enrollments")

    __table_args__ = (
        Index("ix_enrollments_student_course", "student_id", "course_id", unique=True),
    )


class QuizAttempt(Base):
    """
    Records a single attempt by a student at a quiz.

    score and max_score track the result; duration_sec tracks time taken.
    started_at is set when the attempt begins; finished_at when it ends.
    """
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    answers = relationship("AttemptAnswer", back_populates="attempt", lazy="selectin")

    __table_args__ = (
        Index("ix_quiz_attempts_student_quiz", "student_id", "quiz_id"),
    )


class AttemptAnswer(Base):
    """
    Records a student's answer to a single question within a quiz attempt.
    """
    __tablename__ = "attempt_answers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_taken_sec: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    # Relationships
    attempt = relationship("QuizAttempt", back_populates="answers")
    question = relationship("Question")


class LessonProgress(Base):
    """
    Tracks a student's progress on a specific lesson.
    """
    __tablename__ = "lesson_progress"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=False, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_spent_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_visited: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_lesson_progress_student_lesson", "student_id", "lesson_id", unique=True),
    )


class TopicMastery(Base):
    """
    Tracks a student's mastery level (0.0 to 1.0) for a specific topic
    within a course. Updated after each answered question.
    """
    __tablename__ = "topic_mastery"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"), primary_key=True
    )
    topic: Mapped[str] = mapped_column(String(100), primary_key=True)
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_topic_mastery_student_course", "student_id", "course_id"),
    )
