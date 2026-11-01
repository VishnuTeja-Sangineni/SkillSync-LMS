"""Tests for Phase 5: ML performance prediction, storage abstraction, and explanation."""

import os
import pytest
from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import Enrollment, QuizAttempt, AttemptAnswer, TopicMastery, LessonProgress
from app.models.grade import FinalGrade
from ml.storage import LocalFileStorage
from ml.features import extract_features, FEATURE_NAMES
from ml.train import train_model, score_to_risk
from ml.predict import (
    load_model,
    predict_student_performance,
    explain_prediction,
    get_at_risk_students_for_course,
)


def test_local_storage_lifecycle(tmp_path):
    """LocalFileStorage saves, verifies existence, and loads Python objects."""
    storage = LocalFileStorage()
    target = str(tmp_path / "subdir" / "test_model.joblib")

    assert storage.exists(target) is False
    with pytest.raises(FileNotFoundError):
        storage.load(target)

    data = {"weights": [1.0, 2.0, 3.0], "version": "1.0"}
    storage.save(data, target)

    assert storage.exists(target) is True
    loaded = storage.load(target)
    assert loaded["version"] == "1.0"
    assert loaded["weights"] == [1.0, 2.0, 3.0]


def test_score_to_risk_thresholds():
    """Verify threshold mappings (>=70 Low, 50-70 Medium, <50 High)."""
    assert score_to_risk(95.0) == "Low"
    assert score_to_risk(70.0) == "Low"
    assert score_to_risk(69.9) == "Medium"
    assert score_to_risk(50.0) == "Medium"
    assert score_to_risk(49.9) == "High"
    assert score_to_risk(12.0) == "High"


def test_feature_extraction_empty_student(db_session, test_student, test_course):
    """Features extract cleanly with defaults when student has zero activity."""
    feats = extract_features(db_session, test_student.id, test_course.id)

    assert len(feats) == len(FEATURE_NAMES)
    for name in FEATURE_NAMES:
        assert name in feats

    assert feats["avg_quiz_score"] == 0.0
    assert feats["attempt_count"] == 0.0
    assert feats["total_time_spent"] == 0.0
    assert feats["lessons_completion_pct"] == 0.0


def test_train_model_pipeline(db_session, test_course, tmp_path):
    """Train pipeline fits model, evaluates metrics, and outputs feature importances."""
    from app.models.user import User

    # Create synthetic training set of 12 students with final grades
    for i in range(12):
        u = User(
            name=f"ML Student {i}",
            email=f"ml_student_{i}@test.com",
            password_hash="hash",
            role="student",
        )
        db_session.add(u)
        db_session.commit()

        db_session.add(Enrollment(student_id=u.id, course_id=test_course.id))
        db_session.add(TopicMastery(student_id=u.id, course_id=test_course.id, topic="math", mastery=0.1 * i))
        db_session.add(FinalGrade(student_id=u.id, course_id=test_course.id, final_score=30.0 + 5.0 * i))

    db_session.commit()

    model_file = str(tmp_path / "model.joblib")
    res = train_model(db=db_session, save=True, model_path=model_file)

    assert res["status"] == "success"
    assert res["samples"] >= 12
    assert "mae" in res["metrics"]
    assert "r2" in res["metrics"]
    assert len(res["feature_importances"]) == len(FEATURE_NAMES)
    assert os.path.exists(model_file)


