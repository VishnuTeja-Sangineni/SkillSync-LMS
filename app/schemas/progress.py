"""Pydantic schemas for progress tracking."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EnrollmentCreate(BaseModel):
    course_id: int

class EnrollmentResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    enrolled_at: datetime
    model_config = {"from_attributes": True}


class LessonProgressUpdate(BaseModel):
    lesson_id: int
    completed: bool = False
    time_spent_sec: int = Field(default=0, ge=0)

class LessonProgressResponse(BaseModel):
    id: int
    student_id: int
    lesson_id: int
    completed: bool
    time_spent_sec: int
    last_visited: datetime
    model_config = {"from_attributes": True}
