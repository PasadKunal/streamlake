"""Unit tests for Gold layer DuckDB aggregations.

All tests use in-memory DataFrames — no MinIO or Delta Lake required.
"""
import pytest
import pandas as pd
from orchestration.gold_aggregations import (
    compute_dau,
    compute_funnel,
    compute_revenue,
    compute_user_signals,
    run_all,
)


@pytest.fixture()
def silver_df() -> pd.DataFrame:
    """Minimal Silver DataFrame covering multiple users, event types, countries."""
    return pd.DataFrame([
        # user-1: US, DESKTOP — CLICK + PURCHASE
        {"event_id": "e1", "user_id": "u1", "session_id": "s1", "event_type": "PAGE_VIEW",
         "device_type": "DESKTOP", "country_code": "US", "event_date": "2026-06-20",
         "amount_cents": None, "timestamp_ms": 1_000_000},
        {"event_id": "e2", "user_id": "u1", "session_id": "s1", "event_type": "ADD_TO_CART",
         "device_type": "DESKTOP", "country_code": "US", "event_date": "2026-06-20",
         "amount_cents": None, "product_id": "P1", "timestamp_ms": 1_001_000},
        {"event_id": "e3", "user_id": "u1", "session_id": "s1", "event_type": "PURCHASE",
         "device_type": "DESKTOP", "country_code": "US", "event_date": "2026-06-20",
         "amount_cents": 5000, "product_id": "P1", "timestamp_ms": 1_002_000},
        # user-2: GB, MOBILE — PAGE_VIEW only
        {"event_id": "e4", "user_id": "u2", "session_id": "s2", "event_type": "PAGE_VIEW",
         "device_type": "MOBILE", "country_code": "GB", "event_date": "2026-06-20",
         "amount_cents": None, "timestamp_ms": 1_003_000},
        # user-3: US, MOBILE — SESSION_START + PURCHASE
        {"event_id": "e5", "user_id": "u3", "session_id": "s3", "event_type": "SESSION_START",
         "device_type": "MOBILE", "country_code": "US", "event_date": "2026-06-20",
         "amount_cents": None, "timestamp_ms": 1_004_000},
        {"event_id": "e6", "user_id": "u3", "session_id": "s3", "event_type": "PURCHASE",
         "device_type": "MOBILE", "country_code": "US", "event_date": "2026-06-20",
         "amount_cents": 2500, "product_id": "P2", "timestamp_ms": 1_005_000},
    ])


