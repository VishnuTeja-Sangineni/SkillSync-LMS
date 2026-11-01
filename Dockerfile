# ==============================================================================
# SkillSync LMS — Multi-Stage Production Dockerfile
# ==============================================================================

# ── Stage 1: Build virtualenv & compile dependencies ─────────────────────────
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies required for compiling C extensions (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Minimal production runtime ──────────────────────────────────────
FROM python:3.11-slim as runner

WORKDIR /app

# Install runtime dependencies (libpq for postgresql, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=prod \
    MODEL_PATH=ml/artifacts/model.joblib \
    MODEL_STORAGE=local \
    AUTO_MIGRATE=true

# Create unprivileged user for security
RUN useradd --create-home --uid 1001 --shell /bin/bash appuser

# Copy application directories and files
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY ml/ ml/
COPY scripts/ scripts/
COPY frontend/ frontend/

# Ensure runtime directories and write permissions for model artifacts
RUN mkdir -p /app/ml/artifacts && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Container health check using the FastAPI health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# Start the application using uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
