"""Pydantic schemas for predictions and recommendations."""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class PredictionResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    predicted_score: float
    risk_level: str
    top_factors_json: Optional[Any] = None
    created_at: datetime
    model_config = {"from_attributes": True}

class PredictionNotReady(BaseModel):
    status: str = "not_ready"
    message: str = "Not enough data or model not trained yet."


class AtRiskStudentResponse(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    course_id: int
    predicted_score: float
    risk_level: str
    top_factors: Optional[Any] = None
    suggested_intervention: str


class RetrainResponse(BaseModel):
    status: str
    samples: int
    metrics: dict
    feature_importances: dict
    trained_at: str
    model_path: str


class RecommendationResponse(BaseModel):
    id: int
    student_id: int
    course_id: int
    type: str
    target_id: Optional[int]
    reason: str
    priority: int
    created_at: datetime
    model_config = {"from_attributes": True}
