"""
Tests for Phase 2: Course, module, lesson, question, and quiz CRUD + enrollment.
"""

import pytest
from tests.conftest import create_test_users, register_user, get_auth_header


@pytest.fixture
def users_and_headers(client):
    """Fixture providing auth headers for admin, teacher, and student."""
    return create_test_users(client)


# ── Course Tests ───────────────────────────────────────────────────────

def test_teacher_can_create_course(client, users_and_headers):
    """Teacher can successfully create a course."""
    resp = client.post(
        "/api/v1/courses",
        json={"title": "Linear Algebra", "description": "Intro to vectors and matrices"},
        headers=users_and_headers["teacher"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Linear Algebra"
    assert data["description"] == "Intro to vectors and matrices"
    assert "id" in data


def test_student_cannot_create_course(client, users_and_headers):
    """Students are forbidden from creating courses."""
    resp = client.post(
        "/api/v1/courses",
        json={"title": "Hacking 101", "description": "Forbidden"},
        headers=users_and_headers["student"],
    )
    assert resp.status_code == 403


def test_list_and_get_course_detail(client, users_and_headers):
    """All authenticated users can list and view course details."""
    # Create course
    create_resp = client.post(
        "/api/v1/courses",
        json={"title": "Calculus I", "description": "Derivatives & integrals"},
        headers=users_and_headers["teacher"],
    )
    course_id = create_resp.json()["id"]

    # Student lists courses
    list_resp = client.get("/api/v1/courses", headers=users_and_headers["student"])
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Student views course detail
    detail_resp = client.get(f"/api/v1/courses/{course_id}", headers=users_and_headers["student"])
    assert detail_resp.status_code == 200
    assert detail_resp.json()["title"] == "Calculus I"
    assert "modules" in detail_resp.json()


def test_update_and_delete_course(client, users_and_headers):
    """Teacher can update and delete their own course."""
    create_resp = client.post(
        "/api/v1/courses",
        json={"title": "Physics I", "description": "Mechanics"},
        headers=users_and_headers["teacher"],
    )
    course_id = create_resp.json()["id"]

    # Update
    patch_resp = client.patch(
        f"/api/v1/courses/{course_id}",
        json={"title": "Physics I: Advanced Mechanics"},
        headers=users_and_headers["teacher"],
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Physics I: Advanced Mechanics"

    # Delete
    del_resp = client.delete(f"/api/v1/courses/{course_id}", headers=users_and_headers["teacher"])
    assert del_resp.status_code == 204

    # Verify not found
    get_resp = client.get(f"/api/v1/courses/{course_id}", headers=users_and_headers["teacher"])
    assert get_resp.status_code == 404


def test_non_owner_teacher_cannot_modify_course(client, users_and_headers):
    """A teacher cannot modify another teacher's course."""
    # Teacher 1 creates course
    create_resp = client.post(
        "/api/v1/courses",
        json={"title": "Biology", "description": "Cell biology"},
        headers=users_and_headers["teacher"],
    )
    course_id = create_resp.json()["id"]

    # Teacher 2 registers
    register_user(client, "Teacher 2", "teacher2@test.com", "Teacher@123", "teacher")
    t2_headers = get_auth_header(client, "teacher2@test.com", "Teacher@123")

    # Teacher 2 tries to update
    patch_resp = client.patch(
        f"/api/v1/courses/{course_id}",
        json={"title": "Hijacked Course"},
        headers=t2_headers,
    )
    assert patch_resp.status_code == 403


# ── Enrollment Tests ───────────────────────────────────────────────────

def test_enrollment_flow(client, users_and_headers):
    """Student can enroll in course, view enrolled list, and duplicate enrollment is rejected."""
    create_resp = client.post(
        "/api/v1/courses",
        json={"title": "Chemistry", "description": "Organic chemistry"},
        headers=users_and_headers["teacher"],
    )
    course_id = create_resp.json()["id"]

    # Enroll
    enroll_resp = client.post(
        f"/api/v1/courses/{course_id}/enroll",
        headers=users_and_headers["student"],
    )
    assert enroll_resp.status_code == 201
    assert enroll_resp.json()["course_id"] == course_id

    # Duplicate enroll returns 409
    dup_resp = client.post(
        f"/api/v1/courses/{course_id}/enroll",
        headers=users_and_headers["student"],
    )
    assert dup_resp.status_code == 409

    # Check student enrolled courses list
    enrolled_resp = client.get("/api/v1/courses/enrolled", headers=users_and_headers["student"])
    assert enrolled_resp.status_code == 200
    assert any(c["id"] == course_id for c in enrolled_resp.json())

    # Teacher views enrolled students
    students_resp = client.get(
        f"/api/v1/courses/{course_id}/students",
        headers=users_and_headers["teacher"],
    )
    assert students_resp.status_code == 200
    assert len(students_resp.json()) == 1


# ── Modules & Lessons Tests ────────────────────────────────────────────

def test_module_and_lesson_crud(client, users_and_headers):
    """Teacher can create modules and lessons, update them, and delete them."""
    course_resp = client.post(
        "/api/v1/courses",
        json={"title": "Computer Science", "description": "Algorithms"},
        headers=users_and_headers["teacher"],
    )
    course_id = course_resp.json()["id"]

    # Create module
    mod_resp = client.post(
        f"/api/v1/courses/{course_id}/modules",
        json={"title": "Module 1: Sorting", "order": 1},
        headers=users_and_headers["teacher"],
    )
    assert mod_resp.status_code == 201
    module_id = mod_resp.json()["id"]

    # Update module
    patch_mod_resp = client.patch(
        f"/api/v1/courses/{course_id}/modules/{module_id}",
        json={"title": "Module 1: Basic Sorting"},
        headers=users_and_headers["teacher"],
    )
    assert patch_mod_resp.status_code == 200
    assert patch_mod_resp.json()["title"] == "Module 1: Basic Sorting"

    # Create lesson in module
    lesson_resp = client.post(
        "/api/v1/lessons",
        json={
            "module_id": module_id,
            "title": "Quicksort",
            "content": "Quicksort is divide and conquer...",
            "topic": "Algorithms",
            "est_minutes": 20,
            "order": 1,
        },
        headers=users_and_headers["teacher"],
    )
    assert lesson_resp.status_code == 201
    lesson_id = lesson_resp.json()["id"]

    # Student views lesson
    get_lesson = client.get(f"/api/v1/lessons/{lesson_id}", headers=users_and_headers["student"])
    assert get_lesson.status_code == 200
    assert get_lesson.json()["title"] == "Quicksort"

    # Teacher updates lesson
    patch_lesson = client.patch(
        f"/api/v1/lessons/{lesson_id}",
        json={"est_minutes": 25},
        headers=users_and_headers["teacher"],
    )
    assert patch_lesson.status_code == 200
    assert patch_lesson.json()["est_minutes"] == 25

    # Verify lesson appears in course detail
    detail = client.get(f"/api/v1/courses/{course_id}", headers=users_and_headers["student"])
    assert len(detail.json()["modules"][0]["lessons"]) == 1

    # Student cannot delete lesson
    assert client.delete(f"/api/v1/lessons/{lesson_id}", headers=users_and_headers["student"]).status_code == 403

    # Teacher deletes lesson
    assert client.delete(f"/api/v1/lessons/{lesson_id}", headers=users_and_headers["teacher"]).status_code == 204

    # Teacher deletes module
    assert client.delete(f"/api/v1/courses/{course_id}/modules/{module_id}", headers=users_and_headers["teacher"]).status_code == 204


# ── Questions Tests ────────────────────────────────────────────────────

def test_question_crud_and_validation(client, users_and_headers):
    """Teacher can create questions with topic/difficulty, and invalid input is rejected."""
    course_resp = client.post(
        "/api/v1/courses",
        json={"title": "World History", "description": "Ancient and modern"},
        headers=users_and_headers["teacher"],
    )
    course_id = course_resp.json()["id"]

    # Valid question
    q_resp = client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Ancient Rome",
            "difficulty": "medium",
            "text": "Who was the first Roman Emperor?",
            "options_json": ["Julius Caesar", "Augustus", "Nero", "Tiberius"],
            "correct_index": 1,
        },
        headers=users_and_headers["teacher"],
    )
    assert q_resp.status_code == 201
    q_id = q_resp.json()["id"]
    assert q_resp.json()["topic"] == "Ancient Rome"

    # Student cannot create questions
    assert client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Ancient Rome",
            "difficulty": "easy",
            "text": "Student question?",
            "options_json": ["A", "B"],
            "correct_index": 0,
        },
        headers=users_and_headers["student"],
    ).status_code == 403

    # Invalid difficulty fails validation
    bad_diff = client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Ancient Rome",
            "difficulty": "super-hard",
            "text": "Invalid diff?",
            "options_json": ["A", "B"],
            "correct_index": 0,
        },
        headers=users_and_headers["teacher"],
    )
    assert bad_diff.status_code == 422

    # Invalid correct_index out of bounds
    bad_idx = client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Ancient Rome",
            "difficulty": "easy",
            "text": "Out of bounds index?",
            "options_json": ["Option 0", "Option 1"],
            "correct_index": 5,
        },
        headers=users_and_headers["teacher"],
    )
    assert bad_idx.status_code == 422

    # Teacher can filter questions
    filter_resp = client.get(
        f"/api/v1/questions?course_id={course_id}&topic=Ancient Rome",
        headers=users_and_headers["teacher"],
    )
    assert filter_resp.status_code == 200
    assert len(filter_resp.json()) == 1

    # Teacher updates question
    patch_q = client.patch(
        f"/api/v1/questions/{q_id}",
        json={"difficulty": "hard"},
        headers=users_and_headers["teacher"],
    )
    assert patch_q.status_code == 200
    assert patch_q.json()["difficulty"] == "hard"

    # Delete question
    del_q = client.delete(f"/api/v1/questions/{q_id}", headers=users_and_headers["teacher"])
    assert del_q.status_code == 204


