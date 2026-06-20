"""
Verification script for Phase 5 — ML Loop.
Tests: MLflow registry, model predictions, SHAP explanations, A/B split.

Does NOT require the FastAPI server to be running.

Usage:
    source .venv/bin/activate
    python verify_ml.py
"""
import os
import warnings
warnings.filterwarnings("ignore")

import mlflow
import mlflow.xgboost
import pandas as pd
from pathlib import Path

MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
MODEL_NAME = "streamlake-churn-model"
PARQUET    = Path("feature_store/data/user_features.parquet")

print("=" * 55)
print("  StreamLake — ML Loop Verification (Phase 5)")
print("=" * 55)

# ── 1. MLflow Model Registry ──────────────────────────────
print("\n── MLflow Model Registry ─────────────────────────────")
mlflow.set_tracking_uri(MLFLOW_URI)
client = mlflow.MlflowClient()
try:
    versions = client.get_latest_versions(MODEL_NAME)
    for v in versions:
        run = client.get_run(v.run_id)
        m   = run.data.metrics
        print(f"  Model   : {MODEL_NAME} v{v.version}")
        print(f"  Run ID  : {v.run_id[:12]}...")
        print(f"  AUC     : {m.get('auc', 'N/A')}")
        print(f"  F1      : {m.get('f1', 'N/A')}")
        print(f"  Precision: {m.get('precision', 'N/A')}")
        print(f"  Recall  : {m.get('recall', 'N/A')}")
        print(f"  Churn % : {m.get('churn_rate_test', 'N/A')}")
except Exception as e:
    print(f"  ERROR: {e}")
    print("  Run: python -m ml.train")
    exit(1)

# ── 2. Load model and predict ─────────────────────────────
print("\n── Model Predictions ─────────────────────────────────")
try:
    model = mlflow.xgboost.load_model(f"models:/{MODEL_NAME}/latest")
    df    = pd.read_parquet(PARQUET)

    from ml.train import FEATURE_COLS
    X     = df[FEATURE_COLS]
    probs = model.predict_proba(X)[:, 1]
    df["churn_probability"] = probs

    high_risk = (probs >= 0.7).sum()
    low_risk  = (probs < 0.3).sum()
    print(f"  Total users scored : {len(df):,}")
    print(f"  High risk (≥0.70)  : {high_risk:,} ({high_risk/len(df)*100:.1f}%)")
    print(f"  Low risk  (<0.30)  : {low_risk:,}  ({low_risk/len(df)*100:.1f}%)")

    # Show sample predictions
    sample = df[["user_id", "purchase_count_24h", "event_count_24h",
                 "days_since_last_purchase", "churn_probability"]].head(6)
    print(f"\n  Sample predictions:")
    print(sample.to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")

# ── 3. SHAP explanation ───────────────────────────────────
print("\n── SHAP Explanation (single user) ────────────────────")
try:
    from ml.shap_explainer import explain_prediction
    sample_user = df.sample(1, random_state=7)
    X_single    = sample_user[FEATURE_COLS]
    explanation = explain_prediction(model, X_single)
    uid         = sample_user["user_id"].iloc[0]
    prob        = float(model.predict_proba(X_single)[0][1])
    print(f"  User : {uid}")
    print(f"  Churn probability: {prob:.4f}")
    print(f"  Top 3 driving features:")
    for feat in explanation:
        arrow = "↑" if feat["direction"] == "increases_churn" else "↓"
        print(f"    {arrow} {feat['feature']:<30} SHAP={feat['shap_value']:+.4f}")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 4. A/B Split distribution ─────────────────────────────
print("\n── A/B Split (Champion/Challenger) ───────────────────")
try:
    from ml.ab_splitter import split_stats
    user_ids = df["user_id"].tolist()
    stats    = split_stats(user_ids)
    print(f"  Total users    : {stats['total']:,}")
    print(f"  Champion  (90%): {stats['champion']:,} ({stats['champion_pct']*100:.1f}%)")
    print(f"  Challenger(10%): {stats['challenger']:,} ({stats['challenger_pct']*100:.1f}%)")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n✓ Phase 5 ML verification complete\n")
print("  To start the inference API:")
print("  uvicorn serving.app:app --reload --port 8000\n")
