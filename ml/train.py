"""
Model training script and pipeline.

Trains a GradientBoostingRegressor to predict final course scores (0–100)
from student activity features, evaluates MAE, R2, and risk classification
metrics, and persists the model artifact via the ModelStorage abstraction.
"""

import sys
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    mean_squared_error,
    classification_report,
)

from app.config import settings
from app.database import SessionLocal
from ml.features import FEATURE_NAMES, build_training_dataset
from ml.storage import get_storage

logger = logging.getLogger(__name__)


def score_to_risk(score: float) -> str:
    """Map final score to risk category."""
    if score >= 70.0:
        return "Low"
    elif score >= 50.0:
        return "Medium"
    else:
        return "High"


def train_model(
    db=None,
    save: bool = True,
    model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Train the performance prediction model on current database records.

    Args:
        db: SQLAlchemy Session. If None, creates a new session.
        save: If True, saves the trained model to ModelStorage.
        model_path: Optional custom path for storage. Defaults to settings.MODEL_PATH.

    Returns:
        Summary dict containing metrics, feature importances, and sample counts.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        features_list, labels, ids = build_training_dataset(db)
        if len(features_list) < 10:
            raise ValueError(
                f"Insufficient training samples ({len(features_list)}). Need at least 10."
            )

        df_X = pd.DataFrame(features_list, columns=FEATURE_NAMES)
        y = np.array(labels, dtype=float)

        # Compute dataset stats for model explanations
        feature_stats = {}
        for col in FEATURE_NAMES:
            feature_stats[col] = {
                "mean": float(df_X[col].mean()),
                "std": float(df_X[col].std()) if df_X[col].std() > 0 else 1.0,
                "median": float(df_X[col].median()),
                "min": float(df_X[col].min()),
                "max": float(df_X[col].max()),
            }

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            df_X, y, test_size=0.2, random_state=42
        )

        model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.08,
            max_depth=4,
            random_state=42,
        )
        model.fit(X_train, y_train)

        # Evaluate regression
        y_pred = model.predict(X_test)
        y_pred_clipped = np.clip(y_pred, 0.0, 100.0)

        mae = float(mean_absolute_error(y_test, y_pred_clipped))
        r2 = float(r2_score(y_test, y_pred_clipped))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_clipped)))

        # Evaluate risk level classification
        y_test_risk = [score_to_risk(s) for s in y_test]
        y_pred_risk = [score_to_risk(s) for s in y_pred_clipped]
        class_report = classification_report(
            y_test_risk, y_pred_risk, output_dict=True, zero_division=0
        )

        # Feature importances
        importances = model.feature_importances_
        feature_importances = {
            name: round(float(imp), 4)
            for name, imp in sorted(
                zip(FEATURE_NAMES, importances), key=lambda x: x[1], reverse=True
            )
        }

        target_path = model_path or settings.MODEL_PATH

        artifact = {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "feature_importances": feature_importances,
            "feature_stats": feature_stats,
            "metrics": {
                "mae": round(mae, 4),
                "r2": round(r2, 4),
                "rmse": round(rmse, 4),
                "classification_report": class_report,
            },
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "n_samples": len(features_list),
        }

        if save:
            storage = get_storage()
            storage.save(artifact, target_path)
            logger.info("Model artifact successfully saved to %s", target_path)

        return {
            "status": "success",
            "samples": len(features_list),
            "metrics": artifact["metrics"],
            "feature_importances": feature_importances,
            "trained_at": artifact["trained_at"],
            "model_path": target_path,
        }

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("Training SkillSync LMS Performance Prediction Model")
    print("=" * 60)

    result = train_model()

    print(f"\nTraining completed on {result['samples']} samples.")
    print("\n--- Regression Metrics ---")
    print(f"  MAE:  {result['metrics']['mae']:.4f}")
    print(f"  RMSE: {result['metrics']['rmse']:.4f}")
    print(f"  R2:   {result['metrics']['r2']:.4f}")

    print("\n--- Feature Importances ---")
    for feat, imp in result["feature_importances"].items():
        print(f"  {feat:<25}: {imp:.4f}")

    print(f"\nModel saved to: {result['model_path']}")
