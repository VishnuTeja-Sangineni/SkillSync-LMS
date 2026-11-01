"""
Prediction and model explanation engine.

Loads trained model artifacts via ModelStorage, generates final score predictions
(0–100) and risk levels (Low/Medium/High), and produces plain-English explanations
of the top 3 factors driving each prediction.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.course import Course
from app.models.progress import Enrollment
from app.models.prediction import Prediction
from ml.features import FEATURE_NAMES, extract_features
from ml.storage import get_storage
from ml.train import score_to_risk

logger = logging.getLogger(__name__)

# Cache loaded artifact in-memory so subsequent requests don't re-read disk/S3
_MODEL_CACHE: Optional[Dict[str, Any]] = None
_CACHED_PATH: Optional[str] = None


def load_model(model_path: Optional[str] = None, force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """
    Load the trained model artifact.
    Returns None if no model has been trained yet (graceful degradation).
    """
    global _MODEL_CACHE, _CACHED_PATH

    target_path = model_path or settings.MODEL_PATH

    if not force_reload and _MODEL_CACHE is not None and _CACHED_PATH == target_path:
        return _MODEL_CACHE

    storage = get_storage()
    if not storage.exists(target_path):
        logger.warning("No model found at %s. Prediction will degrade gracefully.", target_path)
        return None

    try:
        artifact = storage.load(target_path)
        _MODEL_CACHE = artifact
        _CACHED_PATH = target_path
        return artifact
    except Exception as e:
        logger.error("Error loading model from %s: %s", target_path, e)
        return None


def invalidate_model_cache():
    """Clear in-memory cached model (e.g. after retraining)."""
    global _MODEL_CACHE, _CACHED_PATH
    _MODEL_CACHE = None
    _CACHED_PATH = None


def explain_prediction(features: Dict[str, float], artifact: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Produce plain-English explanations for the top 3 factors affecting this student.

    Combines global feature importances with local student-specific deviations
    to identify the most influential factors.
    """
    # Detect newly enrolled student with zero coursework activity
    if (
        features.get("attempt_count", 0) == 0
        and features.get("total_time_spent", 0) == 0
        and features.get("lessons_completion_pct", 0) == 0
    ):
        return [
            {
                "factor": "new_enrollment",
                "impact": "neutral",
                "description": "Newly enrolled — baseline estimate awaiting first study activity",
            },
            {
                "factor": "attempt_count",
                "impact": "neutral",
                "description": "No quiz attempts yet to evaluate specific topic mastery",
            },
            {
                "factor": "total_time_spent",
                "impact": "neutral",
                "description": "Begin Module 1 lessons to generate a personalized prediction",
            },
        ]

    feature_importances = artifact.get("feature_importances", {})
    feature_stats = artifact.get("feature_stats", {})

    ranked_factors = []

    for feat in FEATURE_NAMES:
        val = features.get(feat, 0.0)
        global_imp = feature_importances.get(feat, 0.01)
        stats = feature_stats.get(feat, {"mean": 50.0, "std": 10.0})
        mean = stats.get("mean", 50.0)
        std = stats.get("std", 1.0)
        if std <= 0:
            std = 1.0

        # Z-score indicates how far this student is from the class average
        z_score = (val - mean) / std

        # Generate descriptive factor explanation
        description = ""
        impact = "neutral"

        if feat == "avg_quiz_score":
            if val >= 75:
                impact = "positive"
                description = f"Strong quiz performance with an average score of {val:.1f}%"
            elif val < 50:
                impact = "negative"
                description = f"Low average quiz score of {val:.1f}%, below course benchmark"
            else:
                impact = "neutral"
                description = f"Moderate average quiz score of {val:.1f}%"

        elif feat == "total_time_spent":
            hours = round(val / 3600.0, 1)
            if val >= mean:
                impact = "positive"
                description = f"High study commitment with {hours} hours spent on course material"
            elif val < mean * 0.5:
                impact = "negative"
                description = f"Limited study time with only {hours} hours recorded"
            else:
                impact = "neutral"
                description = f"Moderate study time with {hours} hours recorded"

        elif feat == "avg_mastery":
            pct = round(val * 100.0, 1)
            if val >= 0.7:
                impact = "positive"
                description = f"High overall topic mastery across the curriculum ({pct}%)"
            elif val < 0.45:
                impact = "negative"
                description = f"Low topic mastery ({pct}%), indicating foundational knowledge gaps"
            else:
                impact = "neutral"
                description = f"Moderate topic mastery across topics ({pct}%)"

        elif feat == "lessons_completion_pct":
            if val >= 80:
                impact = "positive"
                description = f"Completed {val:.1f}% of course lessons"
            elif val < 50:
                impact = "negative"
                description = f"Low lesson completion rate of only {val:.1f}%"
            else:
                impact = "neutral"
                description = f"Progressing through lessons ({val:.1f}% completed)"

        elif feat == "days_since_last_activity":
            days = int(val)
            if days >= 7:
                impact = "negative"
                description = f"Inactive for {days} days since last learning session"
            elif days <= 2:
                impact = "positive"
                description = f"Active recently within the last {days} days"
            else:
                impact = "neutral"
                description = f"{days} days since last activity"

        elif feat == "score_trend":
            if val > 0.5:
                impact = "positive"
                description = "Consistently improving quiz scores over recent attempts"
            elif val < -0.5:
                impact = "negative"
                description = "Declining quiz score trend over recent attempts"
            else:
                impact = "neutral"
                description = "Stable performance across quiz attempts"

        elif feat == "weakest_mastery":
            pct = round(val * 100.0, 1)
            if val < 0.4:
                impact = "negative"
                description = f"Struggling in weakest topic with only {pct}% mastery"
            else:
                impact = "neutral"
                description = f"Weakest topic is maintained at {pct}% mastery"

        elif feat == "days_active_14":
            days = int(val)
            if days >= 7:
                impact = "positive"
                description = f"Highly active ({days} out of the last 14 days)"
            elif days <= 1:
                impact = "negative"
                description = f"Low engagement ({days} active days in last 14)"
            else:
                impact = "neutral"
                description = f"Moderate engagement ({days} active days in last 14)"

        elif feat == "attempt_count":
            cnt = int(val)
            if cnt >= 4:
                impact = "positive"
                description = f"High practice volume with {cnt} quiz attempts"
            elif cnt <= 1:
                impact = "negative"
                description = f"Minimal quiz practice ({cnt} attempt so far)"
            else:
                impact = "neutral"
                description = f"Regular quiz practice ({cnt} attempts)"

        else:
            description = f"{feat.replace('_', ' ').capitalize()} is {val:.2f}"

        # Combined weight: global importance * local deviation magnitude
        # We add 0.5 so highly important features are kept even if deviation is small
        combined_score = global_imp * (1.0 + abs(z_score))
        ranked_factors.append((combined_score, {"factor": feat, "impact": impact, "description": description}))

    # Sort descending by combined score and take top 3
    ranked_factors.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in ranked_factors[:3]]


