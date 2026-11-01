"""
Recommendations router: personalized recommendations for students.

Endpoint:
- GET /recommendations/student/{student_id}/course/{course_id}:
    Hybrid rule-based + collaborative recommendations for next best actions.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Enrollment
from app.schemas.prediction import RecommendationResponse
from app.security import get_current_user
from recommender.engine import get_recommendations_for_student

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "/student/{student_id}/course/{course_id}",
    response_model=List[RecommendationResponse],
)
def get_recommendations_endpoint(
    student_id: int,
    course_id: int,
    limit: int = Query(5, ge=1, le=20),
    refresh: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get personalized recommendations (what to study next, which quizzes to take,
    and remediation actions) ranked by priority.
    Students can only view their own recommendations.
    Teachers can view recommendations for students in courses they teach.
    Admins can view any recommendation.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    # Authorization
    if current_user.role == "student" and current_user.id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own recommendations.",
        )

    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view recommendations for courses you teach.",
        )

    # Check enrollment
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.course_id == course_id,
    ).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not enrolled in this course.",
        )

    try:
        recs = get_recommendations_for_student(
            db=db,
            student_id=student_id,
            course_id=course_id,
            limit=limit,
            refresh=refresh,
        )
        return [RecommendationResponse.model_validate(r) for r in recs]
    except Exception as e:
        logger.exception("Failed to generate recommendations: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        )
