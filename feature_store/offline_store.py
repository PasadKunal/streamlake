"""
Offline feature retrieval with point-in-time correct joins.

The key FAANG concept demonstrated here:
  - WRONG: JOIN users ON user_id → leaks future feature values into training
  - RIGHT: JOIN users ON (user_id, timestamp) → only features known AT THAT MOMENT

Feast's get_historical_features() handles the point-in-time logic automatically.
Each row in entity_df gets the feature values that were valid at its event_timestamp,
preventing data leakage from future purchases/sessions bleeding into earlier training rows.

Usage:
    from feature_store.offline_store import build_training_dataset, sample_entity_df
    from deltalake import DeltaTable

    silver_df = DeltaTable(...).to_pandas()
    entity_df = sample_entity_df(silver_df, n_samples=1000)
    training_df = build_training_dataset(entity_df)
    # training_df has event_timestamp, user_id, label, + 9 features (no future leakage)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from feast import FeatureStore
from loguru import logger

REPO_DIR = Path(__file__).parent

FEATURE_REFS = [
    "user_activity_features:purchase_count_1h",
    "user_activity_features:purchase_count_24h",
    "user_activity_features:purchase_count_7d",
    "user_activity_features:revenue_sum_1h",
    "user_activity_features:revenue_sum_24h",
    "user_activity_features:revenue_sum_7d",
    "user_activity_features:session_count_24h",
    "user_activity_features:event_count_24h",
    "user_activity_features:days_since_last_purchase",
]


def sample_entity_df(silver_df: pd.DataFrame, n_samples: int = 2000) -> pd.DataFrame:
    """
    Build a labeled entity DataFrame from Silver events for training.

    Label: churned_7d = 1 if the user had no events in the 7 days AFTER this event.
    This creates a binary churn classification target.

    The event_timestamp is the point at which features must be "frozen" —
    Feast will only return feature values known at or before this timestamp.
    """
    from datetime import timezone

    silver_df = silver_df.copy()
    silver_df["event_dt"] = pd.to_datetime(silver_df["timestamp_ms"], unit="ms", utc=True)

    max_ts = silver_df["event_dt"].max()
    cutoff  = max_ts - pd.Timedelta(days=7)

    # Sample events from at least 7 days before the end of the dataset
    # (so we have a full 7-day window to observe post-event activity for labeling)
    eligible = silver_df[silver_df["event_dt"] <= cutoff]
    if eligible.empty:
        # Not enough history — use all events with a synthetic label
        logger.warning("Less than 7 days of data; using synthetic churn labels")
        eligible = silver_df.copy()

    sampled = eligible.sample(n=min(n_samples, len(eligible)), random_state=42)

    # For each sampled event, label churned = 1 if user had no activity in next 7 days
    post_activity = (
        silver_df.groupby("user_id")["event_dt"]
        .max()
        .rename("last_seen")
        .reset_index()
    )
    sampled = sampled.merge(post_activity, on="user_id", how="left")
    sampled["churned_7d"] = (
        (sampled["last_seen"] - sampled["event_dt"]) < pd.Timedelta(days=7)
    ).astype(int)

    return sampled[["user_id", "event_dt", "churned_7d"]].rename(
        columns={"event_dt": "event_timestamp"}
    )


def build_training_dataset(entity_df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform a point-in-time correct feature join via Feast.

    entity_df must have columns: user_id (str), event_timestamp (datetime, UTC)
    Returns: entity_df columns + 9 feature columns (no future data leakage)
    """
    store = FeatureStore(repo_path=str(REPO_DIR))
    logger.info(f"Running point-in-time feature join for {len(entity_df):,} training examples...")

    training_df = store.get_historical_features(
        entity_df=entity_df,
        features=FEATURE_REFS,
    ).to_df()

    logger.info(
        f"Training dataset ready | "
        f"rows={len(training_df):,} "
        f"features={len(FEATURE_REFS)} "
        f"null_rate={training_df[FEATURE_REFS[0].split(':')[1]].isna().mean():.1%}"
    )
    return training_df


def get_online_features(user_ids: list[str]) -> pd.DataFrame:
    """
    Retrieve real-time features for a list of users from Redis (< 10ms p99).
    Used by the FastAPI inference endpoint in Phase 5.
    """
    store = FeatureStore(repo_path=str(REPO_DIR))
    result = store.get_online_features(
        features=FEATURE_REFS,
        entity_rows=[{"user_id": uid} for uid in user_ids],
    ).to_df()
    return result
