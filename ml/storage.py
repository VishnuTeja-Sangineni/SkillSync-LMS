"""
Model storage abstraction — cloud-friendly model persistence.

Provides:
- LocalFileStorage: saves/loads joblib models to/from the local filesystem.
- S3Storage: saves/loads joblib models to/from an AWS S3 bucket.

The active backend is selected via the MODEL_STORAGE env var ("local" or "s3").
"""

import io
import os
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

import joblib

logger = logging.getLogger(__name__)


class ModelStorage(ABC):
    """Abstract base class for model persistence backends."""

    @abstractmethod
    def save(self, model: Any, path: str) -> None:
        """Persist a trained model to the given path/key."""
        ...

    @abstractmethod
    def load(self, path: str) -> Any:
        """Load a trained model from the given path/key."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check whether a model exists at the given path/key."""
        ...


class LocalFileStorage(ModelStorage):
    """Save and load models on the local filesystem using joblib."""

    def save(self, model: Any, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, p)
        logger.info("Model saved to local path: %s", p)

    def load(self, path: str) -> Any:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Model file not found: {p}")
        model = joblib.load(p)
        logger.info("Model loaded from local path: %s", p)
        return model

    def exists(self, path: str) -> bool:
        return Path(path).exists()


class S3Storage(ModelStorage):
    """Save and load models in an AWS S3 bucket using boto3 + joblib."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 model storage. "
                "Install it with: pip install boto3"
            )

        session_kwargs: dict = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key

        self._s3 = boto3.client("s3", **session_kwargs)
        self._bucket = bucket
        logger.info("S3Storage initialised: bucket=%s region=%s", bucket, region)

    def save(self, model: Any, path: str) -> None:
        buf = io.BytesIO()
        joblib.dump(model, buf)
        buf.seek(0)
        self._s3.put_object(Bucket=self._bucket, Key=path, Body=buf.read())
        logger.info("Model saved to s3://%s/%s", self._bucket, path)

    def load(self, path: str) -> Any:
        resp = self._s3.get_object(Bucket=self._bucket, Key=path)
        buf = io.BytesIO(resp["Body"].read())
        model = joblib.load(buf)
        logger.info("Model loaded from s3://%s/%s", self._bucket, path)
        return model

    def exists(self, path: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=path)
            return True
        except Exception:
            return False


def get_storage() -> ModelStorage:
    """
    Factory: return the correct storage backend based on MODEL_STORAGE env var.
    """
    from app.config import settings

    if settings.MODEL_STORAGE.lower() == "s3":
        return S3Storage(
            bucket=settings.AWS_S3_BUCKET,
            region=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
        )
    return LocalFileStorage()
