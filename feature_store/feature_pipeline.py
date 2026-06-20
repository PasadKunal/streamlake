"""
Feature pipeline: Silver Delta → computed features → Feast online (Redis) + offline (Parquet).

Steps:
  1. Read Silver Delta from MinIO
  2. Compute 9 rolling-window features per user via DuckDB
  3. Save features to Parquet  (Feast FileOfflineStore)
  4. Save features to Delta    (MinIO — long-term storage, audit trail)
  5. Apply Feast registry      (registers entity + feature view in registry.db)
  6. Write features to Redis   (Feast online store, < 10ms serving)

Usage:
    source .venv/bin/activate
    python -m feature_store.feature_pipeline
    python -m feature_store.feature_pipeline --once  (same, explicit)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
from deltalake import DeltaTable
from feast import FeatureStore
from loguru import logger

from storage.delta_writer import STORAGE_OPTIONS, write_batch

SILVER_PATH   = os.getenv("DELTA_SILVER_PATH",    "s3://streamlake-silver/events")
FEATURES_PATH = os.getenv("DELTA_FEATURES_PATH",  "s3://streamlake-features/user_activity")
REPO_DIR      = Path(__file__).parent
PARQUET_PATH  = REPO_DIR / "data" / "user_features.parquet"

FEATURE_DELTA_SCHEMA = pa.schema([
    pa.field("user_id",                 pa.string(),                   nullable=False),
    pa.field("event_timestamp",         pa.timestamp("ms", tz="UTC"),  nullable=False),
    pa.field("purchase_count_1h",       pa.int64(),                    nullable=False),
    pa.field("purchase_count_24h",      pa.int64(),                    nullable=False),
    pa.field("purchase_count_7d",       pa.int64(),                    nullable=False),
    pa.field("revenue_sum_1h",          pa.int64(),                    nullable=False),
    pa.field("revenue_sum_24h",         pa.int64(),                    nullable=False),
    pa.field("revenue_sum_7d",          pa.int64(),                    nullable=False),
    pa.field("session_count_24h",       pa.int64(),                    nullable=False),
    pa.field("event_count_24h",         pa.int64(),                    nullable=False),
    pa.field("days_since_last_purchase",pa.int64(),                    nullable=False),
])


def compute_features(silver_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 9 rolling-window features per user from a Silver DataFrame.

    Pure function (no I/O) — accepts a Silver pandas DataFrame,
    returns a features DataFrame ready for Feast and Delta.

    Windows:
      1h  = last 3,600,000 ms from max observed event timestamp
      24h = last 86,400,000 ms
      7d  = last 604,800,000 ms
    """
    ref_ts = int(silver_df["timestamp_ms"].max())

    con = duckdb.connect()
    con.register("silver", silver_df)

    df = con.execute("""
        WITH ref AS (SELECT ? AS ref_ts)
        SELECT
            s.user_id,

            -- Purchase counts
            COUNT(*) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 3_600_000
            )::BIGINT                                                          AS purchase_count_1h,

            COUNT(*) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 86_400_000
            )::BIGINT                                                          AS purchase_count_24h,

            COUNT(*) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 604_800_000
            )::BIGINT                                                          AS purchase_count_7d,

            -- Revenue sums (NULL-safe)
            COALESCE(SUM(s.amount_cents) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 3_600_000
            ), 0)::BIGINT                                                      AS revenue_sum_1h,

            COALESCE(SUM(s.amount_cents) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 86_400_000
            ), 0)::BIGINT                                                      AS revenue_sum_24h,

            COALESCE(SUM(s.amount_cents) FILTER (
                WHERE s.event_type = 'PURCHASE'
                  AND s.timestamp_ms >= (SELECT ref_ts FROM ref) - 604_800_000
            ), 0)::BIGINT                                                      AS revenue_sum_7d,

            -- Session engagement
            COUNT(DISTINCT s.session_id) FILTER (
                WHERE s.timestamp_ms >= (SELECT ref_ts FROM ref) - 86_400_000
            )::BIGINT                                                          AS session_count_24h,

            COUNT(*) FILTER (
                WHERE s.timestamp_ms >= (SELECT ref_ts FROM ref) - 86_400_000
            )::BIGINT                                                          AS event_count_24h,

            -- Recency: days since last purchase (999 = never purchased)
            CASE
                WHEN MAX(s.timestamp_ms) FILTER (WHERE s.event_type = 'PURCHASE') IS NULL
                THEN 999
                ELSE CAST(
                    ((SELECT ref_ts FROM ref)
                     - MAX(s.timestamp_ms) FILTER (WHERE s.event_type = 'PURCHASE'))
                    / 86_400_000 AS BIGINT)
            END                                                                AS days_since_last_purchase

        FROM silver s
        GROUP BY s.user_id
    """, [ref_ts]).df()

    # Feast requires a UTC datetime column named event_timestamp
    ref_dt = datetime.fromtimestamp(ref_ts / 1000, tz=timezone.utc)
    df["event_timestamp"] = ref_dt
    return df


def run() -> None:
    logger.info("Loading Silver Delta...")
    try:
        dt = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS)
        silver_df = dt.to_pandas()
    except Exception as e:
        logger.error(f"Cannot read Silver: {e}")
        return

    logger.info(f"Silver loaded | version={dt.version()} records={len(silver_df):,}")

    logger.info("Computing user features via DuckDB...")
    features_df = compute_features(silver_df)
    logger.info(f"Features computed | users={len(features_df):,}")

    # Write Parquet for Feast FileOfflineStore
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(PARQUET_PATH, index=False)
    logger.info(f"Offline parquet written → {PARQUET_PATH}")

    # Write Delta to MinIO for long-term storage
    delta_records = features_df.copy()
    delta_records["event_timestamp"] = delta_records["event_timestamp"].astype("int64") // 1_000_000
    write_batch(delta_records.to_dict(orient="records"), FEATURES_PATH, FEATURE_DELTA_SCHEMA, [])
    logger.info(f"Feature Delta written → {FEATURES_PATH}")

    # Apply Feast registry (idempotent)
    logger.info("Applying Feast registry...")
    from feature_store.feature_repo import user, user_activity_features
    store = FeatureStore(repo_path=str(REPO_DIR))
    store.apply([user, user_activity_features])
    logger.info("Feast registry applied")

    # Materialize to Redis online store
    logger.info("Writing features to Redis online store...")
    online_df = features_df.copy()
    store.write_to_online_store(
        feature_view_name="user_activity_features",
        df=online_df,
        allow_registry_cache=True,
    )
    logger.info(f"Redis online store populated | users={len(features_df):,}")

    logger.info("Phase 4 feature pipeline complete")


if __name__ == "__main__":
    run()
