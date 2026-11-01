"""Tests for Phase 6: Recommendation engine and API endpoints."""

from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import Enrollment, TopicMastery, LessonProgress, QuizAttempt
from app.models.prediction import Prediction
from recommender.engine import (
    compute_cosine_similarity,
    generate_rule_based_recommendations,
    generate_collaborative_recommendations,
    get_recommendations_for_student,
)


def test_cosine_similarity_math():
    """Cosine similarity handles identical, orthogonal, and zero vectors."""
    v1 = np.array([1.0, 2.0, 3.0])
    assert compute_cosine_similarity(v1, v1) == pytest.approx(1.0)

    v_orth1 = np.array([1.0, 0.0])
    v_orth2 = np.array([0.0, 1.0])
    assert compute_cosine_similarity(v_orth1, v_orth2) == pytest.approx(0.0)

    v_zero = np.array([0.0, 0.0])
    assert compute_cosine_similarity(v1, v_zero) == pytest.approx(0.0)


def test_rule_based_weak_and_strong_topics(db_session, test_student, test_course):
    """Rule-based engine suggests review for weak topics and challenge for strong topics."""
    # Module & lessons
    mod = Module(course_id=test_course.id, title="Module 1", order=1)
    db_session.add(mod)
    db_session.commit()

    les_weak = Lesson(module_id=mod.id, title="Basics of Algebra", content="...", topic="algebra", est_minutes=10, order=1)
    les_strong = Lesson(module_id=mod.id, title="Basics of Geometry", content="...", topic="geometry", est_minutes=10, order=2)
    db_session.add_all([les_weak, les_strong])
    db_session.commit()

    # Quizzes
    quiz_challenge = Quiz(course_id=test_course.id, title="Advanced Geometry Challenge")
    db_session.add(quiz_challenge)
    db_session.commit()

    q_hard = Question(
        course_id=test_course.id,
        topic="geometry",
        difficulty="hard",
        text="Hard question",
        options_json=["A", "B"],
        correct_index=0,
    )
    db_session.add(q_hard)
    db_session.commit()
    db_session.add(QuizQuestion(quiz_id=quiz_challenge.id, question_id=q_hard.id))

    # Topic masteries for student: weak in algebra (0.25), strong in geometry (0.85)
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="algebra", mastery=0.25))
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="geometry", mastery=0.85))
    db_session.commit()

    recs = generate_rule_based_recommendations(db_session, test_student.id, test_course.id)

    # Must contain remediation lesson for algebra
    types = [r["type"] for r in recs]
    assert "lesson" in types
    algebra_rec = next(r for r in recs if r["target_id"] == les_weak.id)
    assert "algebra" in algebra_rec["reason"].lower()
    assert algebra_rec["priority"] <= 2

    # Must contain challenge quiz for geometry
    geom_rec = next(r for r in recs if r["type"] == "quiz" and r["target_id"] == quiz_challenge.id)
    assert "geometry" in geom_rec["reason"].lower()
    assert geom_rec["priority"] >= 5


def test_rule_based_inactivity_action(db_session, test_student, test_course):
    """Students inactive for 5+ days receive a re-engagement nudge action."""
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=8)

    quiz = Quiz(course_id=test_course.id, title="Past Quiz")
    db_session.add(quiz)
    db_session.commit()

    att = QuizAttempt(
        student_id=test_student.id,
        quiz_id=quiz.id,
        score=5.0,
        max_score=10.0,
        started_at=old_date,
        finished_at=old_date,
    )
    db_session.add(att)
    db_session.commit()

    recs = generate_rule_based_recommendations(db_session, test_student.id, test_course.id)
    action_recs = [r for r in recs if r["type"] == "action"]

    assert len(action_recs) >= 1
    assert "haven't engaged" in action_recs[0]["reason"].lower() or "days" in action_recs[0]["reason"].lower()


