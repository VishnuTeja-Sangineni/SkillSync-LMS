"""
Hybrid recommendation engine for SkillSync LMS.

Combines:
1. Rule-based recommendations:
   - Weak topics (< 0.5 mastery) -> recommend incomplete lessons and practice quizzes
   - Strong topics (> 0.8 mastery) -> recommend hard challenge quizzes
   - Inactivity (5+ days) -> recommend re-engagement action
   - High risk prediction -> prioritized remediation plan
2. Collaborative filtering:
   - Computes cosine similarity between student mastery vectors in the course
   - Finds similar students who improved in weak topics or achieved high mastery
   - Recommends lessons and quizzes that helped those similar peers
3. Ranking & Deduplication:
   - Merges recommendations, prioritizes by urgency (1 = highest priority),
   - Synthesizes human-readable explanations (e.g. "Your Algebra mastery is 38% and similar students improved after this lesson.")
   - Persists recommendations to the database.
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set

import numpy as np
from sqlalchemy.orm import Session

from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz, Question, QuizQuestion
from app.models.progress import (
    Enrollment,
    QuizAttempt,
    AttemptAnswer,
    LessonProgress,
    TopicMastery,
)
from app.models.prediction import Prediction, Recommendation
from app.services.mastery import apply_forgetting_decay
from ml.predict import predict_student_performance

logger = logging.getLogger(__name__)


def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two 1D numerical vectors."""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def generate_rule_based_recommendations(
    db: Session,
    student_id: int,
    course_id: int,
    prediction: Optional[Prediction] = None,
) -> List[Dict[str, Any]]:
    """Generate recommendations based on deterministic pedagogical rules."""
    recs: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # 1. Topic Mastery analysis
    mastery_records = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.student_id == student_id,
            TopicMastery.course_id == course_id,
        )
        .all()
    )

    decayed_masteries: Dict[str, float] = {}
    for tm in mastery_records:
        decayed = apply_forgetting_decay(tm.mastery, tm.updated_at, current_time=now)
        decayed_masteries[tm.topic] = decayed

    # Query all completed lessons for this student
    completed_lesson_ids = set(
        r[0]
        for r in db.query(LessonProgress.lesson_id)
        .filter(LessonProgress.student_id == student_id, LessonProgress.completed == True)
        .all()
    )

    # Query course lessons grouped by topic
    course_lessons = (
        db.query(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .filter(Module.course_id == course_id)
        .order_by(Lesson.order.asc())
        .all()
    )
    lessons_by_topic: Dict[str, List[Lesson]] = {}
    for l in course_lessons:
        lessons_by_topic.setdefault(l.topic, []).append(l)

    # Query course quizzes grouped by topic
    course_quizzes = (
        db.query(Quiz)
        .filter(Quiz.course_id == course_id)
        .all()
    )

    # Map quiz -> topics covered
    quiz_topics: Dict[int, Set[str]] = {}
    quiz_has_hard: Dict[int, bool] = {}
    for q in course_quizzes:
        qqs = db.query(Question).join(QuizQuestion, Question.id == QuizQuestion.question_id).filter(QuizQuestion.quiz_id == q.id).all()
        topics = set(question.topic for question in qqs)
        quiz_topics[q.id] = topics
        quiz_has_hard[q.id] = any(question.difficulty == "hard" for question in qqs)

    # Check weak topics (< 0.5)
    weak_topics = [(t, m) for t, m in decayed_masteries.items() if m < 0.5]
    weak_topics.sort(key=lambda x: x[1])  # lowest mastery first

    for topic, mastery in weak_topics:
        m_pct = int(round(mastery * 100))
        # Find incomplete lesson in weak topic
        topic_lessons = lessons_by_topic.get(topic, [])
        uncompleted_lessons = [l for l in topic_lessons if l.id not in completed_lesson_ids]
        if uncompleted_lessons:
            rec_lesson = uncompleted_lessons[0]
            recs.append({
                "type": "lesson",
                "target_id": rec_lesson.id,
                "reason": f"Your {topic} mastery is {m_pct}%. Studying '{rec_lesson.title}' will help close knowledge gaps.",
                "priority": 1 if mastery < 0.35 else 2,
            })

        # Find quiz covering this topic
        matching_quizzes = [q for q in course_quizzes if topic in quiz_topics.get(q.id, set())]
        if matching_quizzes:
            recs.append({
                "type": "quiz",
                "target_id": matching_quizzes[0].id,
                "reason": f"Practice your {topic} skills with '{matching_quizzes[0].title}' to increase your mastery above 50%.",
                "priority": 2,
            })

    # Check strong topics (> 0.8)
    strong_topics = [(t, m) for t, m in decayed_masteries.items() if m >= 0.8]
    for topic, mastery in strong_topics:
        m_pct = int(round(mastery * 100))
        # Find quiz with hard questions in this topic
        challenge_quizzes = [
            q for q in course_quizzes
            if topic in quiz_topics.get(q.id, set()) and quiz_has_hard.get(q.id, False)
        ]
        if challenge_quizzes:
            recs.append({
                "type": "quiz",
                "target_id": challenge_quizzes[0].id,
                "reason": f"You have strong {topic} mastery ({m_pct}%). Challenge yourself with advanced questions in '{challenge_quizzes[0].title}'.",
                "priority": 6,
            })

    # Check inactivity (5+ days since last activity)
    recent_attempt = (
        db.query(QuizAttempt.started_at)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(Quiz.course_id == course_id, QuizAttempt.student_id == student_id)
        .order_by(QuizAttempt.started_at.desc())
        .first()
    )
    recent_lesson = (
        db.query(LessonProgress.last_visited)
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .filter(Module.course_id == course_id, LessonProgress.student_id == student_id)
        .order_by(LessonProgress.last_visited.desc())
        .first()
    )

    last_dates = []
    if recent_attempt and recent_attempt[0]:
        last_dates.append(recent_attempt[0])
    if recent_lesson and recent_lesson[0]:
        last_dates.append(recent_lesson[0])

    if last_dates:
        latest = max(last_dates)
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        days_inactive = (now - latest).total_seconds() / 86400.0
        if days_inactive >= 5.0:
            recs.append({
                "type": "action",
                "target_id": None,
                "reason": f"You haven't engaged in {int(days_inactive)} days. Spend 10 minutes reviewing today to avoid forgetting decay!",
                "priority": 1,
            })

    # Check high risk prediction
    if prediction and prediction.risk_level == "High":
        recs.append({
            "type": "action",
            "target_id": None,
            "reason": "Your predicted performance is at high risk. Focus on completing pending lessons and retaking weak topic quizzes.",
            "priority": 1,
        })

    return recs


def generate_collaborative_recommendations(
    db: Session,
    student_id: int,
    course_id: int,
) -> List[Dict[str, Any]]:
    """
    Generate collaborative filtering recommendations by finding peers
    with similar mastery profiles who achieved higher mastery.
    """
    # 1. Get all unique topics in course
    topics_query = (
        db.query(Question.topic)
        .filter(Question.course_id == course_id)
        .distinct()
        .all()
    )
    all_topics = sorted([t[0] for t in topics_query])
    if not all_topics:
        return []

    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}
    dim = len(all_topics)

    # 2. Get all enrolled students
    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    enrolled_ids = [e.student_id for e in enrollments]
    if len(enrolled_ids) <= 1:
        return []

    # 3. Build mastery vectors for all students in this course
    all_masteries = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.course_id == course_id,
            TopicMastery.student_id.in_(enrolled_ids),
        )
        .all()
    )

    student_vectors: Dict[int, np.ndarray] = {
        sid: np.full(dim, 0.5, dtype=float) for sid in enrolled_ids
    }
    for tm in all_masteries:
        if tm.topic in topic_to_idx and tm.student_id in student_vectors:
            student_vectors[tm.student_id][topic_to_idx[tm.topic]] = tm.mastery

    target_vec = student_vectors.get(student_id)
    if target_vec is None:
        return []

    # 4. Find similar peers who achieved higher overall performance
    target_mean = float(np.mean(target_vec))
    peer_similarities = []

    for peer_id, peer_vec in student_vectors.items():
        if peer_id == student_id:
            continue
        sim = compute_cosine_similarity(target_vec, peer_vec)
        peer_mean = float(np.mean(peer_vec))
        # We look for peers with high similarity who have demonstrated improvement/higher mastery
        if sim >= 0.65 and peer_mean >= target_mean:
            peer_similarities.append((sim, peer_mean, peer_id))

    peer_similarities.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top_peers = [p[2] for p in peer_similarities[:5]]

    if not top_peers:
        return []

    # 5. Find what successful peers completed that target student hasn't
    target_completed_lessons = set(
        r[0]
        for r in db.query(LessonProgress.lesson_id)
        .filter(LessonProgress.student_id == student_id, LessonProgress.completed == True)
        .all()
    )

    peer_lessons = (
        db.query(LessonProgress.lesson_id)
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .filter(
            Module.course_id == course_id,
            LessonProgress.student_id.in_(top_peers),
            LessonProgress.completed == True,
            ~LessonProgress.lesson_id.in_(target_completed_lessons) if target_completed_lessons else True,
        )
        .all()
    )

    # Count how many similar peers completed each lesson
    lesson_counts: Dict[int, int] = {}
    for lid in peer_lessons:
        lesson_counts[lid[0]] = lesson_counts.get(lid[0], 0) + 1

    collab_recs = []
    for lid, count in sorted(lesson_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
        lesson = db.query(Lesson).filter(Lesson.id == lid).first()
        if not lesson:
            continue
        target_topic_m = target_vec[topic_to_idx.get(lesson.topic, 0)]
        m_pct = int(round(target_topic_m * 100))
        collab_recs.append({
            "type": "lesson",
            "target_id": lesson.id,
            "reason": f"Recommended because your {lesson.topic} mastery is {m_pct}% and {count} similar students improved after completing '{lesson.title}'.",
            "priority": 3,
        })

    return collab_recs


def get_recommendations_for_student(
    db: Session,
    student_id: int,
    course_id: int,
    limit: int = 5,
    refresh: bool = False,
) -> List[Recommendation]:
    """
    Generate, deduplicate, persist, and return personalized recommendations.

    Args:
        db: SQLAlchemy Session.
        student_id: Student User ID.
        course_id: Course ID.
        limit: Maximum recommendations to return (default 5).
        refresh: If True, regenerates recommendations even if recently created.

    Returns:
        List of persisted Recommendation model instances.
    """
    now = datetime.now(timezone.utc)

    # Check if recent recommendations already exist (within last 6 hours) unless refresh requested
    if not refresh:
        existing = (
            db.query(Recommendation)
            .filter(
                Recommendation.student_id == student_id,
                Recommendation.course_id == course_id,
            )
            .order_by(Recommendation.priority.asc(), Recommendation.created_at.desc())
            .limit(limit)
            .all()
        )
        if existing:
            # Check age of newest
            age_hours = (now - existing[0].created_at.replace(tzinfo=timezone.utc) if existing[0].created_at.tzinfo is None else now - existing[0].created_at).total_seconds() / 3600.0
            if age_hours < 6.0:
                return existing

    # Predict performance to inform recommendations
    pred = predict_student_performance(db, student_id=student_id, course_id=course_id)

    # 1. Rule-based
    rule_recs = generate_rule_based_recommendations(db, student_id, course_id, prediction=pred)

    # 2. Collaborative
    collab_recs = generate_collaborative_recommendations(db, student_id, course_id)

    # 3. Merge & Deduplicate
    # Key on (type, target_id)
    seen_keys: Set[Tuple[str, Optional[int]]] = set()
    merged: List[Dict[str, Any]] = []

    # Priority queue: sort all by priority ascending
    all_candidates = rule_recs + collab_recs
    all_candidates.sort(key=lambda x: x["priority"])

    for item in all_candidates:
        key = (item["type"], item["target_id"])
        if item["target_id"] is not None:
            if key in seen_keys:
                continue
            seen_keys.add(key)
        else:
            # For actions (target_id is None), deduplicate by reason prefix
            action_key = (item["type"], item["reason"][:20])
            if action_key in seen_keys:
                continue
            seen_keys.add(action_key)

        merged.append(item)
        if len(merged) >= limit:
            break

    # 4. Clear old recommendations for this (student, course) and persist fresh ones
    db.query(Recommendation).filter(
        Recommendation.student_id == student_id,
        Recommendation.course_id == course_id,
    ).delete()

    persisted_recs = []
    for item in merged:
        rec = Recommendation(
            student_id=student_id,
            course_id=course_id,
            type=item["type"],
            target_id=item["target_id"],
            reason=item["reason"],
            priority=item["priority"],
            created_at=now,
        )
        db.add(rec)
        persisted_recs.append(rec)

    db.commit()
    for r in persisted_recs:
        db.refresh(r)

    logger.info("Generated %d recommendations for student %d in course %d", len(persisted_recs), student_id, course_id)
    return persisted_recs
