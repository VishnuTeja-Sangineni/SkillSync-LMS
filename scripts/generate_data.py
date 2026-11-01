"""
Synthetic data generator for SkillSync LMS.

Builds a realistic demo dataset (courses, questions, ~150 students, ten weeks
of learning activity) so the analytics, prediction and recommendation features
have something meaningful to work with.

How the simulation works
------------------------
Every student has two hidden traits that are NOT stored anywhere:
  * ability    - how well they really understand the material (0-1)
  * engagement - how often they show up and study (0-1)
plus an engagement *profile* that shapes their ten-week trajectory:
  steady (55%), improving (15%), declining (15%), dropout (15%)

Each week a student is active with some probability, and each active session
is either a lesson or a quiz. Whether an answer is correct depends on the
student's ability for that topic versus the question's difficulty, and
practising slowly raises ability. Topic mastery is updated with the REAL
formula from app/services/mastery.py, and quiz questions are picked with the
same mastery -> difficulty rule the adaptive engine uses.

The final course score (the label the ML model will learn to predict) comes
from the hidden traits plus noise, so patterns are learnable but not perfect.

Everything is deterministic for a given seed.
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import (
    AttemptAnswer, Course, Enrollment, FinalGrade, Lesson, LessonProgress,
    Module, Question, Quiz, QuizAttempt, QuizQuestion, TopicMastery, User,
)
from app.services.mastery import compute_mastery_update
from scripts.course_content import COURSES, LESSONS
from scripts.question_bank import DIFFICULTIES, generate_topic_questions

WEEKS = 10
DIFF_LEVEL = {"easy": 0.30, "medium": 0.55, "hard": 0.80}
BASE_SECONDS = {"easy": 25, "medium": 40, "hard": 60}
PROFILES = [("steady", 0.55), ("improving", 0.15), ("declining", 0.15), ("dropout", 0.15)]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Karthik", "Siddharth", "Ishaan", "Kabir", "Dev",
    "Ananya", "Diya", "Meera", "Saanvi", "Isha", "Kavya", "Riya", "Nisha", "Tara", "Pooja",
    "Liam", "Noah", "Emma", "Olivia", "Mia", "Lucas", "Sofia", "Ethan", "Zara", "Omar",
    "Hana", "Yuki", "Chen", "Amara", "Leila", "Mateo", "Elena", "Nikhil", "Sneha", "Farah",
]
LAST_NAMES = [
    "Sharma", "Reddy", "Patel", "Iyer", "Nair", "Gupta", "Rao", "Khan", "Singh", "Mehta",
    "Das", "Joshi", "Menon", "Verma", "Kapoor", "Bose", "Chopra", "Naidu", "Shah", "Pillai",
    "Smith", "Garcia", "Kim", "Nguyen", "Brown", "Silva", "Ali", "Tanaka", "Costa", "Ivanov",
]


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


# ── Course content ────────────────────────────────────────────────────

@dataclass
class TopicData:
    name: str
    module: Module
    lessons: List[Lesson]
    questions: Dict[str, List[Question]]  # difficulty -> questions
    quiz: Quiz


@dataclass
class CourseData:
    course: Course
    topics: List[TopicData]
    final_quiz: Quiz
    final_questions: List[Question]

    @property
    def total_lessons(self) -> int:
        return sum(len(t.lessons) for t in self.topics)


def build_courses(db: Session, rng: random.Random, teachers: Dict[str, User]) -> List[CourseData]:
    """Create all courses, modules, lessons, questions and quizzes."""
    result = []
    for spec in COURSES:
        course = Course(title=spec["title"], description=spec["description"],
                        teacher_id=teachers[spec["teacher"]].id)
        db.add(course)
        db.flush()

        topics: List[TopicData] = []
        for order, topic_name in enumerate(spec["topics"]):
            module = Module(course_id=course.id, title=topic_name, order=order)
            db.add(module)
            db.flush()

            lessons = []
            for lorder, (title, content, minutes) in enumerate(LESSONS[topic_name]):
                lesson = Lesson(module_id=module.id, title=title, content=content,
                                topic=topic_name, est_minutes=minutes, order=lorder)
                db.add(lesson)
                lessons.append(lesson)

            by_diff: Dict[str, List[Question]] = {d: [] for d in DIFFICULTIES}
            all_q = []
            for q in generate_topic_questions(rng, topic_name):
                question = Question(course_id=course.id, topic=topic_name, difficulty=q["difficulty"],
                                    text=q["text"], options_json=q["options"], correct_index=q["correct_index"])
                db.add(question)
                by_diff[q["difficulty"]].append(question)
                all_q.append(question)
            db.flush()

            quiz = Quiz(course_id=course.id, module_id=module.id, title=f"{topic_name} Checkpoint")
            db.add(quiz)
            db.flush()
            db.add_all([QuizQuestion(quiz_id=quiz.id, question_id=q.id) for q in all_q])
            topics.append(TopicData(topic_name, module, lessons, by_diff, quiz))

        final_questions = []
        for t in topics:
            for d in DIFFICULTIES:
                final_questions.append(rng.choice(t.questions[d]))
        final_quiz = Quiz(course_id=course.id, module_id=None, title=f"{spec['title']} Final Exam")
        db.add(final_quiz)
        db.flush()
        db.add_all([QuizQuestion(quiz_id=final_quiz.id, question_id=q.id) for q in final_questions])
        result.append(CourseData(course, topics, final_quiz, final_questions))
    db.flush()
    return result


# ── Student simulation ────────────────────────────────────────────────

@dataclass
class StudentTraits:
    user: User
    ability: float
    engagement: float
    profile: str
    drop_week: int
    courses: List[int]  # indexes into the course list


def weekly_activity_probability(profile: str, e: float, week: int, drop_week: int) -> float:
    """Chance that a student studies at all in a given week."""
    if profile == "steady":
        p = 0.25 + 0.70 * e
    elif profile == "improving":
        p = 0.15 + 0.50 * e + 0.35 * (week / (WEEKS - 1))
    elif profile == "declining":
        p = (0.60 + 0.35 * e) * (1 - 0.85 * week / (WEEKS - 1))
    else:  # dropout
        p = (0.30 + 0.65 * e) if week < drop_week else 0.02
    return _clip(p, 0.0, 0.98)


def difficulty_for_mastery(mastery: float) -> str:
    """Same rule as the adaptive engine: <0.4 easy, 0.4-0.7 medium, >0.7 hard."""
    if mastery < 0.4:
        return "easy"
    if mastery <= 0.7:
        return "medium"
    return "hard"


@dataclass
class SimResult:
    final_score: float
    active_weeks: int
    completed_lessons: int
    attempts: int


def simulate_course(db: Session, rng: random.Random, traits: StudentTraits, cdata: CourseData,
                    enrolled_at: datetime, now: datetime) -> SimResult:
    """Simulate one student's ten weeks in one course and add all rows to the session."""
    student_id = traits.user.id
    topics = cdata.topics
    affinity = {t.name: rng.gauss(0, 0.08) for t in topics}
    gain = {t.name: 0.0 for t in topics}
    mastery: Dict[str, float] = {}
    last_practised: Dict[str, datetime] = {}
    progress: Dict[int, LessonProgress] = {}
    quizzes_taken = {t.name: 0 for t in topics}
    ptr, final_taken, active_weeks, n_attempts = 0, False, 0, 0

    def ability_for(topic: str) -> float:
        return _clip(traits.ability + affinity[topic] + gain[topic])

    def run_quiz(quiz: Quiz, questions: Optional[List[Question]], topic: Optional[TopicData], t0: datetime):
        nonlocal n_attempts
        used, answers, t = set(), [], t0
        attempt = QuizAttempt(student_id=student_id, quiz_id=quiz.id, started_at=t0, score=0.0, max_score=0.0)
        n_q = len(questions) if questions is not None else 8
        for k in range(n_q):
            if questions is not None:
                q = questions[k]
            else:
                want = difficulty_for_mastery(mastery.get(topic.name, 0.5))
                order = [want] + [d for d in DIFFICULTIES if d != want]
                q = next((c for d in order for c in topic.questions[d] if c.id not in used), None)
                if q is None:
                    break
                used.add(q.id)
            p_correct = 0.25 + 0.75 * _sigmoid((ability_for(q.topic) - DIFF_LEVEL[q.difficulty]) * 7)
            correct = rng.random() < p_correct
            chosen = q.correct_index if correct else rng.choice(
                [i for i in range(len(q.options_json)) if i != q.correct_index])
            secs = max(3, int(BASE_SECONDS[q.difficulty] * rng.lognormvariate(0, 0.35)
                              * (1.0 if correct else 1.25) * (1.15 - 0.3 * ability_for(q.topic))))
            t += timedelta(seconds=secs)
            db.add(AttemptAnswer(attempt=attempt, question_id=q.id, selected_index=chosen,
                                 is_correct=correct, time_taken_sec=secs))
            mastery[q.topic] = compute_mastery_update(mastery.get(q.topic, 0.5), correct, q.difficulty)
            gain[q.topic] += 0.004
            last_practised[q.topic] = t
            attempt.score += 1.0 if correct else 0.0
            attempt.max_score += 1.0
        attempt.duration_sec = int((t - t0).total_seconds())
        attempt.finished_at = t
        db.add(attempt)
        n_attempts += 1

    def do_lesson(lesson: Lesson, t: datetime, topic: str):
        spent = int(lesson.est_minutes * 60 * rng.lognormvariate(0, 0.3) * (0.5 + 0.5 * traits.engagement))
        done = rng.random() < 0.55 + 0.40 * traits.engagement
        row = progress.get(lesson.id)
        if row is None:
            row = LessonProgress(student_id=student_id, lesson_id=lesson.id, completed=False,
                                 time_spent_sec=0, last_visited=t)
            progress[lesson.id] = row
            db.add(row)
        row.time_spent_sec += spent
        row.last_visited = t
        if done and not row.completed:
            row.completed = True
            gain[topic] += 0.03

    # Walk through the ten weeks
    for week in range(WEEKS):
        if rng.random() > weekly_activity_probability(traits.profile, traits.engagement, week, traits.drop_week):
            continue
        n_sessions = 1 + (rng.random() < 0.2 + 0.5 * traits.engagement) + (rng.random() < 0.3 * traits.engagement)
        times = sorted(
            enrolled_at + timedelta(days=7 * week + rng.randint(0, 6), hours=rng.randint(1, 14),
                                    minutes=rng.randint(0, 59))
            for _ in range(n_sessions)
        )
        times = [t for t in times if t <= now - timedelta(hours=1)]
        if not times:
            continue
        active_weeks += 1
        for t in times:
            if ptr < len(topics):
                topic = topics[ptr]
                left = [l for l in topic.lessons if not (progress.get(l.id) and progress[l.id].completed)]
                skip_ahead = quizzes_taken[topic.name] == 0 and rng.random() < 0.2
                if left and not skip_ahead:
                    do_lesson(left[0], t, topic.name)
                else:
                    run_quiz(topic.quiz, None, topic, t)
                    quizzes_taken[topic.name] += 1
                    if mastery.get(topic.name, 0.5) >= 0.65 or quizzes_taken[topic.name] >= 2:
                        ptr += 1
            elif not final_taken:
                run_quiz(cdata.final_quiz, cdata.final_questions, None, t)
                final_taken = True
            elif rng.random() < 0.5:
                weakest = min(topics, key=lambda x: mastery.get(x.name, 0.5))
                run_quiz(weakest.quiz, None, weakest, t)

    # Persist topic mastery (stored value is pre-decay; decay is applied when read)
    for name, value in mastery.items():
        db.add(TopicMastery(student_id=student_id, course_id=cdata.course.id, topic=name,
                            mastery=round(value, 4), updated_at=last_practised[name]))

    # Ground-truth final score from hidden traits + behaviour + noise
    knowledge = sum(ability_for(t.name) for t in topics) / len(topics)
    completed = sum(1 for r in progress.values() if r.completed)
    completion = completed / cdata.total_lessons
    raw = 0.70 * knowledge + 0.15 * completion + 0.15 * (active_weeks / WEEKS) + 0.04 + rng.gauss(0, 0.045)
    return SimResult(round(100 * _clip(raw), 1), active_weeks, completed, n_attempts)