# ── Quizzes Tests ──────────────────────────────────────────────────────

def test_quiz_crud_and_question_association(client, users_and_headers):
    """Teacher can create a quiz, associate questions, and students see questions without correct_index."""
    course_resp = client.post(
        "/api/v1/courses",
        json={"title": "Mathematics", "description": "Math concepts"},
        headers=users_and_headers["teacher"],
    )
    course_id = course_resp.json()["id"]

    # Create two questions
    q1 = client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Algebra",
            "difficulty": "easy",
            "text": "What is 2 + 2?",
            "options_json": ["3", "4", "5"],
            "correct_index": 1,
        },
        headers=users_and_headers["teacher"],
    ).json()

    q2 = client.post(
        "/api/v1/questions",
        json={
            "course_id": course_id,
            "topic": "Algebra",
            "difficulty": "medium",
            "text": "What is 3x = 9?",
            "options_json": ["1", "2", "3"],
            "correct_index": 2,
        },
        headers=users_and_headers["teacher"],
    ).json()

    # Create quiz associating both questions
    quiz_resp = client.post(
        "/api/v1/quizzes",
        json={
            "course_id": course_id,
            "title": "Algebra Quiz 1",
            "question_ids": [q1["id"], q2["id"]],
        },
        headers=users_and_headers["teacher"],
    )
    assert quiz_resp.status_code == 201
    quiz_data = quiz_resp.json()
    quiz_id = quiz_data["id"]
    assert len(quiz_data["questions"]) == 2

    # Teacher view: sees correct_index
    teacher_view = client.get(f"/api/v1/quizzes/{quiz_id}", headers=users_and_headers["teacher"])
    assert teacher_view.status_code == 200
    assert "correct_index" in teacher_view.json()["questions"][0]

    # Student view: correct_index MUST NOT be present
    student_view = client.get(f"/api/v1/quizzes/{quiz_id}", headers=users_and_headers["student"])
    assert student_view.status_code == 200
    student_questions = student_view.json()["questions"]
    assert len(student_questions) == 2
    for sq in student_questions:
        assert "correct_index" not in sq

    # Update quiz title and questions
    patch_quiz = client.patch(
        f"/api/v1/quizzes/{quiz_id}",
        json={"title": "Algebra Quiz 1 (Updated)", "question_ids": [q1["id"]]},
        headers=users_and_headers["teacher"],
    )
    assert patch_quiz.status_code == 200
    assert patch_quiz.json()["title"] == "Algebra Quiz 1 (Updated)"
    assert len(patch_quiz.json()["questions"]) == 1

    # Delete quiz
    assert client.delete(f"/api/v1/quizzes/{quiz_id}", headers=users_and_headers["teacher"]).status_code == 204