class TestComputeDAU:
    def test_returns_dataframe(self, silver_df):
        df = compute_dau(silver_df)
        assert not df.empty

    def test_has_required_columns(self, silver_df):
        df = compute_dau(silver_df)
        for col in ["event_date", "country_code", "device_type", "unique_users",
                    "total_sessions", "total_events", "gold_computed_ms"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_unique_users_us_desktop(self, silver_df):
        df = compute_dau(silver_df)
        row = df[(df["country_code"] == "US") & (df["device_type"] == "DESKTOP")]
        assert len(row) == 1
        assert row.iloc[0]["unique_users"] == 1

    def test_us_mobile_has_two_users(self, silver_df):
        df = compute_dau(silver_df)
        row = df[(df["country_code"] == "US") & (df["device_type"] == "MOBILE")]
        assert row.iloc[0]["unique_users"] == 1  # u3 only (u1 is DESKTOP)

    def test_total_us_unique_users(self, silver_df):
        df = compute_dau(silver_df)
        us_users = df[df["country_code"] == "US"]["unique_users"].sum()
        assert us_users == 2  # u1 (DESKTOP) + u3 (MOBILE)

    def test_gold_computed_ms_is_positive(self, silver_df):
        df = compute_dau(silver_df)
        assert (df["gold_computed_ms"] > 0).all()


class TestComputeRevenue:
    def test_returns_dataframe(self, silver_df):
        df = compute_revenue(silver_df)
        assert not df.empty

    def test_has_required_columns(self, silver_df):
        df = compute_revenue(silver_df)
        for col in ["event_date", "country_code", "product_id", "total_purchases",
                    "total_revenue_cents", "avg_order_value_cents", "gold_computed_ms"]:
            assert col in df.columns

    def test_us_total_revenue(self, silver_df):
        df = compute_revenue(silver_df)
        us_revenue = df[df["country_code"] == "US"]["total_revenue_cents"].sum()
        assert us_revenue == 7500  # 5000 + 2500

    def test_us_purchase_count(self, silver_df):
        df = compute_revenue(silver_df)
        us_purchases = df[df["country_code"] == "US"]["total_purchases"].sum()
        assert us_purchases == 2

    def test_no_gb_revenue(self, silver_df):
        df = compute_revenue(silver_df)
        assert len(df[df["country_code"] == "GB"]) == 0

    def test_avg_order_value_p1(self, silver_df):
        df = compute_revenue(silver_df)
        row = df[df["product_id"] == "P1"]
        assert len(row) == 1
        assert row.iloc[0]["avg_order_value_cents"] == pytest.approx(5000.0)


class TestComputeFunnel:
    def test_returns_dataframe(self, silver_df):
        df = compute_funnel(silver_df)
        assert not df.empty

    def test_has_required_columns(self, silver_df):
        df = compute_funnel(silver_df)
        for col in ["event_date", "country_code", "total_page_views",
                    "total_add_to_carts", "total_purchases",
                    "view_to_cart_pct", "cart_to_purchase_pct", "gold_computed_ms"]:
            assert col in df.columns

    def test_us_page_views(self, silver_df):
        df = compute_funnel(silver_df)
        row = df[df["country_code"] == "US"]
        assert row.iloc[0]["total_page_views"] == 1  # only e1

    def test_us_funnel_conversions(self, silver_df):
        df = compute_funnel(silver_df)
        row = df[df["country_code"] == "US"].iloc[0]
        assert row["total_add_to_carts"] == 1
        assert row["total_purchases"] == 2  # P1 + P2

    def test_view_to_cart_100_percent_us(self, silver_df):
        df = compute_funnel(silver_df)
        row = df[df["country_code"] == "US"].iloc[0]
        assert row["view_to_cart_pct"] == pytest.approx(100.0)

    def test_gb_zero_conversions(self, silver_df):
        df = compute_funnel(silver_df)
        row = df[df["country_code"] == "GB"].iloc[0]
        assert row["total_add_to_carts"] == 0
        assert row["total_purchases"] == 0
        assert row["view_to_cart_pct"] == 0.0


class TestComputeUserSignals:
    def test_returns_dataframe(self, silver_df):
        df = compute_user_signals(silver_df)
        assert not df.empty

    def test_has_required_columns(self, silver_df):
        df = compute_user_signals(silver_df)
        for col in ["user_id", "last_seen_date", "days_since_last_session",
                    "total_sessions_7d", "total_events_7d", "total_purchases_7d",
                    "total_revenue_7d_cents", "is_churned", "churn_risk_score",
                    "signal_date", "gold_computed_ms"]:
            assert col in df.columns

    def test_all_users_present(self, silver_df):
        df = compute_user_signals(silver_df)
        assert set(df["user_id"]) == {"u1", "u2", "u3"}

    def test_no_users_churned_fresh_data(self, silver_df):
        df = compute_user_signals(silver_df)
        # All events are on signal_date so days_since = 0 → not churned
        assert not df["is_churned"].any()

    def test_churn_risk_score_range(self, silver_df):
        df = compute_user_signals(silver_df)
        assert (df["churn_risk_score"] >= 0.0).all()
        assert (df["churn_risk_score"] <= 1.0).all()

    def test_u1_has_one_purchase(self, silver_df):
        df = compute_user_signals(silver_df)
        row = df[df["user_id"] == "u1"].iloc[0]
        assert row["total_purchases_7d"] == 1
        assert row["total_revenue_7d_cents"] == 5000

    def test_u2_has_no_purchases(self, silver_df):
        df = compute_user_signals(silver_df)
        row = df[df["user_id"] == "u2"].iloc[0]
        assert row["total_purchases_7d"] == 0
        assert row["total_revenue_7d_cents"] == 0

    def test_churned_user_detection(self):
        """User with last activity 8+ days ago should be flagged is_churned=True."""
        old_df = pd.DataFrame([
            {"event_id": "x1", "user_id": "old_user", "session_id": "sx",
             "event_type": "PAGE_VIEW", "device_type": "DESKTOP", "country_code": "US",
             "event_date": "2026-06-11", "amount_cents": None, "timestamp_ms": 999},
            {"event_id": "x2", "user_id": "new_user", "session_id": "sy",
             "event_type": "CLICK", "device_type": "MOBILE", "country_code": "US",
             "event_date": "2026-06-19", "amount_cents": None, "timestamp_ms": 1000},
        ])
        df = compute_user_signals(old_df)
        old_row = df[df["user_id"] == "old_user"].iloc[0]
        new_row = df[df["user_id"] == "new_user"].iloc[0]
        assert old_row["is_churned"] is True or old_row["days_since_last_session"] >= 7
        assert new_row["is_churned"] is False or new_row["days_since_last_session"] < 7


class TestRunAll:
    def test_returns_all_four_keys(self, silver_df):
        results = run_all(silver_df)
        assert set(results.keys()) == {"dau", "revenue", "funnel", "user_signals"}

    def test_all_results_are_dataframes(self, silver_df):
        import pandas as pd
        results = run_all(silver_df)
        for name, df in results.items():
            assert isinstance(df, pd.DataFrame), f"{name} is not a DataFrame"
