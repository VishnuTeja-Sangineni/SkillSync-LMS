"""Tests for the synthetic data generator and the seed script."""
from datetime import datetime, timezone

from app.models import (
    AttemptAnswer, Enrollment, FinalGrade, Question, QuizAttempt, QuizQuestion, TopicMastery, User,
)
from scripts.seed import DEMO_PASSWORDS, build_hashes, seed_database, table_counts, wipe

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _seed(db, n=12, **kw):
    return seed_database(db, n_students=n, seed=7, now=NOW, **kw)


def test_seed_creates_expected_structure(db_session):
    summary = _seed(db_session)
    c = summary["counts"]
    assert summary["status"] == "seeded"
    assert c["users"] == 3 + 12          # admin + 2 teachers + students
    assert (c["courses"], c["modules"], c["lessons"], c["questions"], c["quizzes"]) == (3, 15, 30, 180, 18)
    assert c["quiz_questions"] == 15 * 12 + 3 * 15   # topic quizzes + final exams
    assert c["final_grades"] == c["enrollments"] > 0
    assert c["quiz_attempts"] > 0 and c["attempt_answers"] > c["quiz_attempts"]


def test_demo_accounts_can_log_in(client, db_session):
    _seed(db_session)
    for role, pw in DEMO_PASSWORDS.items():
        headers = _login_header(client, f"{role}@skillsync.com", pw)
        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["role"] == role


def test_seed_is_idempotent(db_session):
    first = _seed(db_session)
    before = table_counts(db_session)
    second = _seed(db_session)
    assert second["status"] == "already_seeded"
    assert table_counts(db_session) == before == first["counts"]


def test_reset_wipes_everything_first(db_session):
    _seed(db_session)
    db_session.add(User(name="Stray", email="stray@example.com", password_hash="x", role="student"))
    db_session.commit()
    summary = _seed(db_session, reset=True)
    assert summary["status"] == "seeded"
    assert db_session.query(User).filter(User.email == "stray@example.com").count() == 0
    assert summary["counts"]["users"] == 15


def test_same_seed_gives_identical_data(db_session):
    def fingerprint():
        grades = [round(g.final_score, 1) for g in db_session.query(FinalGrade).order_by(FinalGrade.id)]
        return (grades, db_session.query(QuizAttempt).count(), db_session.query(Question).first().text)

    _seed(db_session)
    a = fingerprint()
    wipe(db_session)
    _seed(db_session)
    assert fingerprint() == a


def test_generated_activity_is_internally_consistent(db_session):
    _seed(db_session)
    for att in db_session.query(QuizAttempt).all():
        answers = att.answers
        assert answers
        assert att.max_score == len(answers)
        assert att.score == sum(a.is_correct for a in answers)
        assert att.duration_sec == sum(a.time_taken_sec for a in answers)
        assert att.finished_at >= att.started_at
    for a in db_session.query(AttemptAnswer).limit(500):
        assert a.is_correct == (a.selected_index == a.question.correct_index)
    for m in db_session.query(TopicMastery):
        assert 0.0 <= m.mastery <= 1.0
    for g in db_session.query(FinalGrade):
        assert 0.0 <= g.final_score <= 100.0


def test_quiz_questions_belong_to_the_same_course(db_session):
    _seed(db_session)
    from app.models import Quiz
    for qq in db_session.query(QuizQuestion):
        assert qq.question.course_id == db_session.get(Quiz, qq.quiz_id).course_id


def test_students_only_have_activity_in_enrolled_courses(db_session):
    _seed(db_session)
    enrolled = {(e.student_id, e.course_id) for e in db_session.query(Enrollment)}
    for m in db_session.query(TopicMastery):
        assert (m.student_id, m.course_id) in enrolled


def test_profiles_produce_varied_outcomes(db_session):
    summary = _seed(db_session, n=60)
    scores = summary["final_scores"]
    assert max(scores) - min(scores) > 30
    assert len(summary["profiles"]) >= 3


def test_admin_can_delete_seeded_student_but_not_teacher_with_courses(client, db_session):
    _seed(db_session)
    admin = _login_header(client, "admin@skillsync.com", DEMO_PASSWORDS["admin"])
    student = db_session.query(User).filter(User.email == "student@skillsync.com").one()
    assert client.delete(f"/api/v1/admin/users/{student.id}", headers=admin).status_code == 204
    assert db_session.query(QuizAttempt).filter(QuizAttempt.student_id == student.id).count() == 0
    teacher = db_session.query(User).filter(User.email == "teacher@skillsync.com").one()
    assert client.delete(f"/api/v1/admin/users/{teacher.id}", headers=admin).status_code == 409


def _login_header(client, email, password):
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
