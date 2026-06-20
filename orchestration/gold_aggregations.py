"""
Gold layer aggregations — DuckDB SQL over Silver pandas DataFrames.

Each function is pure (no I/O): accepts a Silver DataFrame, returns a Gold DataFrame.
I/O (reading Silver, writing Gold) lives in run_gold_pipeline.py and the Airflow DAG.

Four aggregations:
  dau          — Daily Active Users by date / country / device
  revenue      — Daily purchase revenue by date / country / product
  funnel       — PAGE_VIEW → ADD_TO_CART → PURCHASE conversion rates
  user_signals — Per-user churn risk signals using trailing 7-day activity window
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def compute_dau(silver_df: pd.DataFrame) -> pd.DataFrame:
    """Daily Active Users grouped by (event_date, country_code, device_type)."""
    con = duckdb.connect()
    con.register("silver", silver_df)
    df = con.execute("""
        SELECT
            event_date,
            country_code,
            device_type,
            COUNT(DISTINCT user_id)    AS unique_users,
            COUNT(DISTINCT session_id) AS total_sessions,
            COUNT(*)                   AS total_events
        FROM silver
        GROUP BY event_date, country_code, device_type
        ORDER BY event_date, unique_users DESC
    """).df()
    df["gold_computed_ms"] = _now_ms()
    return df


def compute_revenue(silver_df: pd.DataFrame) -> pd.DataFrame:
    """Daily purchase revenue grouped by (event_date, country_code, product_id)."""
    con = duckdb.connect()
    con.register("silver", silver_df)
    df = con.execute("""
        SELECT
            event_date,
            country_code,
            COALESCE(product_id, 'N/A')      AS product_id,
            COUNT(*)                         AS total_purchases,
            COALESCE(SUM(amount_cents), 0)   AS total_revenue_cents,
            COALESCE(AVG(amount_cents), 0.0) AS avg_order_value_cents
        FROM silver
        WHERE event_type = 'PURCHASE'
          AND amount_cents IS NOT NULL
          AND amount_cents > 0
        GROUP BY event_date, country_code, product_id
        ORDER BY event_date, total_revenue_cents DESC
    """).df()
    df["gold_computed_ms"] = _now_ms()
    return df


def compute_funnel(silver_df: pd.DataFrame) -> pd.DataFrame:
    """Conversion funnel: PAGE_VIEW → ADD_TO_CART → PURCHASE per (date, country)."""
    con = duckdb.connect()
    con.register("silver", silver_df)
    df = con.execute("""
        SELECT
            event_date,
            country_code,
            COUNT(*) FILTER (WHERE event_type = 'PAGE_VIEW')    AS total_page_views,
            COUNT(*) FILTER (WHERE event_type = 'ADD_TO_CART')  AS total_add_to_carts,
            COUNT(*) FILTER (WHERE event_type = 'PURCHASE')     AS total_purchases,
            CASE
                WHEN COUNT(*) FILTER (WHERE event_type = 'PAGE_VIEW') = 0 THEN 0.0
                ELSE ROUND(
                    100.0
                    * COUNT(*) FILTER (WHERE event_type = 'ADD_TO_CART')
                    / COUNT(*) FILTER (WHERE event_type = 'PAGE_VIEW'), 2)
            END AS view_to_cart_pct,
            CASE
                WHEN COUNT(*) FILTER (WHERE event_type = 'ADD_TO_CART') = 0 THEN 0.0
                ELSE ROUND(
                    100.0
                    * COUNT(*) FILTER (WHERE event_type = 'PURCHASE')
                    / COUNT(*) FILTER (WHERE event_type = 'ADD_TO_CART'), 2)
            END AS cart_to_purchase_pct
        FROM silver
        GROUP BY event_date, country_code
        ORDER BY event_date, total_page_views DESC
    """).df()
    df["gold_computed_ms"] = _now_ms()
    return df


def compute_user_signals(silver_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-user churn signals using trailing 7-day activity window.

    Columns:
      - last_seen_date          — most recent event_date for the user
      - days_since_last_session — calendar days since last_seen_date vs signal_date
      - total_sessions_7d       — distinct sessions in trailing 7 days
      - total_events_7d         — event count in trailing 7 days
      - total_purchases_7d      — purchase count in trailing 7 days
      - total_revenue_7d_cents  — revenue sum in trailing 7 days
      - is_churned              — True if days_since_last_session >= 7
      - churn_risk_score        — 0.0 (active today) → 1.0 (churned ≥ 7 days ago)
      - signal_date             — the reference date used for this computation
    """
    signal_date = silver_df["event_date"].max()
    cutoff_date = (
        datetime.strptime(signal_date, "%Y-%m-%d") - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    con = duckdb.connect()
    con.register("silver", silver_df)

    df = con.execute("""
        WITH last_seen AS (
            SELECT user_id, MAX(event_date) AS last_seen_date
            FROM silver
            GROUP BY user_id
        ),
        weekly AS (
            SELECT
                user_id,
                COUNT(DISTINCT session_id)                                  AS total_sessions_7d,
                COUNT(*)                                                     AS total_events_7d,
                COUNT(*) FILTER (WHERE event_type = 'PURCHASE')             AS total_purchases_7d,
                COALESCE(
                    SUM(amount_cents) FILTER (WHERE event_type = 'PURCHASE'), 0
                )                                                            AS total_revenue_7d_cents
            FROM silver
            WHERE event_date >= ?
            GROUP BY user_id
        )
        SELECT
            ls.user_id,
            ls.last_seen_date,
            DATEDIFF('day',
                CAST(ls.last_seen_date AS DATE),
                CAST(? AS DATE))                                            AS days_since_last_session,
            COALESCE(w.total_sessions_7d,     0)                           AS total_sessions_7d,
            COALESCE(w.total_events_7d,       0)                           AS total_events_7d,
            COALESCE(w.total_purchases_7d,    0)                           AS total_purchases_7d,
            COALESCE(w.total_revenue_7d_cents,0)                           AS total_revenue_7d_cents,
            DATEDIFF('day',
                CAST(ls.last_seen_date AS DATE),
                CAST(? AS DATE)) >= 7                                       AS is_churned,
            LEAST(
                CAST(DATEDIFF('day',
                    CAST(ls.last_seen_date AS DATE),
                    CAST(? AS DATE)) AS DOUBLE) / 7.0,
                1.0
            )                                                               AS churn_risk_score,
            ?                                                               AS signal_date
        FROM last_seen ls
        LEFT JOIN weekly w USING (user_id)
        ORDER BY churn_risk_score DESC, total_events_7d DESC
    """, [cutoff_date, signal_date, signal_date, signal_date, signal_date]).df()

    df["gold_computed_ms"] = _now_ms()
    return df


def run_all(silver_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Run all four Gold aggregations and return a named dict of DataFrames."""
    return {
        "dau":          compute_dau(silver_df),
        "revenue":      compute_revenue(silver_df),
        "funnel":       compute_funnel(silver_df),
        "user_signals": compute_user_signals(silver_df),
    }
