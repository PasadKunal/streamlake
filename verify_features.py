"""
Verification script for the ML Feature Store (Phase 4).
Checks Redis online store, offline Parquet, and Delta table.

Usage:
    source .venv/bin/activate
    python verify_features.py
"""
import os
from pathlib import Path

print("=" * 55)
print("  StreamLake — Feature Store Verification")
print("=" * 55)

REPO_DIR = Path("feature_store")

# ── 1. Offline Parquet ────────────────────────────────────
print("\n── Offline Parquet ───────────────────────────────────")
parquet_path = REPO_DIR / "data" / "user_features.parquet"
try:
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    print(f"  Users              : {len(df):,}")
    print(f"  Features           : {[c for c in df.columns if c not in ('user_id', 'event_timestamp')]}")
    print(f"  Purchasers (count_24h > 0): {(df['purchase_count_24h'] > 0).sum():,}")
    print(f"  Avg revenue 7d     : {df['revenue_sum_7d'].mean():.0f} cents")
    print(f"  Max revenue 7d     : {df['revenue_sum_7d'].max():,} cents")
    print(f"\n  Sample (5 rows):")
    cols = ["user_id", "purchase_count_24h", "revenue_sum_7d", "session_count_24h",
            "event_count_24h", "days_since_last_purchase"]
    print(df[cols].head(5).to_string(index=False))
except Exception as e:
    print(f"  NOT FOUND: {e}")
    print("  Run: python -m feature_store.feature_pipeline")

# ── 2. Redis Online Store ─────────────────────────────────
print("\n── Redis Online Store ─────────────────────────────────")
try:
    from feast import FeatureStore
    store = FeatureStore(repo_path=str(REPO_DIR))

    # Spot-check first 3 users from parquet
    df = pd.read_parquet(parquet_path)
    sample_users = df["user_id"].head(3).tolist()

    result = store.get_online_features(
        features=[
            "user_activity_features:purchase_count_24h",
            "user_activity_features:revenue_sum_7d",
            "user_activity_features:days_since_last_purchase",
            "user_activity_features:event_count_24h",
        ],
        entity_rows=[{"user_id": uid} for uid in sample_users],
    ).to_df()

    print(f"  Redis keys checked : {len(sample_users)}")
    print(f"  Null feature values: {result.isna().sum().sum()}")
    print(f"\n  Online feature sample:")
    print(result.to_string(index=False))

except Exception as e:
    print(f"  ERROR: {e}")
    print("  Make sure Redis is running: docker compose up -d")

# ── 3. Feature Delta on MinIO ─────────────────────────────
print("\n── Feature Delta (MinIO) ──────────────────────────────")
try:
    from deltalake import DeltaTable
    STORAGE_OPTIONS = {
        "AWS_ENDPOINT_URL":          os.getenv("AWS_ENDPOINT_URL",      "http://localhost:9002"),
        "AWS_ACCESS_KEY_ID":         os.getenv("AWS_ACCESS_KEY_ID",     "minioadmin"),
        "AWS_SECRET_ACCESS_KEY":     os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        "AWS_REGION":                "us-east-1",
        "AWS_ALLOW_HTTP":            "true",
        "AWS_S3_ALLOW_UNSAFE_RENAME":"true",
    }
    dt = DeltaTable("s3://streamlake-features/user_activity", storage_options=STORAGE_OPTIONS)
    fdf = dt.to_pandas()
    print(f"  Delta version : {dt.version()}")
    print(f"  Rows          : {len(fdf):,}")
    print(f"  Columns       : {list(fdf.columns)}")
except Exception as e:
    print(f"  ERROR: {e}")

print("\n✓ Feature store verification complete\n")
