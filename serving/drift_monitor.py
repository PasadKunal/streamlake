"""
PSI (Population Stability Index) drift monitor.

Compares current feature distributions — computed live from the S3 Silver
Delta table — against the training baseline saved by ml/train.py at
`serving/training_baseline.json`.

No local files are required beyond the baseline JSON, which is committed
to the repository and present in every deployment.

PSI thresholds (industry standard):
  PSI < 0.10   -> stable        (green  -- no action)
  0.10-0.25    -> moderate      (yellow -- monitor closely)
  PSI > 0.25   -> significant   (red    -- trigger retraining)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

BASELINE_PATH = Path("serving/training_baseline.json")
SILVER_PATH   = os.getenv("DELTA_SILVER_PATH", "s3://streamlake-silver/events")

PSI_STABLE  = 0.10
PSI_RETRAIN = 0.25


def _s3_options() -> dict[str, str]:
    """Build S3 storage options from environment variables."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    opts: dict[str, str] = {
        "AWS_ACCESS_KEY_ID":          os.getenv("AWS_ACCESS_KEY_ID", ""),
        "AWS_SECRET_ACCESS_KEY":      os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "AWS_REGION":                 os.getenv("AWS_DEFAULT_REGION", "us-east-2"),
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }
    endpoint = os.getenv("AWS_ENDPOINT_URL", "")
    if endpoint:
        opts["AWS_ENDPOINT_URL"] = endpoint
        if endpoint.startswith("http://"):
            opts["AWS_ALLOW_HTTP"] = "true"
    return {k: v for k, v in opts.items() if v}


def _compute_features(silver_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 9 rolling-window features per user from Silver events.

    Pure pandas — no DuckDB, Feast, or loguru required. Replicates the
    logic in feature_store/feature_pipeline.py so the current distribution
    is always derived from the same feature definitions as the baseline.

    Windows are relative to the latest event timestamp in the dataset.
    """
    ref_ts = int(silver_df["timestamp_ms"].max())
    purchases = silver_df[silver_df["event_type"] == "PURCHASE"]

    users = pd.DataFrame({"user_id": silver_df["user_id"].unique()}).set_index("user_id")

    def _count(df: pd.DataFrame, window_ms: int) -> pd.Series:
        return df[df["timestamp_ms"] >= ref_ts - window_ms].groupby("user_id").size()

    def _revenue(df: pd.DataFrame, window_ms: int) -> pd.Series:
        return (
            df[df["timestamp_ms"] >= ref_ts - window_ms]
            .groupby("user_id")["amount_cents"]
            .sum()
        )

    recent = silver_df[silver_df["timestamp_ms"] >= ref_ts - 86_400_000]

    for series, name in [
        (_count(purchases,   3_600_000),  "purchase_count_1h"),
        (_count(purchases,  86_400_000),  "purchase_count_24h"),
        (_count(purchases, 604_800_000),  "purchase_count_7d"),
        (_revenue(purchases,   3_600_000),  "revenue_sum_1h"),
        (_revenue(purchases,  86_400_000),  "revenue_sum_24h"),
        (_revenue(purchases, 604_800_000),  "revenue_sum_7d"),
        (recent.groupby("user_id")["session_id"].nunique(), "session_count_24h"),
        (recent.groupby("user_id").size(),                  "event_count_24h"),
    ]:
        users = users.join(series.rename(name), how="left")

    users = users.fillna(0)

    # days_since_last_purchase: users who never purchased get 999
    last_pur = purchases.groupby("user_id")["timestamp_ms"].max()
    days = ((ref_ts - last_pur) / 86_400_000).astype(int).rename("days_since_last_purchase")
    users = users.join(days, how="left")
    users["days_since_last_purchase"] = users["days_since_last_purchase"].fillna(999).astype(int)

    return users.reset_index()


def compute_psi(
    baseline_counts: list[int],
    baseline_edges:  list[float],
    actual:          np.ndarray,
) -> float:
    """
    PSI = sum((actual_pct - expected_pct) * ln(actual_pct / expected_pct))
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


def compute_drift_report(baseline_path: Path = BASELINE_PATH) -> dict:
    """
    Compute PSI for all features against the training baseline.

    Baseline: serving/training_baseline.json (committed to repo, always present).
    Current:  S3 Silver Delta table, read live and features recomputed on the fly.
    """
    if not baseline_path.exists():
        raise FileNotFoundError(
            f"Training baseline not found at {baseline_path}. "
            "Run python -m ml.train to generate it."
        )

    baseline = json.loads(baseline_path.read_text())

    from deltalake import DeltaTable
    silver_path = os.getenv("DELTA_SILVER_PATH", SILVER_PATH)
    dt = DeltaTable(silver_path, storage_options=_s3_options())
    silver_df = dt.to_pandas()
    current_df = _compute_features(silver_df)

    results: dict[str, dict] = {}
    any_retrain = False

    for feat, stats in baseline["features"].items():
        if feat not in current_df.columns:
            continue
        current_values = current_df[feat].dropna().values
        psi    = compute_psi(stats["bin_counts"], stats["bin_edges"], current_values)
        status = psi_status(psi)
        if status == "retrain":
            any_retrain = True
        results[feat] = {
            "psi":           round(psi, 6),
            "status":        status,
            "baseline_mean": stats["mean"],
            "current_mean":  round(float(current_values.mean()), 4),
            "baseline_p50":  stats["p50"],
            "current_p50":   round(float(np.median(current_values)), 4),
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
