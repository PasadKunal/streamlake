"""
FastAPI churn prediction inference endpoint.

Endpoints:
  GET  /health              — liveness probe
  GET  /metrics             — Prometheus metrics (scraped by Prometheus on port 9090)
  GET  /model/info          — MLflow model metadata
  GET  /features/{user_id}  — raw feature values from Redis
  POST /predict             — churn probability + SHAP explanation + Prometheus instrumentation

The server loads the XGBoost model from MLflow at startup.
Features are retrieved from the Feast Redis online store (< 10ms).
Each request is A/B split: 90% champion / 10% challenger.

Start server:
    uvicorn serving.app:app --reload --port 8000

Test:
    curl -s -X POST http://localhost:8000/predict \
         -H 'Content-Type: application/json' \
         -d '{"user_id": "USER-007075"}' | python -m json.tool
"""
from __future__ import annotations

import time
import os
from pathlib import Path

import mlflow.xgboost
import pandas as pd
from fastapi import FastAPI, HTTPException
from xgboost import XGBClassifier
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

from feature_store.offline_store import FEATURE_REFS, get_online_features
from ml.ab_splitter import assign as ab_assign
from ml.shap_explainer import explain_prediction
from ml.train import EXPERIMENT, FEATURE_COLS, MODEL_NAME, MLFLOW_URI
from serving.ingest_router import router as ingest_router
from serving.metrics import (
    CHURN_PROBABILITY, DRIFT_ALERT, FEATURE_PSI,
    PREDICTION_LATENCY, PREDICTIONS_TOTAL,
)

app = FastAPI(
    title="StreamLake Churn Prediction API",
    description="Real-time churn probability scoring with SHAP explanations. Accepts order data via webhook or CSV upload.",
    version="1.0.0",
)

app.include_router(ingest_router)

# Models loaded once at startup
_models: dict[str, object] = {}


@app.on_event("startup")
def load_models() -> None:
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = mlflow.MlflowClient()

    try:
        # Champion = latest version
        versions = client.get_latest_versions(MODEL_NAME)
        if not versions:
            raise RuntimeError(f"No registered versions for {MODEL_NAME!r}")

        # Sort by version number; champion = latest, challenger = previous (or same)
        sorted_versions = sorted(versions, key=lambda v: int(v.version))
        champion_uri   = f"models:/{MODEL_NAME}/{sorted_versions[-1].version}"
        challenger_uri = f"models:/{MODEL_NAME}/{sorted_versions[-2].version}" \
                         if len(sorted_versions) >= 2 else champion_uri

        _models["champion"]   = mlflow.xgboost.load_model(champion_uri)
        _models["challenger"] = mlflow.xgboost.load_model(challenger_uri)
        _models["_champion_version"]   = sorted_versions[-1].version
        _models["_challenger_version"] = sorted_versions[-2].version \
                                         if len(sorted_versions) >= 2 else sorted_versions[-1].version
        print(f"Models loaded from MLflow — champion v{_models['_champion_version']}, "
              f"challenger v{_models['_challenger_version']}")

        # Push initial PSI scores to Prometheus
        try:
            from serving.drift_monitor import compute_drift_report, push_psi_to_prometheus
            report = compute_drift_report()
            push_psi_to_prometheus(report)
            print(f"Drift monitor initialised — alert={report['drift_alert']}")
        except Exception as drift_err:
            print(f"Drift monitor skipped: {drift_err}")

    except Exception as e:
        print(f"MLflow registry unavailable ({e}). Trying local model file...")
        model_file = Path("serving/model.xgb")
        if model_file.exists():
            m = XGBClassifier()
            m.load_model(str(model_file))
            _models["champion"]   = m
            _models["challenger"] = m
            _models["_champion_version"]   = "file"
            _models["_challenger_version"] = "file"
            print("Model loaded from serving/model.xgb")
        else:
            print("WARNING: No model available. Run python -m ml.train first.")


# ── Request / Response schemas ────────────────────────────

class PredictRequest(BaseModel):
    user_id: str


class FeatureExplanation(BaseModel):
    feature: str
    shap_value: float
    direction: str


class PredictResponse(BaseModel):
    user_id: str
    churn_probability: float
    churn_prediction: bool
    model_version: str
    ab_group: str
    top_features: list[FeatureExplanation]
    features_used: dict


# ── Endpoints ─────────────────────────────────────────────

@app.get("/metrics", include_in_schema=False)
def metrics():
    """Prometheus metrics scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    return {
        "status":        "ok",
        "models_loaded": list(k for k in _models if not k.startswith("_")),
    }


@app.get("/model/info")
def model_info():
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = mlflow.MlflowClient()
    try:
        versions = client.get_latest_versions(MODEL_NAME)
        return {
            "model_name": MODEL_NAME,
            "versions": [
                {
                    "version":        v.version,
                    "run_id":         v.run_id,
                    "status":         v.status,
                    "creation_time":  v.creation_timestamp,
                }
                for v in versions
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/features/{user_id}")
def get_features(user_id: str):
    try:
        df = get_online_features([user_id])
        row = df[df["user_id"] == user_id]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"No features found for {user_id!r}")
        return row.to_dict(orient="records")[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    if not _models:
        raise HTTPException(status_code=503, detail="Models not loaded. Run python -m ml.train first.")

    # A/B assignment
    ab_group = ab_assign(request.user_id)
    model    = _models.get(ab_group) or _models.get("champion")
    model_version = str(_models.get(f"_{ab_group}_version", "unknown"))

    # Feature retrieval from Redis
    try:
        feat_df = get_online_features([request.user_id])
        feat_row = feat_df[feat_df["user_id"] == request.user_id]
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Feature retrieval failed: {e}")

    if feat_row.empty:
        raise HTTPException(status_code=404, detail=f"No features for user {request.user_id!r}")

    available_cols = [c for c in FEATURE_COLS if c in feat_row.columns]
    missing = [c for c in FEATURE_COLS if c not in feat_row.columns]
    X = feat_row[available_cols].fillna(0)

    if missing:
        for col in missing:
            X[col] = 0
        X = X[FEATURE_COLS]

    # Inference + latency tracking
    t0         = time.perf_counter()
    prob       = float(model.predict_proba(X)[0][1])
    prediction = prob >= 0.5

    # SHAP explanation
    top_features = explain_prediction(model, X)
    latency = time.perf_counter() - t0

    # Prometheus instrumentation
    PREDICTIONS_TOTAL.labels(
        model_version=model_version,
        ab_group=ab_group,
        prediction=str(prediction),
    ).inc()
    PREDICTION_LATENCY.observe(latency)
    CHURN_PROBABILITY.observe(prob)

    return PredictResponse(
        user_id=request.user_id,
        churn_probability=round(prob, 4),
        churn_prediction=prediction,
        model_version=model_version,
        ab_group=ab_group,
        top_features=[FeatureExplanation(**f) for f in top_features],
        features_used=X.iloc[0].to_dict(),
    )
