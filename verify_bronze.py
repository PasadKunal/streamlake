"""
Quick verification script for the Bronze Delta table.
Run this anytime to inspect what's in the Bronze layer.

Usage:
    source .venv/bin/activate
    python verify_bronze.py
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

BRONZE_PATH = os.getenv("DELTA_BRONZE_PATH", "s3://streamlake-bronze/events")

print("=" * 55)
print("  StreamLake — Bronze Delta Table Verification")
print("=" * 55)

try:
    dt = DeltaTable(BRONZE_PATH, storage_options=STORAGE_OPTIONS)
except Exception as e:
    print(f"\n  ERROR: Could not open Bronze table: {e}")
    print("  Make sure Docker is running and data has been written.")
    exit(1)

df = dt.to_pandas()

print(f"\n  Table path   : {BRONZE_PATH}")
print(f"  Delta version: {dt.version()}")
print(f"  Total records: {len(df):,}")
print(f"  Columns      : {len(df.columns)}")

print("\n── Event type distribution ──────────────────────────")
for etype, cnt in df["event_type"].value_counts().items():
    bar = "█" * int(cnt / len(df) * 30)
    print(f"  {etype:<15}  {cnt:>5}  {bar}")

print("\n── Device type distribution ─────────────────────────")
for dtype, cnt in df["device_type"].value_counts().items():
    print(f"  {dtype:<10}  {cnt:>5}  ({cnt/len(df)*100:.1f}%)")

print("\n── Country distribution (top 5) ─────────────────────")
for country, cnt in df["country_code"].value_counts().head(5).items():
    print(f"  {country}  {cnt:>5}")

print("\n── Partitions (ingestion_date) ──────────────────────")
for date, cnt in df["ingestion_date"].value_counts().items():
    print(f"  {date}  →  {cnt:,} records")

print("\n── Late events (timestamp > 30s behind wall clock) ──")
import time
now_ms = int(time.time() * 1000)
late = df[df["timestamp_ms"] < now_ms - 30_000]
print(f"  {len(late):,} late events ({len(late)/len(df)*100:.1f}%)")

print("\n── Kafka offset range ───────────────────────────────")
for p, group in df.groupby("kafka_partition"):
    print(f"  Partition {p}: offset {group['kafka_offset'].min()} → {group['kafka_offset'].max()} ({len(group):,} records)")

print("\n── Sample record ────────────────────────────────────")
row = df.iloc[0]
print(f"  event_id    : {row['event_id']}")
print(f"  event_type  : {row['event_type']}")
print(f"  user_id     : {row['user_id']}")
print(f"  session_id  : {row['session_id']}")
print(f"  device_type : {row['device_type']}")
print(f"  country_code: {row['country_code']}")
print(f"  amount_cents: {row['amount_cents']}")

print("\n✓ Bronze table looks healthy!\n")
