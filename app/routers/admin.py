"""
Admin router — user management and platform stats.

All endpoints require admin role.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Enrollment, QuizAttempt
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.prediction import RetrainResponse
from app.security import require_role
from app.services.cleanup import purge_user
from ml.train import train_model
from ml.predict import invalidate_model_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = Query(None, pattern="^(student|teacher|admin)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """List all users, optionally filtered by role."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    users = query.offset(skip).limit(limit).all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    admin=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Update a user's name or role (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.name is not None:
        user.name = data.name
    if data.role is not None:
        user.role = data.role

    db.commit()
    db.refresh(user)
    logger.info("Admin updated user %d: name=%s, role=%s", user_id, user.name, user.role)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Delete a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    if db.query(Course).filter(Course.teacher_id == user.id).first():
        raise HTTPException(
            status_code=409,
            detail="This user still teaches courses. Delete or reassign their courses first.",
        )

    purge_user(db, user_id)
    db.commit()
    logger.info("Admin deleted user %d", user_id)


@router.get("/stats")
def platform_stats(
    admin=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Get platform-wide statistics."""
    total_users = db.query(func.count(User.id)).scalar()
    total_students = db.query(func.count(User.id)).filter(User.role == "student").scalar()
    total_teachers = db.query(func.count(User.id)).filter(User.role == "teacher").scalar()
    total_courses = db.query(func.count(Course.id)).scalar()
    total_enrollments = db.query(func.count(Enrollment.id)).scalar()
    total_quiz_attempts = db.query(func.count(QuizAttempt.id)).scalar()

    return {
        "total_users": total_users,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_courses": total_courses,
        "total_enrollments": total_enrollments,
        "total_quiz_attempts": total_quiz_attempts,
    }


@router.post("/retrain", response_model=RetrainResponse)
def trigger_model_retrain(
    admin=Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """
    Trigger performance prediction model retraining (admin only).
    Extracts updated dataset from student activity and updates model artifact.
    """
    try:
        result = train_model(db=db, save=True)
        invalidate_model_cache()
        return RetrainResponse(**result)
    except Exception as e:
        logger.exception("Model retraining failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model retraining failed: {str(e)}",
        )

