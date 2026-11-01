"""
Courses router: CRUD operations for courses and modules, plus student enrollment.

Permissions:
- Listing and viewing courses: all authenticated users
- Creating, updating, deleting courses/modules: teacher (owner) or admin
- Enrolling: student or admin
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.course import Course, Module, Lesson
from app.models.progress import Enrollment
from app.schemas.course import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseDetailResponse,
    ModuleCreate,
    ModuleUpdate,
    ModuleResponse,
)
from app.schemas.progress import EnrollmentResponse
from app.services.cleanup import purge_course, purge_module
from app.schemas.user import UserResponse
from app.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["courses"])


def _check_course_ownership(course: Course, user: User):
    """Ensure the user is the course's teacher or an admin."""
    if user.role != "admin" and course.teacher_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this course.",
        )


# ── Courses CRUD ───────────────────────────────────────────────────────

@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    data: CourseCreate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Create a new course (teacher or admin)."""
    course = Course(
        title=data.title,
        description=data.description,
        teacher_id=current_user.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    logger.info("Course created: %s (id=%d) by user %d", course.title, course.id, current_user.id)
    return CourseResponse.model_validate(course)


@router.get("", response_model=List[CourseResponse])
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all available courses."""
    courses = db.query(Course).all()
    return [CourseResponse.model_validate(c) for c in courses]


@router.get("/enrolled", response_model=List[CourseResponse])
def list_enrolled_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List courses the current user is enrolled in."""
    enrollments = db.query(Enrollment).filter(Enrollment.student_id == current_user.id).all()
    course_ids = [e.course_id for e in enrollments]
    courses = db.query(Course).filter(Course.id.in_(course_ids)).all() if course_ids else []
    return [CourseResponse.model_validate(c) for c in courses]


@router.get("/{course_id}", response_model=CourseDetailResponse)
def get_course_detail(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full details of a course including modules and lessons."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return CourseDetailResponse.model_validate(course)


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    data: CourseUpdate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Update course title or description (owner teacher or admin)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    if data.title is not None:
        course.title = data.title
    if data.description is not None:
        course.description = data.description

    db.commit()
    db.refresh(course)
    logger.info("Course updated: id=%d by user %d", course.id, current_user.id)
    return CourseResponse.model_validate(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Delete a course (owner teacher or admin)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    purge_course(db, course_id)
    db.commit()
    logger.info("Course deleted: id=%d by user %d", course_id, current_user.id)


# ── Enrollment ─────────────────────────────────────────────────────────

@router.post("/{course_id}/enroll", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def enroll_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enroll the current user in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Check if already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == course_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already enrolled in this course.",
        )

    enrollment = Enrollment(
        student_id=current_user.id,
        course_id=course_id,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    logger.info("User %d enrolled in course %d", current_user.id, course_id)
    return EnrollmentResponse.model_validate(enrollment)


@router.get("/{course_id}/students", response_model=List[UserResponse])
def list_enrolled_students(
    course_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """List all students enrolled in a course (teacher or admin)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    student_ids = [e.student_id for e in enrollments]
    students = db.query(User).filter(User.id.in_(student_ids)).all() if student_ids else []
    return [UserResponse.model_validate(s) for s in students]


# ── Modules Management ─────────────────────────────────────────────────

@router.post("/{course_id}/modules", response_model=ModuleResponse, status_code=status.HTTP_201_CREATED)
def create_module(
    course_id: int,
    data: ModuleCreate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Add a module to a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    module = Module(
        course_id=course_id,
        title=data.title,
        order=data.order,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    logger.info("Module created: id=%d in course %d", module.id, course_id)
    return ModuleResponse.model_validate(module)


@router.patch("/{course_id}/modules/{module_id}", response_model=ModuleResponse)
def update_module(
    course_id: int,
    module_id: int,
    data: ModuleUpdate,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Update module title or ordering."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    module = db.query(Module).filter(Module.id == module_id, Module.course_id == course_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    if data.title is not None:
        module.title = data.title
    if data.order is not None:
        module.order = data.order

    db.commit()
    db.refresh(module)
    return ModuleResponse.model_validate(module)


@router.delete("/{course_id}/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    course_id: int,
    module_id: int,
    current_user: User = Depends(require_role("teacher", "admin")),
    db: Session = Depends(get_db),
):
    """Delete a module and all its lessons."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    _check_course_ownership(course, current_user)

    module = db.query(Module).filter(Module.id == module_id, Module.course_id == course_id).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    purge_module(db, module_id)
    db.commit()
    logger.info("Module deleted: id=%d from course %d", module_id, course_id)
