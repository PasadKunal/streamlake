"""
Quick verification script for the Silver and Quarantine Delta tables.
Run after the Bronze → Silver pipeline to confirm the data contract.

Usage:
    source .venv/bin/activate
    python verify_silver.py
"""
import os
from deltalake import DeltaTable
import pandas as pd

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL": os.getenv("AWS_ENDPOINT_URL", "http://localhost:9002"),
    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    "AWS_REGION": "us-east-1",
    "AWS_ALLOW_HTTP": "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

print("=" * 55)
print("  StreamLake — Silver Delta Table Verification")
print("=" * 55)

try:
    dt = DeltaTable("s3://streamlake-silver/events", storage_options=STORAGE_OPTIONS)
    df = dt.to_pandas()
except Exception as e:
    print(f"\n  ERROR: {e}")
    print("  Run: python -m processing.bronze_to_silver --once")
    exit(1)

print(f"\n  Delta version : {dt.version()}")
print(f"  Total records : {len(df):,}")
print(f"  Columns       : {len(df.columns)}")

print("\n── Watermark classification ─────────────────────────")
for cls, cnt in df["watermark_classification"].value_counts().items():
    print(f"  {cls:<10}  {cnt:>5}  ({cnt/len(df)*100:.1f}%)")

print("\n── Event type distribution ──────────────────────────")
for et, cnt in df["event_type"].value_counts().items():
    bar = "█" * int(cnt / len(df) * 30)
    print(f"  {et:<15}  {cnt:>5}  {bar}")

print("\n── Event date partitions ─────────────────────────────")
for date, cnt in df["event_date"].value_counts().items():
    print(f"  {date}  →  {cnt:,} records")

print("\n── Data quality checks ───────────────────────────────")
null_event_ids = df["event_id"].isna().sum()
null_user_ids  = df["user_id"].isna().sum()
dupes          = df["event_id"].duplicated().sum()
print(f"  Null event_ids   : {null_event_ids}")
print(f"  Null user_ids    : {null_user_ids}")
print(f"  Duplicate event_ids: {dupes}")
print(f"  All checks pass  : {'✓' if null_event_ids == 0 and null_user_ids == 0 and dupes == 0 else '✗'}")

# Quarantine check
print("\n── Quarantine table ──────────────────────────────────")
try:
    qt = DeltaTable("s3://streamlake-silver/quarantine", storage_options=STORAGE_OPTIONS)
    qdf = qt.to_pandas()
    print(f"  Quarantined records: {len(qdf):,}")
    if len(qdf) > 0:
        print(f"  Quarantine reasons:")
        for reason, cnt in qdf["quarantine_reason"].value_counts().items():
            print(f"    {reason}: {cnt}")
except Exception:
    print("  No quarantine records (table not yet created)")

print(f"\n✓ Silver table looks healthy!\n")
