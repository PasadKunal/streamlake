"""
PSI (Population Stability Index) drift monitor.

Compares current feature distributions against the training baseline
saved by ml/train.py at `serving/training_baseline.json`.

PSI thresholds (industry standard):
  PSI < 0.10   → stable        (green  — no action)
  0.10–0.25    → moderate      (yellow — monitor closely)
  PSI > 0.25   → significant   (red    — trigger retraining)

Usage:
    from serving.drift_monitor import compute_drift_report
    report = compute_drift_report()
    print(report)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

BASELINE_PATH = Path("serving/training_baseline.json")
PARQUET_PATH  = Path("feature_store/data/user_features.parquet")

PSI_STABLE   = 0.10
PSI_RETRAIN  = 0.25


def compute_psi(
    baseline_counts: list[int],
    baseline_edges:  list[float],
    actual:          np.ndarray,
) -> float:
    """
    Compute PSI between a saved baseline histogram and a current distribution.

    PSI = Σ (actual_% − expected_%) × ln(actual_% / expected_%)
    """
    edges = np.array(baseline_edges)
    actual_counts, _ = np.histogram(actual, bins=edges)
    n_baseline = sum(baseline_counts)
    n_actual   = len(actual)

    eps = 1e-6
    exp_pcts = np.maximum(np.array(baseline_counts, dtype=float) / n_baseline, eps)
    act_pcts = np.maximum(actual_counts.astype(float)             / n_actual,   eps)

    return float(np.sum((act_pcts - exp_pcts) * np.log(act_pcts / exp_pcts)))


def psi_status(psi: float) -> str:
    if psi < PSI_STABLE:
        return "stable"
    if psi < PSI_RETRAIN:
        return "moderate"
    return "retrain"


def compute_drift_report(
    baseline_path: Path = BASELINE_PATH,
    current_path:  Path = PARQUET_PATH,
) -> dict:
    """
    Load the training baseline and current features, compute PSI per feature.

    Returns a report dict with per-feature PSI scores and an overall drift flag.
    """
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Training baseline not found at {baseline_path}. "
            "Run python -m ml.train to generate it."
        )
    if not current_path.exists():
        raise FileNotFoundError(
            f"Current features not found at {current_path}. "
            "Run python -m feature_store.feature_pipeline."
        )

    baseline = json.loads(baseline_path.read_text())
    current_df = pd.read_parquet(current_path)

    results: dict[str, dict] = {}
    any_retrain = False

    for feat, stats in baseline["features"].items():
        if feat not in current_df.columns:
            continue
        current_values = current_df[feat].dropna().values
        psi = compute_psi(stats["bin_counts"], stats["bin_edges"], current_values)
        status = psi_status(psi)
        if status == "retrain":
            any_retrain = True
        results[feat] = {
            "psi":            round(psi, 6),
            "status":         status,
            "baseline_mean":  stats["mean"],
            "current_mean":   round(float(current_values.mean()), 4),
            "baseline_p50":   stats["p50"],
            "current_p50":    round(float(np.median(current_values)), 4),
        }

    return {
        "baseline_computed_at": baseline.get("computed_at"),
        "baseline_n_samples":   baseline.get("n_samples"),
        "current_n_samples":    len(current_df),
        "drift_alert":          any_retrain,
        "features":             results,
    }


def push_psi_to_prometheus(report: dict) -> None:
    """Update Prometheus FEATURE_PSI and DRIFT_ALERT gauges from a drift report."""
    from serving.metrics import DRIFT_ALERT, FEATURE_PSI
    for feat, info in report["features"].items():
        FEATURE_PSI.labels(feature=feat).set(info["psi"])
    DRIFT_ALERT.set(1.0 if report["drift_alert"] else 0.0)
