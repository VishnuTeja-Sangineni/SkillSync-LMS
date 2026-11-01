"""
Adaptive Quiz Engine.

Selects the next question for a student in a quiz based on their current
topic mastery, with forgetting decay accounted for:
- Mastery < 0.4 -> easy
- 0.4 <= Mastery <= 0.7 -> medium
- Mastery > 0.7 -> hard

Avoids repeats within the same quiz attempt, and falls back gracefully
if questions of the ideal difficulty are exhausted.
"""

from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import QuizAttempt, AttemptAnswer, TopicMastery
from app.services.mastery import apply_forgetting_decay

DIFF_RANK = {"easy": 0, "medium": 1, "hard": 2}


def get_recommended_difficulty(mastery: float) -> str:
    """Map topic mastery to recommended question difficulty."""
    if mastery < 0.4:
        return "easy"
    elif mastery <= 0.7:
        return "medium"
    else:
        return "hard"


def select_next_question(
    db: Session,
    quiz_id: int,
    student_id: int,
    attempt_id: int,
) -> Optional[Question]:
    """
    Select the next adaptive question for this student and attempt.

    Returns:
        The selected Question instance, or None if all questions in the quiz
        have already been answered.
    """
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        return None

    # 1. Fetch all question IDs belonging to this quiz
    quiz_questions = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .all()
    )
    all_question_ids = [qq.question_id for qq in quiz_questions]
    if not all_question_ids:
        return None

    # 2. Find question IDs already answered in this attempt
    answered_ids = set(
        row[0]
        for row in db.query(AttemptAnswer.question_id)
        .filter(AttemptAnswer.attempt_id == attempt_id)
        .all()
    )

    # 3. Filter candidate questions
    remaining_ids = [qid for qid in all_question_ids if qid not in answered_ids]
    if not remaining_ids:
        return None

    candidate_questions: List[Question] = (
        db.query(Question)
        .filter(Question.id.in_(remaining_ids))
        .all()
    )
    if not candidate_questions:
        return None

    # 4. Fetch student's topic masteries for topics in candidate questions
    candidate_topics = set(q.topic for q in candidate_questions)
    mastery_records = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.student_id == student_id,
            TopicMastery.course_id == quiz.course_id,
            TopicMastery.topic.in_(candidate_topics),
        )
        .all()
    )

    topic_mastery_map: Dict[str, float] = {}
    for tm in mastery_records:
        decayed = apply_forgetting_decay(tm.mastery, tm.updated_at)
        topic_mastery_map[tm.topic] = decayed

    # 5. Score candidate questions based on difficulty distance to recommended
    scored_candidates = []
    for q in candidate_questions:
        curr_mastery = topic_mastery_map.get(q.topic, 0.5)
        rec_diff = get_recommended_difficulty(curr_mastery)
        rec_rank = DIFF_RANK.get(rec_diff, 1)
        q_rank = DIFF_RANK.get(q.difficulty.lower(), 1)
        penalty = abs(q_rank - rec_rank)
        # Order: lowest penalty first; tie-breaker: question id
        scored_candidates.append((penalty, q.id, q))

    scored_candidates.sort(key=lambda item: (item[0], item[1]))
    return scored_candidates[0][2]
