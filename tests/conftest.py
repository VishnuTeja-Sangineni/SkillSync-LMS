"""
Pytest fixtures for SkillSync LMS tests.

Provides:
- An isolated temporary SQLite database for each test session
- A FastAPI TestClient
- Helper functions to create users and get auth tokens
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Override settings BEFORE importing app modules so the test DB is used
os.environ["DATABASE_URL"] = "sqlite:///./test_skillsync.db"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ENVIRONMENT"] = "dev"

from fastapi.testclient import TestClient
from app.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403 — import all models for table creation


# ── Test Database Setup ───────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///./test_skillsync.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Dependency override that uses the test database."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the database dependency for all tests
app.dependency_overrides[get_db] = override_get_db


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables at the start of the test session, drop at the end."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    # Clean up the test database file
    import pathlib
    db_file = pathlib.Path("./test_skillsync.db")
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


@pytest.fixture(autouse=True)
def clean_tables():
    """Clear all table data before each test for isolation."""
    db = TestSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


@pytest.fixture
def client():
    """Provide a FastAPI TestClient."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    """Provide a database session for direct DB operations in tests."""
    db = TestSessionLocal()
    yield db
    db.close()


# ── Helper Functions ──────────────────────────────────────────────────

def register_user(client: TestClient, name="Test User", email="test@test.com",
                  password="Test@123", role="student") -> dict:
    """Register a user and return the response JSON (includes token)."""
    resp = client.post("/api/v1/auth/register", json={
        "name": name,
        "email": email,
        "password": password,
        "role": role,
    })
    return resp


def get_auth_header(client: TestClient, email="test@test.com",
                    password="Test@123") -> dict:
    """Login and return an Authorization header dict."""
    resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_test_users(client: TestClient) -> dict:
    """Create one user of each role and return their auth headers."""
    headers = {}

    register_user(client, "Admin User", "admin@test.com", "Admin@123", "admin")
    headers["admin"] = get_auth_header(client, "admin@test.com", "Admin@123")

    register_user(client, "Teacher User", "teacher@test.com", "Teacher@123", "teacher")
    headers["teacher"] = get_auth_header(client, "teacher@test.com", "Teacher@123")

    register_user(client, "Student User", "student@test.com", "Student@123", "student")
    headers["student"] = get_auth_header(client, "student@test.com", "Student@123")

    return headers


@pytest.fixture
def users_and_headers(client):
    """Fixture providing auth headers for admin, teacher, and student."""
    return create_test_users(client)


@pytest.fixture
def auth_headers_admin(users_and_headers):
    return users_and_headers["admin"]


@pytest.fixture
def auth_headers_teacher(users_and_headers):
    return users_and_headers["teacher"]


@pytest.fixture
def auth_headers_student(users_and_headers):
    return users_and_headers["student"]


@pytest.fixture
def test_user(db_session):
    user = User(
        name="Unit Test Student",
        email="unittest_student@example.com",
        password_hash="hash",
        role="student",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_teacher(db_session):
    teacher = db_session.query(User).filter(User.email == "teacher@test.com").first()
    if not teacher:
        teacher = User(
            name="Teacher User",
            email="teacher@test.com",
            password_hash="hash",
            role="teacher",
        )
        db_session.add(teacher)
        db_session.commit()
        db_session.refresh(teacher)
    return teacher


@pytest.fixture
def test_student(db_session):
    student = db_session.query(User).filter(User.email == "student@test.com").first()
    if not student:
        student = User(
            name="Student User",
            email="student@test.com",
            password_hash="hash",
            role="student",
        )
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)
    return student


@pytest.fixture
def test_course(db_session, test_teacher):
    course = Course(
        title="Intro to Computing",
        description="Core computing concepts",
        teacher_id=test_teacher.id,
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course

