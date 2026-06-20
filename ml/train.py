"""
XGBoost churn model training with MLflow tracking.

Label definition:
  churn = 1 → user never purchased (days_since_last_purchase == 999)
              AND low engagement (session_count_24h <= 1)
  churn = 0 → purchased recently OR high-engagement session activity

Usage:
    source .venv/bin/activate
    python -m ml.train
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
from sklearn.metrics import (
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from ml.shap_explainer import log_shap_summary

PARQUET_PATH  = Path("feature_store/data/user_features.parquet")
EXPERIMENT    = "streamlake-churn"
MODEL_NAME    = "streamlake-churn-model"
MLFLOW_URI    = os.getenv("MLFLOW_TRACKING_URI", "mlruns")

FEATURE_COLS = [
    "purchase_count_1h",
    "purchase_count_24h",
    "purchase_count_7d",
    "revenue_sum_1h",
    "revenue_sum_24h",
    "revenue_sum_7d",
    "session_count_24h",
    "event_count_24h",
    "days_since_last_purchase",
]


def build_training_data() -> tuple[pd.DataFrame, pd.Series]:
    """Load Phase 4 features and derive churn label."""
    df = pd.read_parquet(PARQUET_PATH)

    # Churn = never purchased AND low engagement
    # days_since_last_purchase == 999 means the user never purchased
    y = (
        (df["days_since_last_purchase"] == 999) &
        (df["session_count_24h"] <= 1)
    ).astype(int)

    return df[FEATURE_COLS].copy(), y


def train(run_name: str = "xgb-churn-v1") -> str:
    """
    Train XGBoost, log everything to MLflow, register model.
    Returns the MLflow run_id.
    """
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment(EXPERIMENT)

    X, y = build_training_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Handle class imbalance
    n_pos = int(y_train.sum())
    n_neg = int(len(y_train) - n_pos)
    scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    params = {
        "n_estimators":     300,
        "max_depth":        4,
        "learning_rate":    0.05,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": round(scale_pos_weight, 4),
        "eval_metric":      "auc",
        "use_label_encoder": False,
        "random_state":     42,
    }

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        mlflow.log_param("feature_cols", FEATURE_COLS)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))
        mlflow.log_param("churn_rate_train", round(float(y_train.mean()), 4))

        model = XGBClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(int)

        metrics = {
            "auc":            round(float(roc_auc_score(y_test, y_prob)), 4),
            "f1":             round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
            "precision":      round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
            "recall":         round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
            "churn_rate_test":round(float(y_test.mean()), 4),
        }
        mlflow.log_metrics(metrics)

        # Feature importance (XGBoost gain)
        importance = dict(zip(FEATURE_COLS, model.feature_importances_))
        for feat, imp in importance.items():
            mlflow.log_metric(f"importance_{feat}", round(float(imp), 6))

        # SHAP summary logged as artifact
        log_shap_summary(model, X_test, run)

        # Save training baseline for PSI drift detection (Phase 6)
        baseline = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "n_samples":   len(X_train),
            "features":    {},
        }
        for feat in FEATURE_COLS:
            vals = X_train[feat].values.astype(float)
            counts, edges = np.histogram(vals, bins=10)
            baseline["features"][feat] = {
                "bin_edges":  edges.tolist(),
                "bin_counts": counts.tolist(),
                "mean": round(float(vals.mean()), 6),
                "std":  round(float(vals.std()),  6),
                "p50":  round(float(np.median(vals)), 6),
            }
        baseline_path = Path("serving/training_baseline.json")
        baseline_path.write_text(json.dumps(baseline, indent=2))
        mlflow.log_artifact(str(baseline_path), "baseline")

        # Register model in MLflow Model Registry
        mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        print(f"\n{'─'*45}")
        print(f"  Run ID  : {run.info.run_id[:8]}...")
        print(f"  AUC     : {metrics['auc']}")
        print(f"  F1      : {metrics['f1']}")
        print(f"  Precision: {metrics['precision']}")
        print(f"  Recall  : {metrics['recall']}")
        print(f"  Churn % : {metrics['churn_rate_test']*100:.1f}%")
        print(f"  Model   : {MODEL_NAME} (registered)")
        print(f"{'─'*45}\n")

        return run.info.run_id


if __name__ == "__main__":
    train()
