"""
Fire-and-forget outbound webhook sender.

Runs in a daemon thread so it never blocks /predict.
Logs success/failure but never raises — the caller doesn't care about delivery.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

import requests
from loguru import logger


def fire_webhook(url: str, payload: dict, timeout: float = 5.0) -> None:
    """POST payload to url in a background daemon thread."""

    def _send() -> None:
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            logger.info(f"Outbound webhook delivered | url={url} status={resp.status_code}")
        except Exception as exc:
            logger.warning(f"Outbound webhook failed | url={url} error={exc}")

    threading.Thread(target=_send, daemon=True).start()


def build_alert_payload(
    user_id: str,
    churn_probability: float,
    churn_prediction: bool,
    model_version: str,
    ab_group: str,
    top_features: list[dict],
) -> dict:
    return {
        "event":              "churn_alert",
        "user_id":            user_id,
        "churn_probability":  churn_probability,
        "churn_prediction":   churn_prediction,
        "model_version":      model_version,
        "ab_group":           ab_group,
        "top_features":       top_features,
        "timestamp":          datetime.now(timezone.utc).isoformat(),
    }
