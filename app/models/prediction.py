"""
Prediction and Recommendation models.

Predictions store ML-generated scores and risk levels.
Recommendations store actionable suggestions for students.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, JSON, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    """
    Stores an ML-generated prediction for a student in a course.

    predicted_score: estimated final score (0-100).
    risk_level: "Low", "Medium", or "High".
    top_factors_json: JSON list of the top factors influencing the prediction,
        e.g. [{"factor": "low_mastery", "value": 0.32, "description": "..."}]
    """
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    predicted_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)  # Low, Medium, High
    top_factors_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_predictions_student_course", "student_id", "course_id"),
    )


class Recommendation(Base):
    """
    Stores a personalized recommendation for a student in a course.

    type: "lesson", "quiz", or "action"
    target_id: the id of the recommended lesson or quiz (nullable for actions)
    reason: human-readable explanation
    priority: 1 (highest) to 10 (lowest)
    """
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # lesson, quiz, action
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_recommendations_student_course", "student_id", "course_id"),
    )
