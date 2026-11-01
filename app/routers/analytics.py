"""
Analytics router: student and course analytics endpoints.

Endpoints:
- GET /analytics/student/{student_id}: Personal mastery, score trends, streak, weak areas
- GET /analytics/course/{course_id}: Class-level topic mastery, score distribution, engagement
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.schemas.analytics import StudentAnalyticsResponse, CourseAnalyticsResponse
from app.services.analytics import compute_student_analytics, compute_course_analytics
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/student/{student_id}", response_model=StudentAnalyticsResponse)
def get_student_analytics_endpoint(
    student_id: int,
    course_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get personal analytics for a student.
    Students can only view their own analytics.
    Teachers and admins can view any student's analytics.
    """
    if current_user.role == "student" and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own analytics.",
        )

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    try:
        analytics = compute_student_analytics(db, student_id=student_id, course_id=course_id)
        return analytics
    except Exception as e:
        logger.error("Failed to compute student analytics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute analytics",
        )


@router.get("/course/{course_id}", response_model=CourseAnalyticsResponse)
def get_course_analytics_endpoint(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get class-level analytics for a course.
    Only the course's teacher or platform admin can view class analytics.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot view class-level analytics.",
        )

    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view analytics for courses you teach.",
        )

    try:
        analytics = compute_course_analytics(db, course_id=course_id)
        return analytics
    except Exception as e:
        logger.error("Failed to compute course analytics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute analytics",
        )
