"""
Redis sorted-set store for churn scores, namespaced by tenant.

Every /predict call writes to streamlake:churn_scores:{tenant_id}.
GET /alerts queries this set by score range — always O(log N), no full scan.
"""
from __future__ import annotations

import os

import redis as _redis_lib
from dotenv import load_dotenv

load_dotenv()

_client: _redis_lib.Redis | None = None


def _redis() -> _redis_lib.Redis:
    global _client
    if _client is None:
        conn_str = os.getenv("REDIS_CONNECTION_STRING", "localhost:6379")
        parts = conn_str.split(",")
        host, port_str = parts[0].rsplit(":", 1)
        password: str | None = None
        for p in parts[1:]:
            if p.lower().startswith("password="):
                password = p.split("=", 1)[1]
        _client = _redis_lib.Redis(
            host=host, port=int(port_str), password=password, decode_responses=True
        )
    return _client


def _scores_key(tenant: str) -> str:
    return f"streamlake:churn_scores:{tenant}"


def record_score(user_id: str, score: float, tenant: str = "default") -> None:
    """Write churn probability to the tenant sorted set. Non-critical — never raises."""
    try:
        _redis().zadd(_scores_key(tenant), {user_id: score})
    except Exception:
        pass


def get_alerts(threshold: float = 0.7, limit: int = 100, tenant: str = "default") -> list[dict]:
    """Return up to `limit` users with score >= threshold for this tenant, sorted desc."""
    results = _redis().zrangebyscore(
        _scores_key(tenant), threshold, "+inf", withscores=True
    )
    return [
        {"user_id": uid, "churn_probability": round(float(score), 4)}
        for uid, score in sorted(results, key=lambda x: x[1], reverse=True)[:limit]
    ]


def total_scored(tenant: str = "default") -> int:
    try:
        return _redis().zcard(_scores_key(tenant))
    except Exception:
        return 0
