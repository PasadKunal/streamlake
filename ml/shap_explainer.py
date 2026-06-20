"""
SHAP explainability utilities.

Two use cases:
  1. Training time: log global feature importance summary to MLflow
  2. Inference time: explain a single prediction (top-3 driving features)
"""
from __future__ import annotations

import io

import numpy as np
import pandas as pd
import shap


def log_shap_summary(model, X: pd.DataFrame, mlflow_run) -> None:
    """Compute SHAP values and log summary plot + values to MLflow."""
    import tempfile
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import mlflow

    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    # Summary plot → temp file → MLflow artifact
    fig, _ = plt.subplots(figsize=(8, 5))
    shap.summary_plot(shap_values, X, show=False, plot_type="bar")
    plt.tight_layout()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        plt.savefig(tmp.name, format="png", dpi=100)
        mlflow.log_artifact(tmp.name, artifact_path="shap")
    plt.close(fig)

    # Mean absolute SHAP per feature → metrics
    mean_shap = np.abs(shap_values).mean(axis=0)
    for feat, val in zip(X.columns, mean_shap):
        mlflow.log_metric(f"shap_{feat}", round(float(val), 6))


def explain_prediction(model, X_single: pd.DataFrame) -> list[dict]:
    """
    Return top-3 features driving a single prediction.

    Returns list of {"feature": str, "shap_value": float, "direction": str}
    sorted by absolute SHAP value descending.
    """
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_single)

    sv   = shap_values[0] if shap_values.ndim > 1 else shap_values
    cols = X_single.columns.tolist()

    ranked = sorted(zip(cols, sv), key=lambda x: abs(x[1]), reverse=True)[:3]
    return [
        {
            "feature":    feat,
            "shap_value": round(float(val), 4),
            "direction":  "increases_churn" if val > 0 else "decreases_churn",
        }
        for feat, val in ranked
    ]
