"""
Course, Module, and Lesson models.

A course is created by a teacher and contains ordered modules,
each of which contains ordered lessons.
"""

from sqlalchemy import String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    """
    A course created by a teacher.

    Students enroll in courses. Each course contains modules → lessons.
    """
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    # Relationships
    teacher = relationship("User", back_populates="taught_courses")
    modules = relationship("Module", back_populates="course", lazy="selectin", order_by="Module.order")
    quizzes = relationship("Quiz", back_populates="course", lazy="selectin")
    questions = relationship("Question", back_populates="course", lazy="selectin")
    enrollments = relationship("Enrollment", back_populates="course", lazy="selectin")


class Module(Base):
    """
    A module within a course. Contains ordered lessons.
    """
    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    course = relationship("Course", back_populates="modules")
    lessons = relationship("Lesson", back_populates="module", lazy="selectin", order_by="Lesson.order")
    quizzes = relationship("Quiz", back_populates="module", lazy="selectin")


class Lesson(Base):
    """
    A lesson within a module. Contains educational content.

    Each lesson is tagged with a topic (e.g., "Algebra", "Photosynthesis")
    and an estimated completion time.
    """
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(ForeignKey("modules.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True, default="")
    topic: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    est_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    module = relationship("Module", back_populates="lessons")
