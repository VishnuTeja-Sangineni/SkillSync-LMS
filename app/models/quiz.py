"""
Quiz and Question models.

Questions are tagged by topic and difficulty. Quizzes group questions
and are associated with a course and optionally a module.
"""

from sqlalchemy import String, Text, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Question(Base):
    """
    A single question in the question bank.

    Each question belongs to a course and is tagged with a topic and difficulty
    level. Options are stored as a JSON array of strings, and correct_index
    indicates which option (0-based) is the correct answer.

    Example options_json: ["Paris", "London", "Berlin", "Madrid"]
    Example correct_index: 0  (Paris)
    """
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # easy, medium, hard
    text: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # List of option strings
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    course = relationship("Course", back_populates="questions")

    __table_args__ = (
        Index("ix_questions_course_topic", "course_id", "topic"),
        Index("ix_questions_course_difficulty", "course_id", "difficulty"),
    )


class Quiz(Base):
    """
    A quiz associated with a course and optionally a module.

    Quizzes are linked to questions through the quiz_questions association table.
    """
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    course = relationship("Course", back_populates="quizzes")
    module = relationship("Module", back_populates="quizzes")
    quiz_questions = relationship(
        "QuizQuestion",
        back_populates="quiz",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class QuizQuestion(Base):
    """
    Association table linking quizzes to questions (many-to-many).
    """
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"), primary_key=True
    )

    # Relationships
    quiz = relationship("Quiz", back_populates="quiz_questions")
    question = relationship("Question")
