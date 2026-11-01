"""
Feature engineering for the ML prediction pipeline.

Extracts 10 features per (student, course) pair from the database:

 1. avg_quiz_score       — mean of (score / max_score) across attempts
 2. score_trend          — linear-regression slope of scores over time
 3. avg_mastery          — mean of all topic masteries
 4. weakest_mastery      — minimum topic mastery
 5. lessons_completion_pct — completed lessons / total lessons in course
 6. total_time_spent     — sum of quiz durations + lesson time (seconds)
 7. days_active_14       — count of distinct active days in last 14 days
 8. avg_time_per_question — mean time per answered question (seconds)
 9. attempt_count        — total number of quiz attempts
10. days_since_last_activity — days since the most recent action

All features are rounded to 4 decimal places for consistency.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz
from app.models.progress import (
    Enrollment,
    QuizAttempt,
    AttemptAnswer,
    LessonProgress,
    TopicMastery,
)

logger = logging.getLogger(__name__)

FEATURE_NAMES = [
    "avg_quiz_score",
    "score_trend",
    "avg_mastery",
    "weakest_mastery",
    "lessons_completion_pct",
    "total_time_spent",
    "days_active_14",
    "avg_time_per_question",
    "attempt_count",
    "days_since_last_activity",
]

# Human-readable descriptions keyed by feature name
FEATURE_DESCRIPTIONS = {
    "avg_quiz_score": "average quiz score",
    "score_trend": "score trend over time",
    "avg_mastery": "average topic mastery",
    "weakest_mastery": "weakest topic mastery",
    "lessons_completion_pct": "lesson completion rate",
    "total_time_spent": "total study time",
    "days_active_14": "recent activity (last 14 days)",
    "avg_time_per_question": "average time per question",
    "attempt_count": "number of quiz attempts",
    "days_since_last_activity": "days since last activity",
}


def extract_features(
    db: Session,
    student_id: int,
    course_id: int,
    reference_time: Optional[datetime] = None,
) -> Dict[str, float]:
    """
    Extract a feature dict for one (student, course) pair.

    Args:
        db: SQLAlchemy session.
        student_id: The student's user ID.
        course_id: The course ID.
        reference_time: "now" for relative calculations (defaults to UTC now).

    Returns:
        Dict mapping each of the 10 feature names to a float value.
    """
    now = reference_time or datetime.now(timezone.utc)

    # ── 1. Quiz attempts ──────────────────────────────────────────────
    attempts: List[QuizAttempt] = (
        db.query(QuizAttempt)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(
            Quiz.course_id == course_id,
            QuizAttempt.student_id == student_id,
            QuizAttempt.max_score > 0,
        )
        .order_by(QuizAttempt.started_at.asc())
        .all()
    )

    percentages = []
    total_quiz_time = 0
    active_dates: set = set()

    for att in attempts:
        percentages.append(att.score / att.max_score * 100.0)
        total_quiz_time += att.duration_sec or 0
        if att.started_at:
            d = att.started_at
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            active_dates.add(d.date())

    avg_quiz_score = round(float(np.mean(percentages)), 4) if percentages else 0.0

    # Score trend (slope via linear regression)
    n = len(percentages)
    if n >= 2:
        x = np.arange(n, dtype=float)
        y = np.array(percentages, dtype=float)
        x_mean = x.mean()
        y_mean = y.mean()
        denom = float(np.sum((x - x_mean) ** 2))
        numer = float(np.sum((x - x_mean) * (y - y_mean)))
        score_trend = round(numer / denom, 4) if denom > 0 else 0.0
    else:
        score_trend = 0.0

    attempt_count = len(attempts)

    # ── 2. Topic mastery ──────────────────────────────────────────────
    masteries = (
        db.query(TopicMastery.mastery)
        .filter(
            TopicMastery.student_id == student_id,
            TopicMastery.course_id == course_id,
        )
        .all()
    )
    mastery_vals = [m[0] for m in masteries]
    avg_mastery = round(float(np.mean(mastery_vals)), 4) if mastery_vals else 0.0
    weakest_mastery = round(float(np.min(mastery_vals)), 4) if mastery_vals else 0.0

    # ── 3. Lesson completion ──────────────────────────────────────────
    total_lessons = (
        db.query(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .filter(Module.course_id == course_id)
        .count()
    )

    lesson_progress_records = (
        db.query(LessonProgress)
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .filter(
            Module.course_id == course_id,
            LessonProgress.student_id == student_id,
        )
        .all()
    )

    completed_count = sum(1 for lp in lesson_progress_records if lp.completed)
    lessons_completion_pct = (
        round(completed_count / total_lessons * 100.0, 4)
        if total_lessons > 0
        else 0.0
    )

    total_lesson_time = sum(lp.time_spent_sec for lp in lesson_progress_records)
    for lp in lesson_progress_records:
        if lp.last_visited:
            d = lp.last_visited
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            active_dates.add(d.date())

    total_time_spent = float(total_quiz_time + total_lesson_time)

    # ── 4. Days active in last 14 ─────────────────────────────────────
    cutoff = (now.date() - timedelta(days=14)) if hasattr(now, "date") else now
    days_active_14 = float(sum(1 for d in active_dates if d >= cutoff))

    # ── 5. Average time per question ──────────────────────────────────
    attempt_ids = [a.id for a in attempts]
    if attempt_ids:
        answers = (
            db.query(AttemptAnswer.time_taken_sec)
            .filter(AttemptAnswer.attempt_id.in_(attempt_ids))
            .all()
        )
        times = [a[0] for a in answers if a[0] is not None and a[0] > 0]
        avg_time_per_question = round(float(np.mean(times)), 4) if times else 0.0
    else:
        avg_time_per_question = 0.0

    # ── 6. Days since last activity ───────────────────────────────────
    if active_dates:
        most_recent = max(active_dates)
        days_since_last_activity = float((now.date() - most_recent).days)
    else:
        days_since_last_activity = 999.0  # sentinel: no activity recorded

    return {
        "avg_quiz_score": avg_quiz_score,
        "score_trend": score_trend,
        "avg_mastery": avg_mastery,
        "weakest_mastery": weakest_mastery,
        "lessons_completion_pct": lessons_completion_pct,
        "total_time_spent": total_time_spent,
        "days_active_14": days_active_14,
        "avg_time_per_question": avg_time_per_question,
        "attempt_count": float(attempt_count),
        "days_since_last_activity": days_since_last_activity,
    }


def build_training_dataset(
    db: Session,
) -> Tuple[List[Dict[str, float]], List[float], List[Tuple[int, int]]]:
    """
    Build (features, labels, ids) from FinalGrade + activity data for every
    enrolled student that has a recorded final grade.

    Returns:
        features: list of feature dicts (one per student-course pair)
        labels:   list of final scores (0–100)
        ids:      list of (student_id, course_id) tuples
    """
    from app.models.grade import FinalGrade

    grades = db.query(FinalGrade).all()
    features: List[Dict[str, float]] = []
    labels: List[float] = []
    ids: List[Tuple[int, int]] = []

    for g in grades:
        feat = extract_features(db, g.student_id, g.course_id)
        features.append(feat)
        labels.append(g.final_score)
        ids.append((g.student_id, g.course_id))

    logger.info("Built training dataset: %d samples", len(features))
    return features, labels, ids
