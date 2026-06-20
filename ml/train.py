"""
XGBoost churn model training with MLflow tracking.

Label definition:
  churn = 1 → user has not purchased in the last 7 days
              (days_since_last_purchase > 7, or 999 meaning never purchased)
  churn = 0 → purchased within the last 7 days

  With synthetic data: the 999 sentinel (never purchased) drives most churn labels.
  With Olist data:     every user has purchased, so the 7-day recency threshold
                       separates one-time/lapsed buyers from repeat buyers.
  The threshold is intentionally kept the same so the same model works with
  both data sources without code changes.

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
    # Olist enrichment features (joined from CSV if available)
    "avg_delivery_delay_days",
    "avg_review_score",
    "avg_payment_installments",
]

ENRICHMENT_PATH = Path("feature_store/data/olist_enrichment.parquet")


OLIST_ORDERS_PATH    = Path("data/olist/olist_orders_dataset.csv")
OLIST_CUSTOMERS_PATH = Path("data/olist/olist_customers_dataset.csv")


def _olist_churn_labels() -> pd.Series | None:
    """
    Derive real churn labels from Olist purchase history.

    A customer who only ever bought once is labelled churned=1.
    A customer who bought two or more times is labelled churned=0.

    Returns a Series indexed by customer_unique_id, or None if the
    Olist CSVs are not present (falls back to synthetic label below).
    """
    if not (OLIST_ORDERS_PATH.exists() and OLIST_CUSTOMERS_PATH.exists()):
        return None

    orders    = pd.read_csv(OLIST_ORDERS_PATH)
    customers = pd.read_csv(OLIST_CUSTOMERS_PATH)

    # Filter to delivered orders only
    orders = orders[orders["order_status"] == "delivered"]

    # Attach customer_unique_id
    orders = orders.merge(
        customers[["customer_id", "customer_unique_id"]],
        on="customer_id", how="left",
    )

    purchase_counts = (
        orders.groupby("customer_unique_id")["order_id"]
        .count()
        .rename("purchase_count")
    )

    # Churn = only ever bought once (never came back)
    labels = (purchase_counts == 1).astype(int)
    labels.index.name = "user_id"
    return labels


def build_training_data() -> tuple[pd.DataFrame, pd.Series]:
    """Load Phase 4 features, join Olist enrichment if available, derive churn label."""
    df = pd.read_parquet(PARQUET_PATH)

    # Join enrichment features when available (delivery delay, review score, installments)
    available_features = [c for c in FEATURE_COLS if c in df.columns]
    if ENRICHMENT_PATH.exists():
        enrichment = pd.read_parquet(ENRICHMENT_PATH)
        df = df.merge(enrichment, on="user_id", how="left")
        new_cols = [c for c in FEATURE_COLS if c in enrichment.columns]
        available_features = [c for c in FEATURE_COLS if c in df.columns]
        print(f"  Enrichment joined: {new_cols}")

    active_features = [c for c in FEATURE_COLS if c in df.columns]

    olist_labels = _olist_churn_labels()

    if olist_labels is not None:
        # Real Olist data path: join on user_id (= customer_unique_id in Olist).
        # Only keep rows that have a real label; synthetic users (USER-XXXXXX)
        # won't appear in Olist and are dropped from training.
        df = df.set_index("user_id")
        df = df.join(olist_labels, how="inner")
        y = df.pop("purchase_count")
        df = df.reset_index(drop=True)
        print(f"  Olist label: {int(y.sum()):,} churned / {int((y==0).sum()):,} retained "
              f"(churn rate {y.mean():.1%})")
    else:
        # Synthetic data fallback: use recency threshold.
        y = (df["days_since_last_purchase"] > 7).astype(int)

    return df[active_features].copy(), y


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
        importance = dict(zip(list(X_train.columns), model.feature_importances_))
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
        for feat in X_train.columns:
            vals = X_train[feat].values.astype(float)
            vals_clean = vals[~np.isnan(vals)]
            if len(vals_clean) == 0:
                continue
            counts, edges = np.histogram(vals_clean, bins=10)
            baseline["features"][feat] = {
                "bin_edges":  edges.tolist(),
                "bin_counts": counts.tolist(),
                "mean": round(float(np.nanmean(vals)), 6),
                "std":  round(float(np.nanstd(vals)),  6),
                "p50":  round(float(np.nanmedian(vals)), 6),
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
