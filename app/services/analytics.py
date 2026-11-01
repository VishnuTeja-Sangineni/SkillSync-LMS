"""
Analytics computation service for students and courses.

Provides:
- Student-level analytics: decayed topic mastery, score trends (with linear regression slope),
  time spent, active day streaks, and identified weak areas.
- Course-level analytics: class average mastery per topic, score distribution histogram,
  completion rate, and engagement over the last 14 days.
"""

from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Set
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.course import Course, Module, Lesson
from app.models.quiz import Quiz, QuizQuestion
from app.models.progress import Enrollment, QuizAttempt, LessonProgress, TopicMastery
from app.services.mastery import apply_forgetting_decay
from app.schemas.analytics import (
    TopicMasteryItem,
    QuizAttemptSummary,
    ScoreTrend,
    StudentAnalyticsResponse,
    TopicAvgMastery,
    ScoreDistributionBin,
    DailyEngagement,
    CourseAnalyticsResponse,
)


def compute_student_analytics(
    db: Session,
    student_id: int,
    course_id: Optional[int] = None,
) -> StudentAnalyticsResponse:
    """Calculate personalized analytics for a student."""
    user = db.query(User).filter(User.id == student_id).first()
    if not user:
        raise ValueError("Student not found")

    # 1. Topic Mastery with decay applied
    tm_query = db.query(TopicMastery).filter(TopicMastery.student_id == student_id)
    if course_id is not None:
        tm_query = tm_query.filter(TopicMastery.course_id == course_id)
    raw_masteries = tm_query.all()

    now = datetime.now(timezone.utc)
    mastery_items: List[TopicMasteryItem] = []
    weak_areas: List[str] = []

    for tm in raw_masteries:
        decayed = apply_forgetting_decay(tm.mastery, tm.updated_at, current_time=now)
        mastery_items.append(
            TopicMasteryItem(
                topic=tm.topic,
                course_id=tm.course_id,
                raw_mastery=tm.mastery,
                mastery=decayed,
                updated_at=tm.updated_at,
            )
        )
        if decayed < 0.5:
            weak_areas.append(tm.topic)

    # Sort mastery items by decayed mastery ascending
    mastery_items.sort(key=lambda m: m.mastery)
    # Deduplicate weak areas preserving order
    weak_areas = list(dict.fromkeys(weak_areas))

    # 2. Score Trend & Attempts
    attempts_query = (
        db.query(QuizAttempt, Quiz.title)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(QuizAttempt.student_id == student_id, QuizAttempt.max_score > 0)
    )
    if course_id is not None:
        attempts_query = attempts_query.filter(Quiz.course_id == course_id)
    attempts_query = attempts_query.order_by(QuizAttempt.started_at.asc())
    attempt_rows = attempts_query.all()

    attempt_summaries: List[QuizAttemptSummary] = []
    percentages: List[float] = []

    for attempt, quiz_title in attempt_rows:
        pct = round((attempt.score / attempt.max_score) * 100.0, 2)
        percentages.append(pct)
        attempt_summaries.append(
            QuizAttemptSummary(
                attempt_id=attempt.id,
                quiz_id=attempt.quiz_id,
                quiz_title=quiz_title,
                score=attempt.score,
                max_score=attempt.max_score,
                percentage=pct,
                duration_sec=attempt.duration_sec or 0,
                date=attempt.started_at,
            )
        )

    # Compute regression slope on percentage scores
    n = len(percentages)
    if n >= 2:
        x = list(range(n))
        x_mean = (n - 1) / 2.0
        y_mean = sum(percentages) / float(n)
        denom = sum((xi - x_mean) ** 2 for xi in x)
        numer = sum((x[i] - x_mean) * (percentages[i] - y_mean) for i in range(n))
        slope = round(numer / denom, 4) if denom > 0 else 0.0

        if slope > 0.5:
            direction = "improving"
        elif slope < -0.5:
            direction = "declining"
        else:
            direction = "stable"
    else:
        slope = 0.0
        direction = "stable"

    score_trend = ScoreTrend(
        slope=slope,
        direction=direction,
        attempts=attempt_summaries,
    )

    # 3. Time Spent
    # Sum quiz duration
    quiz_duration = sum(att.duration_sec or 0 for att, _ in attempt_rows)

    # Sum lesson progress time
    lp_query = db.query(LessonProgress).filter(LessonProgress.student_id == student_id)
    if course_id is not None:
        lp_query = (
            lp_query.join(Lesson, LessonProgress.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .filter(Module.course_id == course_id)
        )
    lesson_records = lp_query.all()
    lesson_duration = sum(lp.time_spent_sec for lp in lesson_records)
    total_time_spent = quiz_duration + lesson_duration

    # 4. Streak Days Calculation
    active_dates: Set[date] = set()
    for att, _ in attempt_rows:
        if att.started_at:
            active_dates.add(att.started_at.date())
    for lp in lesson_records:
        if lp.last_visited:
            active_dates.add(lp.last_visited.date())

    today = now.date()
    streak = 0
    curr_date = today

    # If active today, count backwards from today; if not active today, check yesterday
    if curr_date not in active_dates:
        curr_date = today - timedelta(days=1)

    while curr_date in active_dates:
        streak += 1
        curr_date -= timedelta(days=1)

    # 5. Lesson counts
    completed_lessons_count = sum(1 for lp in lesson_records if lp.completed)
    if course_id is not None:
        total_lessons_count = (
            db.query(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .filter(Module.course_id == course_id)
            .count()
        )
    else:
        # Enrolled courses total lessons
        enrolled_course_ids = [
            e.course_id
            for e in db.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        ]
        total_lessons_count = (
            db.query(Lesson)
            .join(Module, Lesson.module_id == Module.id)
            .filter(Module.course_id.in_(enrolled_course_ids))
            .count()
            if enrolled_course_ids
            else 0
        )

    return StudentAnalyticsResponse(
        student_id=student_id,
        student_name=user.name,
        course_id=course_id,
        mastery_by_topic=mastery_items,
        score_trend=score_trend,
        total_time_spent_sec=total_time_spent,
        streak_days=streak,
        weak_areas=weak_areas,
        completed_lessons_count=completed_lessons_count,
        total_lessons_count=total_lessons_count,
    )


def compute_course_analytics(
    db: Session,
    course_id: int,
) -> CourseAnalyticsResponse:
    """Calculate course-level class analytics for teachers and admins."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise ValueError("Course not found")

    enrollments = db.query(Enrollment).filter(Enrollment.course_id == course_id).all()
    student_ids = [e.student_id for e in enrollments]
    total_enrolled = len(student_ids)

    if total_enrolled == 0:
        return CourseAnalyticsResponse(
            course_id=course.id,
            course_title=course.title,
            total_enrolled=0,
            avg_completion_pct=0.0,
            topic_masteries=[],
            score_distribution=[
                ScoreDistributionBin(bin="< 50%", count=0, percentage=0.0),
                ScoreDistributionBin(bin="50 - 69%", count=0, percentage=0.0),
                ScoreDistributionBin(bin="70 - 84%", count=0, percentage=0.0),
                ScoreDistributionBin(bin="85 - 100%", count=0, percentage=0.0),
            ],
            engagement_over_time=[],
        )

    now = datetime.now(timezone.utc)

    # 1. Topic Mastery Averages
    mastery_records = (
        db.query(TopicMastery)
        .filter(
            TopicMastery.course_id == course_id,
            TopicMastery.student_id.in_(student_ids),
        )
        .all()
    )

    topic_scores = defaultdict(list)
    for tm in mastery_records:
        decayed = apply_forgetting_decay(tm.mastery, tm.updated_at, current_time=now)
        topic_scores[tm.topic].append(decayed)

    topic_masteries = [
        TopicAvgMastery(
            topic=t,
            avg_mastery=round(sum(scores) / len(scores), 4),
            student_count=len(scores),
        )
        for t, scores in sorted(topic_scores.items())
    ]

    # 2. Score Distribution
    attempts = (
        db.query(QuizAttempt)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(
            Quiz.course_id == course_id,
            QuizAttempt.student_id.in_(student_ids),
            QuizAttempt.max_score > 0,
        )
        .all()
    )

    bin_counts = {
        "< 50%": 0,
        "50 - 69%": 0,
        "70 - 84%": 0,
        "85 - 100%": 0,
    }
    total_attempts = len(attempts)

    for att in attempts:
        pct = (att.score / att.max_score) * 100.0
        if pct < 50:
            bin_counts["< 50%"] += 1
        elif pct < 70:
            bin_counts["50 - 69%"] += 1
        elif pct < 85:
            bin_counts["70 - 84%"] += 1
        else:
            bin_counts["85 - 100%"] += 1

    score_distribution = [
        ScoreDistributionBin(
            bin=b,
            count=c,
            percentage=round((c / total_attempts * 100.0), 1) if total_attempts > 0 else 0.0,
        )
        for b, c in bin_counts.items()
    ]

    # 3. Lesson Completion Rate
    total_lessons = (
        db.query(Lesson)
        .join(Module, Lesson.module_id == Module.id)
        .filter(Module.course_id == course_id)
        .count()
    )
    if total_lessons > 0 and total_enrolled > 0:
        completed_count = (
            db.query(LessonProgress)
            .join(Lesson, LessonProgress.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .filter(
                Module.course_id == course_id,
                LessonProgress.student_id.in_(student_ids),
                LessonProgress.completed == True,
            )
            .count()
        )
        avg_completion = round((completed_count / (total_lessons * total_enrolled)) * 100.0, 1)
    else:
        avg_completion = 0.0

    # 4. Engagement Over Time (Last 14 days)
    today = now.date()
    daily_active: Dict[date, Set[int]] = {
        today - timedelta(days=d): set() for d in range(13, -1, -1)
    }

    fourteen_days_ago = now - timedelta(days=14)

    recent_attempts = (
        db.query(QuizAttempt.student_id, QuizAttempt.started_at)
        .join(Quiz, QuizAttempt.quiz_id == Quiz.id)
        .filter(
            Quiz.course_id == course_id,
            QuizAttempt.student_id.in_(student_ids),
            QuizAttempt.started_at >= fourteen_days_ago,
        )
        .all()
    )
    for sid, started in recent_attempts:
        if started:
            d = started.date()
            if d in daily_active:
                daily_active[d].add(sid)

    recent_lessons = (
        db.query(LessonProgress.student_id, LessonProgress.last_visited)
        .join(Lesson, LessonProgress.lesson_id == Lesson.id)
        .join(Module, Lesson.module_id == Module.id)
        .filter(
            Module.course_id == course_id,
            LessonProgress.student_id.in_(student_ids),
            LessonProgress.last_visited >= fourteen_days_ago,
        )
        .all()
    )
    for sid, visited in recent_lessons:
        if visited:
            d = visited.date()
            if d in daily_active:
                daily_active[d].add(sid)

    engagement_over_time = [
        DailyEngagement(
            date=d.isoformat(),
            active_students=len(students),
        )
        for d, students in sorted(daily_active.items())
    ]

    return CourseAnalyticsResponse(
        course_id=course.id,
        course_title=course.title,
        total_enrolled=total_enrolled,
        avg_completion_pct=avg_completion,
        topic_masteries=topic_masteries,
        score_distribution=score_distribution,
        engagement_over_time=engagement_over_time,
    )
