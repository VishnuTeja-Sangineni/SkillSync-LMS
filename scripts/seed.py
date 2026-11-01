"""
Seed the SkillSync LMS database with demo data.

Usage (run from the project root, with your virtual environment active):

    python -m scripts.seed                 # seed an empty database (safe to re-run)
    python -m scripts.seed --students 60   # smaller dataset
    python -m scripts.seed --reset         # WIPE everything, then seed again

Seeding is idempotent: if the demo accounts already exist, nothing happens.

Demo accounts (all generated students share the student password):
    admin@skillsync.com    / Admin@123
    teacher@skillsync.com  / Teacher@123
    student@skillsync.com  / Student@123
"""

import argparse
import sys
from datetime import datetime
from functools import lru_cache
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AttemptAnswer, Course, Enrollment, FinalGrade, Lesson, LessonProgress, Module,
    Prediction, Question, Quiz, QuizAttempt, QuizQuestion, Recommendation,
    TopicMastery, User,
)
from app.security import hash_password
from scripts.generate_data import populate

DEMO_PASSWORDS = {"admin": "Admin@123", "teacher": "Teacher@123", "student": "Student@123"}
DEMO_EMAILS = [
    "admin@skillsync.com", "teacher@skillsync.com", "priya.nair@skillsync.com", "student@skillsync.com",
]

# Children first, so foreign keys are never violated while wiping
_WIPE_ORDER = [
    AttemptAnswer, QuizAttempt, QuizQuestion, Quiz, Question, LessonProgress, Lesson, Module,
    Enrollment, TopicMastery, Prediction, Recommendation, FinalGrade, Course, User,
]

_COUNTED = [User, Course, Module, Lesson, Question, Quiz, QuizQuestion, Enrollment, QuizAttempt,
            AttemptAnswer, LessonProgress, TopicMastery, FinalGrade]


@lru_cache(maxsize=1)
def build_hashes() -> dict:
    """Hash the three demo passwords once (bcrypt is deliberately slow)."""
    return {role: hash_password(pw) for role, pw in DEMO_PASSWORDS.items()}


def table_counts(db: Session) -> dict:
    return {m.__tablename__: db.query(func.count()).select_from(m).scalar() for m in _COUNTED}


def is_seeded(db: Session) -> bool:
    return db.query(User).filter(User.email.in_(DEMO_EMAILS)).count() > 0


def wipe(db: Session) -> None:
    """Delete ALL rows from every application table."""
    for model in _WIPE_ORDER:
        db.query(model).delete(synchronize_session=False)
    db.commit()


def seed_database(db: Session, n_students: int = 150, seed: int = 42, reset: bool = False,
                  now: Optional[datetime] = None) -> dict:
    """
    Seed the database and return a summary dict.

    Returns {"status": "already_seeded"} (and changes nothing) if demo data
    is already present and reset=False.
    """
    if reset:
        wipe(db)
    elif is_seeded(db):
        return {"status": "already_seeded", "counts": table_counts(db)}

    summary = populate(db, build_hashes(), n_students=n_students, seed=seed, now=now)
    summary["status"] = "seeded"
    summary["counts"] = table_counts(db)
    return summary


def ensure_schema() -> None:
    """Make sure the tables exist (runs Alembic migrations, like the app does on startup)."""
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


def _print_summary(summary: dict) -> None:
    if summary["status"] == "already_seeded":
        print("Database already contains demo data. Nothing changed.")
        print("Use --reset to wipe everything and seed again.")
    else:
        print(f"Seeded {summary['students']} students, {summary['courses']} courses, "
              f"{summary['enrollments']} enrollments.")
        scores = summary["final_scores"]
        n = len(scores)
        low = sum(s >= 70 for s in scores)
        high = sum(s < 50 for s in scores)
        print(f"Final scores: mean {sum(scores) / n:.1f} | Low risk {low / n:.0%}, "
              f"Medium {(n - low - high) / n:.0%}, High {high / n:.0%}")
        print("Student engagement profiles:", summary["profiles"])
    print("\nRows per table:")
    for name, count in summary["counts"].items():
        print(f"  {name:<18}{count:>8}")
    print("\nDemo logins:")
    for role, pw in DEMO_PASSWORDS.items():
        print(f"  {role}@skillsync.com  /  {pw}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed SkillSync LMS with demo data")
    parser.add_argument("--students", type=int, default=150, help="number of students (default 150)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    parser.add_argument("--reset", action="store_true", help="wipe ALL existing data first")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt for --reset")
    args = parser.parse_args(argv)

    if args.reset and not args.yes:
        answer = input("This permanently deletes ALL data in the database. Type 'yes' to continue: ")
        if answer.strip().lower() != "yes":
            print("Cancelled.")
            return 1

    from app.database import SessionLocal

    ensure_schema()
    db = SessionLocal()
    try:
        summary = seed_database(db, n_students=args.students, seed=args.seed, reset=args.reset)
    finally:
        db.close()
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