def test_collaborative_filtering_peer_recommendation(db_session, test_student, test_course):
    """Collaborative filtering finds similar peers who improved and recommends their completed lessons."""
    from app.models.user import User

    # Create questions to define course topics
    q1 = Question(course_id=test_course.id, topic="python", difficulty="medium", text="Q1", options_json=["A", "B"], correct_index=0)
    q2 = Question(course_id=test_course.id, topic="sql", difficulty="medium", text="Q2", options_json=["A", "B"], correct_index=0)
    db_session.add_all([q1, q2])

    mod = Module(course_id=test_course.id, title="Mod", order=1)
    db_session.add(mod)
    db_session.commit()

    target_lesson = Lesson(module_id=mod.id, title="Deep SQL Joins", content="...", topic="sql", est_minutes=15, order=1)
    db_session.add(target_lesson)
    db_session.commit()

    # Enroll test student
    db_session.add(Enrollment(student_id=test_student.id, course_id=test_course.id))
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="python", mastery=0.6))
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="sql", mastery=0.4))

    # Peer student with similar vector who completed the target lesson
    peer = User(name="Peer Student", email="peer_collab@test.com", password_hash="hash", role="student")
    db_session.add(peer)
    db_session.commit()

    db_session.add(Enrollment(student_id=peer.id, course_id=test_course.id))
    db_session.add(TopicMastery(student_id=peer.id, course_id=test_course.id, topic="python", mastery=0.65))
    db_session.add(TopicMastery(student_id=peer.id, course_id=test_course.id, topic="sql", mastery=0.75))
    db_session.add(LessonProgress(student_id=peer.id, lesson_id=target_lesson.id, completed=True, time_spent_sec=300))
    db_session.commit()

    collab_recs = generate_collaborative_recommendations(db_session, test_student.id, test_course.id)

    assert len(collab_recs) >= 1
    assert collab_recs[0]["target_id"] == target_lesson.id
    assert "similar students" in collab_recs[0]["reason"].lower()


def test_recommendations_api_flow_and_permissions(
    client,
    auth_headers_student,
    auth_headers_teacher,
    auth_headers_admin,
    test_student,
    test_course,
    db_session,
):
    """End-to-end API test for recommendations: permissions, refresh, and response format."""
    from app.models.user import User

    # 1. Setup course content
    mod = Module(course_id=test_course.id, title="Module 1", order=1)
    db_session.add(mod)
    db_session.commit()

    lesson = Lesson(module_id=mod.id, title="Recursion Basics", content="...", topic="recursion", est_minutes=15, order=1)
    db_session.add(lesson)
    db_session.commit()

    # Enroll student and assign low mastery in recursion
    client.post(f"/api/v1/courses/{test_course.id}/enroll", headers=auth_headers_student)
    db_session.add(TopicMastery(student_id=test_student.id, course_id=test_course.id, topic="recursion", mastery=0.3))
    db_session.commit()

    # 2. Student fetches their own recommendations
    resp = client.get(
        f"/api/v1/recommendations/student/{test_student.id}/course/{test_course.id}?refresh=true",
        headers=auth_headers_student,
    )
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) >= 1
    assert "reason" in recs[0]
    assert "priority" in recs[0]
    assert "type" in recs[0]
    assert recs[0]["student_id"] == test_student.id

    # 3. Student cannot view other student's recommendations
    other_student = User(name="Other", email="other_rec@test.com", password_hash="hash", role="student")
    db_session.add(other_student)
    db_session.commit()

    forbidden_resp = client.get(
        f"/api/v1/recommendations/student/{other_student.id}/course/{test_course.id}",
        headers=auth_headers_student,
    )
    assert forbidden_resp.status_code == 403

    # 4. Teacher of course can view recommendations
    teacher_resp = client.get(
        f"/api/v1/recommendations/student/{test_student.id}/course/{test_course.id}",
        headers=auth_headers_teacher,
    )
    assert teacher_resp.status_code == 200
    assert len(teacher_resp.json()) >= 1

    # 5. Admin can view recommendations
    admin_resp = client.get(
        f"/api/v1/recommendations/student/{test_student.id}/course/{test_course.id}",
        headers=auth_headers_admin,
    )
    assert admin_resp.status_code == 200
    assert len(admin_resp.json()) >= 1
