"""Tests for student and course analytics endpoints."""

from datetime import datetime, timezone, timedelta
from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import Enrollment, QuizAttempt, AttemptAnswer, LessonProgress, TopicMastery


def test_student_analytics_own_access(client, auth_headers_student, test_student, test_course, db_session):
    """Students can retrieve their own analytics including mastery, trends, time, streak."""
    # 1. Enroll student
    db_session.add(Enrollment(student_id=test_student.id, course_id=test_course.id))

    # 2. Add topic masteries (one weak, one strong)
    now = datetime.now(timezone.utc)
    db_session.add(TopicMastery(
        student_id=test_student.id,
        course_id=test_course.id,
        topic="weak-topic",
        mastery=0.35,
        updated_at=now,
    ))
    db_session.add(TopicMastery(
        student_id=test_student.id,
        course_id=test_course.id,
        topic="strong-topic",
        mastery=0.88,
        updated_at=now,
    ))

    # 3. Add quiz attempts to verify score trend slope
    quiz = Quiz(course_id=test_course.id, title="Trend Quiz")
    db_session.add(quiz)
    db_session.commit()

    att1 = QuizAttempt(
        student_id=test_student.id,
        quiz_id=quiz.id,
        score=5.0,
        max_score=10.0,
        duration_sec=300,
        started_at=now - timedelta(days=1),
        finished_at=now - timedelta(days=1, seconds=-300),
    )
    att2 = QuizAttempt(
        student_id=test_student.id,
        quiz_id=quiz.id,
        score=9.0,
        max_score=10.0,
        duration_sec=250,
        started_at=now,
        finished_at=now + timedelta(seconds=250),
    )
    db_session.add_all([att1, att2])
    db_session.commit()

    # 4. Fetch student analytics
    resp = client.get(f"/api/v1/analytics/student/{test_student.id}", headers=auth_headers_student)
    assert resp.status_code == 200
    data = resp.json()

    assert data["student_id"] == test_student.id
    assert "weak-topic" in data["weak_areas"]
    assert "strong-topic" not in data["weak_areas"]
    assert len(data["mastery_by_topic"]) == 2

    # Trend should be improving (from 50% to 90%)
    trend = data["score_trend"]
    assert trend["direction"] == "improving"
    assert trend["slope"] > 0
    assert len(trend["attempts"]) == 2

    # Time spent = 300 + 250 = 550
    assert data["total_time_spent_sec"] >= 550
    # Streak should be at least 1
    assert data["streak_days"] >= 1


def test_student_cannot_view_other_student_analytics(client, auth_headers_student, test_user, db_session):
    """Students cannot access another student's analytics."""
    resp = client.get(f"/api/v1/analytics/student/{test_user.id}", headers=auth_headers_student)
    assert resp.status_code == 403


def test_teacher_can_view_student_analytics(client, auth_headers_teacher, test_student, db_session):
    """Teachers can view a student's analytics."""
    resp = client.get(f"/api/v1/analytics/student/{test_student.id}", headers=auth_headers_teacher)
    assert resp.status_code == 200
    assert resp.json()["student_id"] == test_student.id


def test_course_analytics_access_and_metrics(
    client,
    auth_headers_teacher,
    auth_headers_student,
    auth_headers_admin,
    test_course,
    test_student,
    db_session,
):
    """Course analytics: teacher owner and admin succeed, students are forbidden."""
    # Enroll student in test_course
    db_session.add(Enrollment(student_id=test_student.id, course_id=test_course.id))
    db_session.add(TopicMastery(
        student_id=test_student.id,
        course_id=test_course.id,
        topic="python",
        mastery=0.75,
    ))
    db_session.commit()

    # 1. Student access -> 403 Forbidden
    resp_student = client.get(f"/api/v1/analytics/course/{test_course.id}", headers=auth_headers_student)
    assert resp_student.status_code == 403

    # 2. Teacher owner access -> 200 OK
    resp_teacher = client.get(f"/api/v1/analytics/course/{test_course.id}", headers=auth_headers_teacher)
    assert resp_teacher.status_code == 200
    data = resp_teacher.json()
    assert data["course_id"] == test_course.id
    assert data["total_enrolled"] == 1
    assert len(data["topic_masteries"]) == 1
    assert data["topic_masteries"][0]["topic"] == "python"
    assert "score_distribution" in data
    assert "engagement_over_time" in data

    # 3. Admin access -> 200 OK
    resp_admin = client.get(f"/api/v1/analytics/course/{test_course.id}", headers=auth_headers_admin)
    assert resp_admin.status_code == 200
    assert resp_admin.json()["course_id"] == test_course.id
