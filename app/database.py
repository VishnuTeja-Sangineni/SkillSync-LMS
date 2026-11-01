"""
Database engine, session factory, and declarative base.

Supports both SQLite (local dev) and PostgreSQL (cloud) through a single
DATABASE_URL environment variable. Pool settings are applied only for
PostgreSQL; SQLite gets its own connection arguments.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


def _build_engine():
    """
    Create a SQLAlchemy engine from DATABASE_URL.

    - SQLite: enables WAL mode and foreign keys for performance and safety.
    - PostgreSQL: uses pool_pre_ping to handle stale connections behind
      load balancers or managed databases.
    """
    url = settings.DATABASE_URL

    is_sqlite = url.startswith("sqlite")

    if is_sqlite:
        # SQLite needs check_same_thread=False for FastAPI's async use,
        # and connect_args is only valid for SQLite.
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # Enable WAL mode and foreign keys on every connection
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        # PostgreSQL (or any other DB): use connection pooling settings
        engine = create_engine(
            url,
            pool_pre_ping=True,      # Detect stale connections
            pool_size=5,             # Default pool size
            max_overflow=10,         # Extra connections under load
            echo=False,
        )

    return engine


engine = _build_engine()

# Session factory — each request gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session.

    Usage in a route:
        @router.get("/items")
        def list_items(db: Session = Depends(get_db)):
            ...

    The session is automatically closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
