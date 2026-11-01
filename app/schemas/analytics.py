"""Pydantic schemas for student and course analytics."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class TopicMasteryItem(BaseModel):
    topic: str
    course_id: int
    raw_mastery: float
    mastery: float  # With forgetting decay applied
    updated_at: datetime


class QuizAttemptSummary(BaseModel):
    attempt_id: int
    quiz_id: int
    quiz_title: str
    score: float
    max_score: float
    percentage: float
    duration_sec: Optional[int] = 0
    date: datetime


class ScoreTrend(BaseModel):
    slope: float
    direction: str  # improving, stable, declining
    attempts: List[QuizAttemptSummary] = []


class StudentAnalyticsResponse(BaseModel):
    student_id: int
    student_name: str
    course_id: Optional[int] = None
    mastery_by_topic: List[TopicMasteryItem] = []
    score_trend: ScoreTrend
    total_time_spent_sec: int
    streak_days: int
    weak_areas: List[str] = []
    completed_lessons_count: int = 0
    total_lessons_count: int = 0


class TopicAvgMastery(BaseModel):
    topic: str
    avg_mastery: float
    student_count: int


class ScoreDistributionBin(BaseModel):
    bin: str
    count: int
    percentage: float


class DailyEngagement(BaseModel):
    date: str
    active_students: int


class CourseAnalyticsResponse(BaseModel):
    course_id: int
    course_title: str
    total_enrolled: int
    avg_completion_pct: float
    topic_masteries: List[TopicAvgMastery] = []
    score_distribution: List[ScoreDistributionBin] = []
    engagement_over_time: List[DailyEngagement] = []
