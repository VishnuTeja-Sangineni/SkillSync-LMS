"""
SkillSync LMS — Main FastAPI Application

This is the entry point for the application. Run it with:
    uvicorn app.main:app --reload

The app:
- Loads configuration from environment variables
- Sets up structured JSON logging
- Configures CORS for cross-origin frontend access
- Includes all API routers under /api/v1
- Serves the frontend as static files at the root
- Provides /api/v1/health and /api/v1/ready endpoints
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import engine, SessionLocal
from app.logging_config import setup_logging, request_id_ctx, generate_request_id

# ── Logging setup ─────────────────────────────────────────────────────
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run tasks on startup and shutdown."""
    logger.info(
        "Starting SkillSync LMS (env=%s, db=%s)",
        settings.ENVIRONMENT,
        settings.DATABASE_URL[:50] + "..." if len(settings.DATABASE_URL) > 50 else settings.DATABASE_URL,
    )
    if settings.AUTO_MIGRATE and not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            from alembic.config import Config
            from alembic import command
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations applied successfully on startup")
        except Exception as e:
            logger.warning("Startup migration notice: %s", e)
    yield
    logger.info("Shutting down SkillSync LMS")


# ── Create the FastAPI app ────────────────────────────────────────────
app = FastAPI(
    title="SkillSync LMS",
    description="Adaptive Learning Platform with ML-powered predictions and recommendations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request ID Middleware ─────────────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request for log tracing."""
    rid = request.headers.get("X-Request-ID", generate_request_id())
    request_id_ctx.set(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


# ── API Routers ───────────────────────────────────────────────────────
from app.routers import (  # noqa: E402
    auth,
    admin,
    courses,
    lessons,
    questions,
    quizzes,
    progress,
    analytics,
    predictions,
    recommendations,
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(lessons.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(quizzes.router, prefix="/api/v1")
app.include_router(progress.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")


# ── Health & Readiness ────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["health"])
def health():
    """Liveness check — returns 200 if the process is running."""
    return {"status": "healthy", "service": "skillsync-lms"}


@app.get("/api/v1/ready", tags=["health"])
def ready():
    """
    Readiness check — returns 200 only if the database is reachable.
    Used by container orchestrators to know when the app can accept traffic.
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        logger.error("Readiness check failed: %s", str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "disconnected", "error": str(e)},
        )


# ── Global Exception Handler ─────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a consistent JSON error."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )


# ── Serve Frontend Static Files ──────────────────────────────────────
# The frontend directory is served at the root, so the app works as a
# single deployment. The API routes (/api/v1/*) take precedence.
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
