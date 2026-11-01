"""Pydantic schemas for courses, modules, and lessons."""

from typing import Optional, List
from pydantic import BaseModel, Field


class LessonCreate(BaseModel):
    module_id: int
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""
    topic: str = Field(default="general", max_length=100)
    est_minutes: int = Field(default=10, ge=1)
    order: int = Field(default=0, ge=0)


class LessonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    est_minutes: Optional[int] = Field(None, ge=1)
    order: Optional[int] = Field(None, ge=0)


class LessonResponse(BaseModel):
    id: int
    module_id: int
    title: str
    content: str
    topic: str
    est_minutes: int
    order: int

    model_config = {"from_attributes": True}


class ModuleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    order: int = Field(default=0, ge=0)


class ModuleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    order: Optional[int] = Field(None, ge=0)


class ModuleResponse(BaseModel):
    id: int
    course_id: int
    title: str
    order: int
    lessons: List[LessonResponse] = []

    model_config = {"from_attributes": True}


class CourseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int

    model_config = {"from_attributes": True}


class CourseDetailResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int
    modules: List[ModuleResponse] = []

    model_config = {"from_attributes": True}
