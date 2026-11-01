"""Pydantic schemas for quizzes and questions."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator


class QuestionCreate(BaseModel):
    course_id: int
    topic: str = Field(..., min_length=1, max_length=100)
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    text: str = Field(..., min_length=1)
    options_json: List[str] = Field(..., min_length=2)
    correct_index: int = Field(..., ge=0)

    @model_validator(mode="after")
    def validate_correct_index(self):
        if self.correct_index >= len(self.options_json):
            raise ValueError(
                f"correct_index ({self.correct_index}) must be less than options length ({len(self.options_json)})"
            )
        return self


class QuestionUpdate(BaseModel):
    topic: Optional[str] = Field(None, min_length=1, max_length=100)
    difficulty: Optional[str] = Field(None, pattern="^(easy|medium|hard)$")
    text: Optional[str] = Field(None, min_length=1)
    options_json: Optional[List[str]] = Field(None, min_length=2)
    correct_index: Optional[int] = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_correct_index(self):
        if self.options_json is not None and self.correct_index is not None:
            if self.correct_index >= len(self.options_json):
                raise ValueError("correct_index must be less than options length")
        return self


class QuestionResponse(BaseModel):
    id: int
    course_id: int
    topic: str
    difficulty: str
    text: str
    options_json: list
    correct_index: int

    model_config = {"from_attributes": True}


class QuestionStudentResponse(BaseModel):
    """Question response for students — hides the correct answer."""
    id: int
    course_id: int
    topic: str
    difficulty: str
    text: str
    options_json: list

    model_config = {"from_attributes": True}


class QuizCreate(BaseModel):
    course_id: int
    module_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    question_ids: List[int] = []


class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    module_id: Optional[int] = None
    question_ids: Optional[List[int]] = None


class QuizResponse(BaseModel):
    id: int
    course_id: int
    module_id: Optional[int]
    title: str

    model_config = {"from_attributes": True}


class QuizDetailResponse(BaseModel):
    id: int
    course_id: int
    module_id: Optional[int]
    title: str
    questions: List[QuestionResponse] = []

    model_config = {"from_attributes": True}


class QuizStartResponse(BaseModel):
    attempt_id: int
    quiz_id: int
    student_id: int
    started_at: datetime
    total_questions: int


class QuizNextQuestionResponse(BaseModel):
    question: Optional[QuestionStudentResponse] = None
    attempt_id: int
    question_number: int
    total_questions: int
    is_complete: bool


class QuizAnswerRequest(BaseModel):
    attempt_id: int
    question_id: int
    selected_index: int = Field(..., ge=0)
    time_taken_sec: Optional[int] = Field(default=0, ge=0)


class QuizAnswerResponse(BaseModel):
    is_correct: bool
    correct_index: int
    new_mastery: float
    topic: str
    difficulty: str


class QuizFinishRequest(BaseModel):
    attempt_id: int


class QuizFinishResponse(BaseModel):
    attempt_id: int
    quiz_id: int
    student_id: int
    score: float
    max_score: float
    percentage: float
    duration_sec: int
    finished_at: datetime

