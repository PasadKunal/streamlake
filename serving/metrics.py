"""Prometheus metrics for the StreamLake inference API."""
from prometheus_client import Counter, Gauge, Histogram

PREDICTIONS_TOTAL = Counter(
    "streamlake_predictions_total",
    "Total churn predictions served",
    ["model_version", "ab_group", "prediction"],
)

PREDICTION_LATENCY = Histogram(
    "streamlake_prediction_latency_seconds",
    "End-to-end latency: feature fetch + inference + SHAP",
    buckets=[0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.000],
)

CHURN_PROBABILITY = Histogram(
    "streamlake_churn_probability",
    "Distribution of predicted churn probability scores",
    buckets=[i / 10 for i in range(11)],
)

FEATURE_PSI = Gauge(
    "streamlake_feature_psi",
    "Population Stability Index per feature vs training baseline",
    ["feature"],
)

DRIFT_ALERT = Gauge(
    "streamlake_drift_alert",
    "1 if any feature PSI exceeds retrain threshold (0.25), else 0",
)
