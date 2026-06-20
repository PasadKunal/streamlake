"""Unit tests for the ML feature pipeline.

All tests use in-memory DataFrames — no MinIO, Redis, or Feast required.
"""
import pytest
import pandas as pd
from datetime import datetime, timezone

from feature_store.feature_pipeline import compute_features


@pytest.fixture()
def silver_df() -> pd.DataFrame:
    """Silver DataFrame with controlled purchase/session distribution."""
    base_ts = int(datetime(2026, 6, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    one_hour   = 3_600_000
    one_day    = 86_400_000

    return pd.DataFrame([
        # user-1: 2 purchases — one within 1h, one within 24h (not 1h), multiple sessions
        {"user_id": "u1", "session_id": "s1", "event_type": "SESSION_START",
         "timestamp_ms": base_ts - 30 * 60_000, "amount_cents": None},
        {"user_id": "u1", "session_id": "s1", "event_type": "PURCHASE",
         "timestamp_ms": base_ts - 20 * 60_000, "amount_cents": 5000},  # within 1h
        {"user_id": "u1", "session_id": "s2", "event_type": "PURCHASE",
         "timestamp_ms": base_ts - 2 * one_hour, "amount_cents": 3000},  # within 24h, not 1h
        {"user_id": "u1", "session_id": "s2", "event_type": "CLICK",
         "timestamp_ms": base_ts - 1 * one_hour, "amount_cents": None},

        # user-2: no purchases, only session activity
        {"user_id": "u2", "session_id": "s3", "event_type": "SESSION_START",
         "timestamp_ms": base_ts - 10 * 60_000, "amount_cents": None},
        {"user_id": "u2", "session_id": "s3", "event_type": "CLICK",
         "timestamp_ms": base_ts - 5 * 60_000, "amount_cents": None},

        # user-3: purchase older than 24h but within 7d
        {"user_id": "u3", "session_id": "s4", "event_type": "PURCHASE",
         "timestamp_ms": base_ts - 2 * one_day, "amount_cents": 1500},
        {"user_id": "u3", "session_id": "s4", "event_type": "CLICK",
         "timestamp_ms": base_ts - 1 * one_hour, "amount_cents": None},
    ])


class TestComputeFeatures:
    def test_returns_one_row_per_user(self, silver_df):
        df = compute_features(silver_df)
        assert len(df) == 3
        assert set(df["user_id"]) == {"u1", "u2", "u3"}

    def test_has_all_feature_columns(self, silver_df):
        df = compute_features(silver_df)
        expected = [
            "user_id", "purchase_count_1h", "purchase_count_24h", "purchase_count_7d",
            "revenue_sum_1h", "revenue_sum_24h", "revenue_sum_7d",
            "session_count_24h", "event_count_24h",
            "days_since_last_purchase", "event_timestamp",
        ]
        for col in expected:
            assert col in df.columns, f"Missing column: {col}"

    def test_has_event_timestamp_column(self, silver_df):
        df = compute_features(silver_df)
        assert "event_timestamp" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["event_timestamp"])

    def test_u1_purchase_count_1h(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["purchase_count_1h"] == 1   # only the 20-min-ago purchase

    def test_u1_purchase_count_24h(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["purchase_count_24h"] == 2  # both purchases within 24h

    def test_u1_purchase_count_7d(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["purchase_count_7d"] == 2

    def test_u1_revenue_sum_1h(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["revenue_sum_1h"] == 5000   # only the recent purchase

    def test_u1_revenue_sum_24h(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["revenue_sum_24h"] == 8000  # 5000 + 3000

    def test_u2_no_purchases(self, silver_df):
        df = compute_features(silver_df)
        u2 = df[df["user_id"] == "u2"].iloc[0]
        assert u2["purchase_count_1h"] == 0
        assert u2["purchase_count_24h"] == 0
        assert u2["revenue_sum_7d"] == 0

    def test_u2_days_since_last_purchase_is_999(self, silver_df):
        df = compute_features(silver_df)
        u2 = df[df["user_id"] == "u2"].iloc[0]
        assert u2["days_since_last_purchase"] == 999  # never purchased

    def test_u3_purchase_outside_24h_window(self, silver_df):
        df = compute_features(silver_df)
        u3 = df[df["user_id"] == "u3"].iloc[0]
        assert u3["purchase_count_24h"] == 0   # purchase was 2 days ago
        assert u3["purchase_count_7d"] == 1    # but within 7 days

    def test_u3_days_since_last_purchase(self, silver_df):
        df = compute_features(silver_df)
        u3 = df[df["user_id"] == "u3"].iloc[0]
        assert u3["days_since_last_purchase"] == 2  # purchase was 2 days ago

    def test_u1_session_count_24h(self, silver_df):
        df = compute_features(silver_df)
        u1 = df[df["user_id"] == "u1"].iloc[0]
        assert u1["session_count_24h"] == 2   # s1 and s2

    def test_u2_event_count_24h(self, silver_df):
        df = compute_features(silver_df)
        u2 = df[df["user_id"] == "u2"].iloc[0]
        assert u2["event_count_24h"] == 2     # SESSION_START + CLICK

    def test_no_null_values(self, silver_df):
        df = compute_features(silver_df)
        feature_cols = [
            "purchase_count_1h", "purchase_count_24h", "purchase_count_7d",
            "revenue_sum_1h", "revenue_sum_24h", "revenue_sum_7d",
            "session_count_24h", "event_count_24h", "days_since_last_purchase",
        ]
        for col in feature_cols:
            assert df[col].isna().sum() == 0, f"Nulls found in {col}"

    def test_all_counts_non_negative(self, silver_df):
        df = compute_features(silver_df)
        for col in ["purchase_count_1h", "purchase_count_24h", "purchase_count_7d",
                    "session_count_24h", "event_count_24h"]:
            assert (df[col] >= 0).all(), f"Negative values in {col}"

    def test_revenue_sums_non_negative(self, silver_df):
        df = compute_features(silver_df)
        for col in ["revenue_sum_1h", "revenue_sum_24h", "revenue_sum_7d"]:
            assert (df[col] >= 0).all()

    def test_1h_count_lte_24h_count(self, silver_df):
        df = compute_features(silver_df)
        assert (df["purchase_count_1h"] <= df["purchase_count_24h"]).all()

    def test_24h_count_lte_7d_count(self, silver_df):
        df = compute_features(silver_df)
        assert (df["purchase_count_24h"] <= df["purchase_count_7d"]).all()