def test_predict_and_explain_student(db_session, test_student, test_course, tmp_path):
    """Student prediction returns score, risk level, and 3 plain-English factors."""
    from app.models.user import User

    # Setup training data and train model
    for i in range(15):
        u = User(name=f"User {i}", email=f"user_{i}@test.com", password_hash="hash", role="student")
        db_session.add(u)
        db_session.commit()
        db_session.add(Enrollment(student_id=u.id, course_id=test_course.id))
        db_session.add(TopicMastery(student_id=u.id, course_id=test_course.id, topic="general", mastery=0.05 * i))
        db_session.add(FinalGrade(student_id=u.id, course_id=test_course.id, final_score=20.0 + 4.5 * i))

    db_session.commit()

    model_file = str(tmp_path / "test_predict_model.joblib")
    train_model(db=db_session, save=True, model_path=model_file)

    # Enroll test_student
    db_session.add(Enrollment(student_id=test_student.id, course_id=test_course.id))
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="general", mastery=0.9))
    db_session.commit()

    artifact = load_model(model_path=model_file, force_reload=True)
    pred = predict_student_performance(db_session, test_student.id, test_course.id, artifact=artifact)

    assert pred is not None
    assert 0.0 <= pred.predicted_score <= 100.0
    assert pred.risk_level in ("Low", "Medium", "High")
    assert len(pred.top_factors_json) == 3
    for factor in pred.top_factors_json:
        assert "factor" in factor
        assert "description" in factor
        assert len(factor["description"]) > 5


def test_prediction_api_endpoints(
    client,
    auth_headers_student,
    auth_headers_teacher,
    auth_headers_admin,
    test_student,
    test_course,
    db_session,
    tmp_path,
):
    """End-to-end API tests for student prediction and class at-risk endpoint."""
    from app.models.user import User

    # 1. Setup training data & train
    for i in range(15):
        u = User(name=f"T Student {i}", email=f"ts_{i}@test.com", password_hash="hash", role="student")
        db_session.add(u)
        db_session.commit()
        db_session.add(Enrollment(student_id=u.id, course_id=test_course.id))
        db_session.add(TopicMastery(student_id=u.id, course_id=test_course.id, topic="cs", mastery=0.06 * i))
        db_session.add(FinalGrade(student_id=u.id, course_id=test_course.id, final_score=25.0 + 4.0 * i))

    db_session.commit()
    train_model(db=db_session, save=True)

    # 2. Enroll student
    client.post(f"/api/v1/courses/{test_course.id}/enroll", headers=auth_headers_student)

    # 3. Student fetches own prediction
    resp = client.get(
        f"/api/v1/predictions/student/{test_student.id}/course/{test_course.id}",
        headers=auth_headers_student,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == test_student.id
    assert "predicted_score" in data
    assert "risk_level" in data
    assert len(data["top_factors_json"]) == 3

    # 4. Student cannot view at-risk class report
    resp_student_at_risk = client.get(
        f"/api/v1/predictions/at-risk/course/{test_course.id}",
        headers=auth_headers_student,
    )
    assert resp_student_at_risk.status_code == 403

    # 5. Teacher of course fetches at-risk report
    resp_teacher_at_risk = client.get(
        f"/api/v1/predictions/at-risk/course/{test_course.id}",
        headers=auth_headers_teacher,
    )
    assert resp_teacher_at_risk.status_code == 200
    report = resp_teacher_at_risk.json()
    assert len(report) >= 1
    assert "suggested_intervention" in report[0]
    assert "risk_level" in report[0]

    # 6. Admin triggers retrain
    retrain_resp = client.post("/api/v1/admin/retrain", headers=auth_headers_admin)
    assert retrain_resp.status_code == 200
    retrain_data = retrain_resp.json()
    assert retrain_data["status"] == "success"
    assert "metrics" in retrain_data

    # 7. Student forbidden from retraining
    forbidden_retrain = client.post("/api/v1/admin/retrain", headers=auth_headers_student)
    assert forbidden_retrain.status_code == 403


def test_prediction_graceful_degradation_without_model(
    client,
    auth_headers_student,
    test_student,
    test_course,
    monkeypatch,
):
    """When model artifact does not exist, prediction endpoint degrades gracefully."""
    # Enroll student
    client.post(f"/api/v1/courses/{test_course.id}/enroll", headers=auth_headers_student)

    # Point to nonexistent model
    monkeypatch.setattr("app.config.settings.MODEL_PATH", "nonexistent/path/model.joblib")
    from ml.predict import invalidate_model_cache
    invalidate_model_cache()

    resp = client.get(
        f"/api/v1/predictions/student/{test_student.id}/course/{test_course.id}",
        headers=auth_headers_student,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_ready"
    assert "not trained yet" in data["message"].lower()

