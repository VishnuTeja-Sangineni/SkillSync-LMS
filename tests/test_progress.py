"""Tests for lesson progress tracking."""

from app.models.course import Module, Lesson


def test_lesson_progress_lifecycle(client, auth_headers_student, test_course, db_session):
    """Enrolled student records progress, accumulates time, and queries status."""
    # 1. Enroll student
    enroll_resp = client.post(f"/api/v1/courses/{test_course.id}/enroll", headers=auth_headers_student)
    assert enroll_resp.status_code == 201

    # 2. Add module and lesson
    module = Module(course_id=test_course.id, title="Module 1", order=1)
    db_session.add(module)
    db_session.commit()

    lesson = Lesson(
        module_id=module.id,
        title="Intro Lesson",
        content="Welcome to the course",
        topic="intro",
        est_minutes=15,
        order=1,
    )
    db_session.add(lesson)
    db_session.commit()

    # 3. Record initial progress (120 seconds, not completed)
    resp = client.post(
        "/api/v1/progress/lesson",
        headers=auth_headers_student,
        json={"lesson_id": lesson.id, "completed": False, "time_spent_sec": 120},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["lesson_id"] == lesson.id
    assert data["completed"] is False
    assert data["time_spent_sec"] == 120

    # 4. Record additional progress (mark completed + 60 more seconds)
    resp2 = client.post(
        "/api/v1/progress/lesson",
        headers=auth_headers_student,
        json={"lesson_id": lesson.id, "completed": True, "time_spent_sec": 60},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["completed"] is True
    assert data2["time_spent_sec"] == 180  # 120 + 60 accumulated

    # 5. Query lesson progress directly
    get_resp = client.get(f"/api/v1/progress/lesson/{lesson.id}", headers=auth_headers_student)
    assert get_resp.status_code == 200
    assert get_resp.json()["time_spent_sec"] == 180

    # 6. Query all course lessons progress
    course_prog_resp = client.get(f"/api/v1/progress/course/{test_course.id}", headers=auth_headers_student)
    assert course_prog_resp.status_code == 200
    progs = course_prog_resp.json()
    assert len(progs) == 1
    assert progs[0]["completed"] is True


def test_unenrolled_student_cannot_record_progress(client, auth_headers_student, test_course, db_session):
    """Students cannot record progress on courses they are not enrolled in."""
    module = Module(course_id=test_course.id, title="Mod", order=1)
    db_session.add(module)
    db_session.commit()

    lesson = Lesson(
        module_id=module.id,
        title="Lesson X",
        content="Text",
        topic="x",
        est_minutes=10,
        order=1,
    )
    db_session.add(lesson)
    db_session.commit()

    resp = client.post(
        "/api/v1/progress/lesson",
        headers=auth_headers_student,
        json={"lesson_id": lesson.id, "completed": True, "time_spent_sec": 100},
    )
    assert resp.status_code == 403
