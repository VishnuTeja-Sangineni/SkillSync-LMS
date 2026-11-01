"""
Application configuration via pydantic-settings.

All settings are loaded from environment variables (or a .env file).
This is the single source of truth for configuration — no hardcoded secrets.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    """
    Central configuration for SkillSync LMS.

    Every field maps to an environment variable of the same name (case-insensitive).
    For example, DATABASE_URL in .env becomes settings.DATABASE_URL.
    """

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./skillsync.db"
    AUTO_MIGRATE: bool = True

    # ── Security ──────────────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "*"

    # ── Environment ───────────────────────────────────────────────────
    ENVIRONMENT: str = "dev"  # "dev" or "prod"

    # ── ML Model ──────────────────────────────────────────────────────
    MODEL_PATH: str = "ml/artifacts/model.joblib"
    MODEL_STORAGE: str = "local"  # "local" or "s3"

    # ── AWS (optional, for S3 model storage) ──────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"

    # ── Logging ───────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Server ────────────────────────────────────────────────────────
    PORT: int = 8000

    @field_validator("SECRET_KEY")
    @classmethod
    def check_secret_key(cls, v: str, info) -> str:
        """In production, refuse to start with the default dev key."""
        # info.data may not have ENVIRONMENT yet depending on field order,
        # so we check the env var directly as a fallback.
        import os
        env = os.getenv("ENVIRONMENT", "dev")
        if env == "prod" and v == "dev-secret-key-change-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from the default in production! "
                "Set a strong, random SECRET_KEY environment variable."
            )
        return v

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string to a list."""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Singleton instance — import this everywhere
settings = Settings()
