"""Regression tests: deleting parents must not crash when children exist."""
from app.models.progress import AttemptAnswer, LessonProgress, QuizAttempt, TopicMastery
from app.models.quiz import Question


def _build_course(client, h):
    cid = client.post("/api/v1/courses", json={"title": "Algebra"}, headers=h["teacher"]).json()["id"]
    mid = client.post(f"/api/v1/courses/{cid}/modules", json={"title": "M1"}, headers=h["teacher"]).json()["id"]
    lid = client.post("/api/v1/lessons", json={"module_id": mid, "title": "L1", "topic": "t"}, headers=h["teacher"]).json()["id"]
    qid = client.post("/api/v1/questions", json={
        "course_id": cid, "topic": "t", "difficulty": "easy", "text": "2+2?",
        "options_json": ["3", "4"], "correct_index": 1}, headers=h["teacher"]).json()["id"]
    zid = client.post("/api/v1/quizzes", json={
        "course_id": cid, "module_id": mid, "title": "Q", "question_ids": [qid]}, headers=h["teacher"]).json()["id"]
    return cid, mid, lid, qid, zid


def _add_student_activity(db, student_id, cid, lid, qid, zid):
    db.add(LessonProgress(student_id=student_id, lesson_id=lid, completed=True, time_spent_sec=60))
    db.add(TopicMastery(student_id=student_id, course_id=cid, topic="t", mastery=0.6))
    att = QuizAttempt(student_id=student_id, quiz_id=zid, score=1, max_score=1)
    db.add(att)
    db.flush()
    db.add(AttemptAnswer(attempt_id=att.id, question_id=qid, selected_index=1, is_correct=True))
    db.commit()


def _student_id(client, h):
    return client.get("/api/v1/auth/me", headers=h["student"]).json()["id"]


def test_delete_course_with_everything(client, db_session):
    h = create_test_users(client)
    cid, mid, lid, qid, zid = _build_course(client, h)
    client.post(f"/api/v1/courses/{cid}/enroll", headers=h["student"])
    _add_student_activity(db_session, _student_id(client, h), cid, lid, qid, zid)
    assert client.delete(f"/api/v1/courses/{cid}", headers=h["teacher"]).status_code == 204
    assert client.get(f"/api/v1/courses/{cid}", headers=h["teacher"]).status_code == 404
    assert db_session.query(Question).count() == 0
    assert db_session.query(QuizAttempt).count() == 0


def test_delete_module_keeps_quiz_detached(client):
    h = create_test_users(client)
    cid, mid, lid, qid, zid = _build_course(client, h)
    assert client.delete(f"/api/v1/courses/{cid}/modules/{mid}", headers=h["teacher"]).status_code == 204
    quiz = client.get(f"/api/v1/quizzes/{zid}", headers=h["teacher"]).json()
    assert quiz["module_id"] is None


def test_delete_lesson_and_question_with_history(client, db_session):
    h = create_test_users(client)
    cid, mid, lid, qid, zid = _build_course(client, h)
    _add_student_activity(db_session, _student_id(client, h), cid, lid, qid, zid)
    assert client.delete(f"/api/v1/lessons/{lid}", headers=h["teacher"]).status_code == 204
    assert client.delete(f"/api/v1/questions/{qid}", headers=h["teacher"]).status_code == 204
    assert client.delete(f"/api/v1/quizzes/{zid}", headers=h["teacher"]).status_code == 204


# Self-contained helpers (no import from conftest, so these tests work however
# the tests folder is laid out).
def _login_header(client, email, password):
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_users(client):
    headers = {}
    for role, name in (("admin", "Admin User"), ("teacher", "Teacher User"), ("student", "Student User")):
        email, pw = f"{role}@test.com", f"{role.capitalize()}@123"
        client.post("/api/v1/auth/register", json={"name": name, "email": email, "password": pw, "role": role})
        headers[role] = _login_header(client, email, pw)
    return headers