# ── Population ────────────────────────────────────────────────────────

def _pick_profile(rng: random.Random) -> str:
    r, acc = rng.random(), 0.0
    for name, w in PROFILES:
        acc += w
        if r <= acc:
            return name
    return "steady"


def populate(db: Session, hashes: Dict[str, str], n_students: int = 150, seed: int = 42,
             now: Optional[datetime] = None) -> dict:
    """
    Fill an EMPTY database with demo data and return a summary.

    hashes must hold bcrypt hashes under the keys "admin", "teacher", "student"
    (computed once by the caller so seeding stays fast).
    """
    now = now or datetime.now(timezone.utc)
    rng = random.Random(seed)

    # Staff and demo accounts
    admin = User(name="Demo Admin", email="admin@skillsync.com", password_hash=hashes["admin"], role="admin")
    teacher = User(name="Demo Teacher", email="teacher@skillsync.com", password_hash=hashes["teacher"], role="teacher")
    teacher2 = User(name="Priya Nair", email="priya.nair@skillsync.com", password_hash=hashes["teacher"], role="teacher")
    demo = User(name="Demo Student", email="student@skillsync.com", password_hash=hashes["student"], role="student")
    db.add_all([admin, teacher, teacher2, demo])
    db.flush()
    teachers = {teacher.email: teacher, teacher2.email: teacher2}

    cdata = build_courses(db, random.Random(f"{seed}:content"), teachers)

    # Students (generated accounts share the demo student's password hash)
    students: List[StudentTraits] = [StudentTraits(demo, 0.50, 0.80, "improving", 99, [0, 1])]
    used_emails = set()
    for i in range(n_students - 1):
        srng = random.Random(f"{seed}:student:{i}")
        first, last = srng.choice(FIRST_NAMES), srng.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i + 1}@students.skillsync.com"
        used_emails.add(email)
        user = User(name=f"{first} {last}", email=email, password_hash=hashes["student"], role="student")
        db.add(user)
        ability = _clip(srng.gauss(0.55, 0.17), 0.10, 0.95)
        engagement = _clip(0.85 * srng.betavariate(2.2, 1.8) + 0.15 * ability)
        n_courses = srng.choices([1, 2, 3], weights=[30, 45, 25])[0]
        picked = sorted(srng.sample(range(len(cdata)), n_courses))
        students.append(StudentTraits(user, ability, engagement, _pick_profile(srng),
                                      srng.randint(2, 6), picked))
    db.flush()

    start = now - timedelta(days=WEEKS * 7)
    scores, profile_counts = [], {}
    n_enrollments = 0
    for idx, st in enumerate(students):
        profile_counts[st.profile] = profile_counts.get(st.profile, 0) + 1
        for ci in st.courses:
            srng = random.Random(f"{seed}:sim:{idx}:{ci}")
            enrolled_at = start + timedelta(days=srng.randint(0, 6), hours=srng.randint(8, 20))
            db.add(Enrollment(student_id=st.user.id, course_id=cdata[ci].course.id, enrolled_at=enrolled_at))
            n_enrollments += 1
            res = simulate_course(db, srng, st, cdata[ci], enrolled_at, now)
            db.add(FinalGrade(student_id=st.user.id, course_id=cdata[ci].course.id,
                              final_score=res.final_score, recorded_at=now))
            scores.append(res.final_score)
    db.commit()

    return {
        "students": len(students),
        "courses": len(cdata),
        "enrollments": n_enrollments,
        "profiles": profile_counts,
        "final_scores": scores,
    }
