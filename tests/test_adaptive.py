"""Tests for the adaptive difficulty question selection engine."""

from app.services.adaptive import get_recommended_difficulty, select_next_question
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import QuizAttempt, AttemptAnswer, TopicMastery


def test_get_recommended_difficulty_thresholds():
    """Verify mastery to difficulty mapping (<0.4: easy, 0.4-0.7: medium, >0.7: hard)."""
    assert get_recommended_difficulty(0.2) == "easy"
    assert get_recommended_difficulty(0.39) == "easy"
    assert get_recommended_difficulty(0.4) == "medium"
    assert get_recommended_difficulty(0.65) == "medium"
    assert get_recommended_difficulty(0.7) == "medium"
    assert get_recommended_difficulty(0.71) == "hard"
    assert get_recommended_difficulty(0.95) == "hard"


def test_select_next_question_adapts_to_mastery(db_session, test_user, test_course):
    """select_next_question picks the question difficulty matching the student's mastery."""
    # Create 3 questions of different difficulties in topic 'python-basics'
    q_easy = Question(
        course_id=test_course.id,
        topic="python-basics",
        difficulty="easy",
        text="What is a variable?",
        options_json=["A", "B", "C", "D"],
        correct_index=0,
    )
    q_med = Question(
        course_id=test_course.id,
        topic="python-basics",
        difficulty="medium",
        text="What is list comprehension?",
        options_json=["A", "B", "C", "D"],
        correct_index=1,
    )
    q_hard = Question(
        course_id=test_course.id,
        topic="python-basics",
        difficulty="hard",
        text="What is a metaclass?",
        options_json=["A", "B", "C", "D"],
        correct_index=2,
    )
    db_session.add_all([q_easy, q_med, q_hard])
    db_session.commit()

    quiz = Quiz(course_id=test_course.id, title="Adaptive Test Quiz")
    db_session.add(quiz)
    db_session.commit()

    for q in [q_easy, q_med, q_hard]:
        db_session.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id))
    db_session.commit()

    attempt = QuizAttempt(student_id=test_user.id, quiz_id=quiz.id)
    db_session.add(attempt)
    db_session.commit()

    # Case 1: Student has low mastery (0.2) -> should pick easy question
    tm = TopicMastery(
        student_id=test_user.id,
        course_id=test_course.id,
        topic="python-basics",
        mastery=0.2,
    )
    db_session.add(tm)
    db_session.commit()

    chosen_q = select_next_question(db_session, quiz.id, test_user.id, attempt.id)
    assert chosen_q is not None
    assert chosen_q.difficulty == "easy"
    assert chosen_q.id == q_easy.id

    # Case 2: Student has high mastery (0.85) -> should pick hard question
    tm.mastery = 0.85
    db_session.commit()

    chosen_q_high = select_next_question(db_session, quiz.id, test_user.id, attempt.id)
    assert chosen_q_high is not None
    assert chosen_q_high.difficulty == "hard"
    assert chosen_q_high.id == q_hard.id


def test_select_next_question_avoids_repeats_and_completes(db_session, test_user, test_course):
    """Answered questions are not returned again; returns None when quiz is complete."""
    q1 = Question(
        course_id=test_course.id,
        topic="math",
        difficulty="easy",
        text="2+2?",
        options_json=["3", "4"],
        correct_index=1,
    )
    q2 = Question(
        course_id=test_course.id,
        topic="math",
        difficulty="medium",
        text="2*3?",
        options_json=["5", "6"],
        correct_index=1,
    )
    db_session.add_all([q1, q2])
    db_session.commit()

    quiz = Quiz(course_id=test_course.id, title="Math Quiz")
    db_session.add(quiz)
    db_session.commit()

    db_session.add(QuizQuestion(quiz_id=quiz.id, question_id=q1.id))
    db_session.add(QuizQuestion(quiz_id=quiz.id, question_id=q2.id))
    db_session.commit()

    attempt = QuizAttempt(student_id=test_user.id, quiz_id=quiz.id)
    db_session.add(attempt)
    db_session.commit()

    # First question picked
    first_q = select_next_question(db_session, quiz.id, test_user.id, attempt.id)
    assert first_q is not None

    # Simulate answering first question
    ans = AttemptAnswer(
        attempt_id=attempt.id,
        question_id=first_q.id,
        selected_index=1,
        is_correct=True,
    )
    db_session.add(ans)
    db_session.commit()

    # Second question must be the other one
    second_q = select_next_question(db_session, quiz.id, test_user.id, attempt.id)
    assert second_q is not None
    assert second_q.id != first_q.id

    # Simulate answering second question
    ans2 = AttemptAnswer(
        attempt_id=attempt.id,
        question_id=second_q.id,
        selected_index=1,
        is_correct=True,
    )
    db_session.add(ans2)
    db_session.commit()

    # Quiz is now complete
    third_q = select_next_question(db_session, quiz.id, test_user.id, attempt.id)
    assert third_q is None