def predict_student_performance(
    db: Session,
    student_id: int,
    course_id: int,
    artifact: Optional[Dict[str, Any]] = None,
) -> Optional[Prediction]:
    """
    Predict final course score and risk level for a student, persist to DB,
    and return the Prediction model instance.

    Returns None if no model is loaded.
    """
    if artifact is None:
        artifact = load_model()
    if artifact is None:
        return None

    model = artifact["model"]

    # Extract features for this student-course pair
    features = extract_features(db, student_id=student_id, course_id=course_id)
    df_X = pd.DataFrame([features], columns=FEATURE_NAMES)

    pred_score = float(np.clip(model.predict(df_X)[0], 0.0, 100.0))
    risk_level = score_to_risk(pred_score)
    top_factors = explain_prediction(features, artifact)

    # Persist or update Prediction in database
    prediction = (
        db.query(Prediction)
        .filter(
            Prediction.student_id == student_id,
            Prediction.course_id == course_id,
        )
        .first()
    )

    now = datetime.now(timezone.utc)
    if prediction:
        prediction.predicted_score = round(pred_score, 1)
        prediction.risk_level = risk_level
        prediction.top_factors_json = top_factors
        prediction.created_at = now
    else:
        prediction = Prediction(
            student_id=student_id,
            course_id=course_id,
            predicted_score=round(pred_score, 1),
            risk_level=risk_level,
            top_factors_json=top_factors,
            created_at=now,
        )
        db.add(prediction)

    db.commit()
    db.refresh(prediction)
    return prediction


def determine_suggested_intervention(risk_level: str, features: Dict[str, float]) -> str:
    """Generate a contextual suggested intervention for teachers."""
    if (
        features.get("attempt_count", 0) == 0
        and features.get("total_time_spent", 0) == 0
        and features.get("lessons_completion_pct", 0) == 0
    ):
        return "Newly enrolled student — send welcome orientation and encourage starting Module 1"

    if risk_level == "High":
        if features.get("days_since_last_activity", 0) >= 7:
            return "Send re-engagement reminder and schedule a 1-on-1 check-in"
        elif features.get("weakest_mastery", 1.0) < 0.4:
            return "Assign foundational remediation lessons and easy practice quizzes on weak topics"
        elif features.get("lessons_completion_pct", 100) < 40:
            return "Require completion of prerequisite lessons before next assessment"
        else:
            return "Provide targeted tutor assistance and structured review materials"
    elif risk_level == "Medium":
        if features.get("weakest_mastery", 1.0) < 0.5:
            return "Recommend targeted practice on weakest topics to build mastery"
        else:
            return "Encourage regular weekly study sessions and medium-difficulty quizzes"
    else:
        return "Student is progressing well; recommend advanced challenge questions or peer mentoring"


def get_at_risk_students_for_course(
    db: Session,
    course_id: int,
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Return all enrolled students in a course, sorted by risk level
    (High -> Medium -> Low) and predicted score ascending.

    Returns:
        (list of student risk summaries, is_model_ready: bool)
    """
    artifact = load_model()
    if artifact is None:
        return [], False

    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    if not enrollments:
        return [], True

    results = []
    risk_rank = {"High": 0, "Medium": 1, "Low": 2}

    for enr in enrollments:
        student = db.query(User).filter(User.id == enr.student_id).first()
        if not student:
            continue

        pred = predict_student_performance(db, student_id=student.id, course_id=course_id, artifact=artifact)
        features = extract_features(db, student_id=student.id, course_id=course_id)

        intervention = determine_suggested_intervention(pred.risk_level, features)

        results.append({
            "student_id": student.id,
            "student_name": student.name,
            "student_email": student.email,
            "course_id": course_id,
            "predicted_score": pred.predicted_score,
            "risk_level": pred.risk_level,
            "top_factors": pred.top_factors_json,
            "suggested_intervention": intervention,
            "_risk_order": risk_rank.get(pred.risk_level, 3),
        })

    # Sort: High risk first, then lowest predicted score
    results.sort(key=lambda x: (x["_risk_order"], x["predicted_score"]))

    for item in results:
        del item["_risk_order"]

    return results, True
