"""
User model — supports student, teacher, and admin roles.
"""

from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    Represents a platform user (student, teacher, or admin).

    Attributes:
        id: Primary key.
        name: Display name.
        email: Unique email address used for login.
        password_hash: bcrypt-hashed password (never store plain text!).
        role: One of "student", "teacher", or "admin".
        created_at: When the account was created.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships (back_populates used for bidirectional access)
    taught_courses = relationship("Course", back_populates="teacher", lazy="selectin")
    enrollments = relationship("Enrollment", back_populates="student", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
