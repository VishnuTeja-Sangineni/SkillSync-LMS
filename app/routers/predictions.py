"""
Predictions router: student performance predictions and at-risk student queries.

Endpoints:
- GET /predictions/student/{student_id}/course/{course_id}:
    Predict final score and risk level for a student with top-3 factors explained.
- GET /predictions/at-risk/course/{course_id}:
    List all enrolled students sorted by risk level with suggested teacher interventions.
"""

import logging
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course
from app.models.progress import Enrollment
from app.schemas.prediction import (
    PredictionResponse,
    PredictionNotReady,
    AtRiskStudentResponse,
)
from app.security import get_current_user
from ml.predict import predict_student_performance, get_at_risk_students_for_course

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get(
    "/student/{student_id}/course/{course_id}",
    response_model=Union[PredictionResponse, PredictionNotReady],
)
def get_student_prediction(
    student_id: int,
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get or generate predicted final score and risk level for a student in a course.
    Students can only view their own prediction.
    Teachers can view predictions for students in courses they teach.
    Admins can view any prediction.
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
            detail="You can only access your own performance predictions.",
        )

    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view predictions for courses you teach.",
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

    prediction = predict_student_performance(db, student_id=student_id, course_id=course_id)
    if prediction is None:
        return PredictionNotReady(
            status="not_ready",
            message="Performance prediction model is not trained yet. Please ask an administrator to trigger retraining.",
        )

    return PredictionResponse.model_validate(prediction)


@router.get(
    "/at-risk/course/{course_id}",
    response_model=List[AtRiskStudentResponse],
)
def get_at_risk_students_endpoint(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve all enrolled students in a course ranked by risk level
    (High -> Medium -> Low), including plain-language explanations and
    suggested interventions.
    Restricted to the course's teacher or platform admin.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if current_user.role == "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot view class at-risk reports.",
        )

    if current_user.role == "teacher" and course.teacher_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view at-risk reports for courses you teach.",
        )

    students_at_risk, is_ready = get_at_risk_students_for_course(db, course_id=course_id)
    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction model is not trained yet. Please ask an administrator to trigger retraining.",
        )

    return [AtRiskStudentResponse(**item) for item in students_at_risk]
