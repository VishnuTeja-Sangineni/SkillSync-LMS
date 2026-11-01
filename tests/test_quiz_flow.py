"""End-to-end tests for taking adaptive quizzes via API endpoints."""

import pytest
from app.models.quiz import Question, Quiz, QuizQuestion
from app.models.progress import TopicMastery


def test_adaptive_quiz_full_flow(client, auth_headers_student, auth_headers_teacher, test_course, db_session):
    """Full lifecycle: enroll -> start -> next-question -> answer -> finish."""
    # 1. Enroll student in the course
    enroll_resp = client.post(f"/api/v1/courses/{test_course.id}/enroll", headers=auth_headers_student)
    assert enroll_resp.status_code == 201

    # 2. Teacher creates 3 questions
    q_easy = Question(
        course_id=test_course.id,
        topic="algorithms",
        difficulty="easy",
        text="What is O(1)?",
        options_json=["Constant", "Linear", "Logarithmic", "Quadratic"],
        correct_index=0,
    )
    q_med = Question(
        course_id=test_course.id,
        topic="algorithms",
        difficulty="medium",
        text="What is binary search?",
        options_json=["O(N)", "O(log N)", "O(N^2)", "O(1)"],
        correct_index=1,
    )
    db_session.add_all([q_easy, q_med])
    db_session.commit()

    # Create quiz
    quiz = Quiz(course_id=test_course.id, title="Algorithm Fundamentals")
    db_session.add(quiz)
    db_session.commit()

    db_session.add(QuizQuestion(quiz_id=quiz.id, question_id=q_easy.id))
    db_session.add(QuizQuestion(quiz_id=quiz.id, question_id=q_med.id))
    db_session.commit()

    # 3. Student starts quiz
    start_resp = client.post(f"/api/v1/quizzes/{quiz.id}/start", headers=auth_headers_student)
    assert start_resp.status_code == 201
    start_data = start_resp.json()
    attempt_id = start_data["attempt_id"]
    assert start_data["total_questions"] == 2

    # 4. Student gets first question
    next_resp = client.get(
        f"/api/v1/quizzes/{quiz.id}/next-question?attempt_id={attempt_id}",
        headers=auth_headers_student,
    )
    assert next_resp.status_code == 200
    next_data = next_resp.json()
    assert next_data["is_complete"] is False
    assert next_data["question"] is not None
    # Student view MUST NOT include correct_index
    assert "correct_index" not in next_data["question"]
    first_q_id = next_data["question"]["id"]

    # 5. Student submits correct answer
    ans_resp = client.post(
        f"/api/v1/quizzes/{quiz.id}/answer",
        headers=auth_headers_student,
        json={
            "attempt_id": attempt_id,
            "question_id": first_q_id,
            "selected_index": 0 if first_q_id == q_easy.id else 1,
            "time_taken_sec": 12,
        },
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["is_correct"] is True
    assert "new_mastery" in ans_data
    assert ans_data["topic"] == "algorithms"

    # 6. Duplicate answer submission must fail
    dup_resp = client.post(
        f"/api/v1/quizzes/{quiz.id}/answer",
        headers=auth_headers_student,
        json={
            "attempt_id": attempt_id,
            "question_id": first_q_id,
            "selected_index": 0,
            "time_taken_sec": 5,
        },
    )
    assert dup_resp.status_code == 400

    # 7. Student requests second question
    next_resp2 = client.get(
        f"/api/v1/quizzes/{quiz.id}/next-question?attempt_id={attempt_id}",
        headers=auth_headers_student,
    )
    assert next_resp2.status_code == 200
    next_data2 = next_resp2.json()
    assert next_data2["is_complete"] is False
    second_q_id = next_data2["question"]["id"]
    assert second_q_id != first_q_id

    # 8. Student answers second question (incorrectly)
    ans_resp2 = client.post(
        f"/api/v1/quizzes/{quiz.id}/answer",
        headers=auth_headers_student,
        json={
            "attempt_id": attempt_id,
            "question_id": second_q_id,
            "selected_index": 3,  # wrong option
            "time_taken_sec": 18,
        },
    )
    assert ans_resp2.status_code == 200
    assert ans_resp2.json()["is_correct"] is False

    # 9. Next question should indicate complete
    next_resp3 = client.get(
        f"/api/v1/quizzes/{quiz.id}/next-question?attempt_id={attempt_id}",
        headers=auth_headers_student,
    )
    assert next_resp3.status_code == 200
    assert next_resp3.json()["is_complete"] is True
    assert next_resp3.json()["question"] is None

    # 10. Finish quiz attempt
    finish_resp = client.post(
        f"/api/v1/quizzes/{quiz.id}/finish",
        headers=auth_headers_student,
        json={"attempt_id": attempt_id},
    )
    assert finish_resp.status_code == 200
    finish_data = finish_resp.json()
    assert finish_data["score"] == 1.0
    assert finish_data["max_score"] == 2.0
    assert finish_data["percentage"] == 50.0
    assert finish_data["finished_at"] is not None

    # 11. Trying to answer or get questions on finished attempt fails
    post_finish_ans = client.post(
        f"/api/v1/quizzes/{quiz.id}/answer",
        headers=auth_headers_student,
        json={"attempt_id": attempt_id, "question_id": first_q_id, "selected_index": 0},
    )
    assert post_finish_ans.status_code == 400


def test_unenrolled_student_cannot_start_quiz(client, auth_headers_student, test_course, db_session):
    """Students cannot start a quiz for a course they are not enrolled in."""
    quiz = Quiz(course_id=test_course.id, title="Unenrolled Quiz")
    db_session.add(quiz)
    db_session.commit()

    resp = client.post(f"/api/v1/quizzes/{quiz.id}/start", headers=auth_headers_student)
    assert resp.status_code == 403
    assert "enrolled" in resp.json()["detail"].lower()
