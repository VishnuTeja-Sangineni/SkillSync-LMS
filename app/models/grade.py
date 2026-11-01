"""
Final grade model.

Stores the final course score (0-100) for a student once a course has been
graded. In a real deployment teachers or an admin would record these; in the
demo dataset the seed script fills them in. The ML model (Phase 5) learns to
predict this value from activity data, so it is the training label.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FinalGrade(Base):
    __tablename__ = "final_grades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_final_grades_student_course", "student_id", "course_id", unique=True),
    )
