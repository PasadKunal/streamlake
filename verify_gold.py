"""
Verification script for all four Gold Delta tables.
Run after run_gold_pipeline.py to confirm results.

Usage:
    source .venv/bin/activate
    python verify_gold.py
"""
import os
from deltalake import DeltaTable

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL":          os.getenv("AWS_ENDPOINT_URL",        "http://localhost:9002"),
    "AWS_ACCESS_KEY_ID":         os.getenv("AWS_ACCESS_KEY_ID",       "minioadmin"),
    "AWS_SECRET_ACCESS_KEY":     os.getenv("AWS_SECRET_ACCESS_KEY",   "minioadmin"),
    "AWS_REGION":                "us-east-1",
    "AWS_ALLOW_HTTP":            "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME":"true",
}

TABLES = {
    "DAU":          "s3://streamlake-gold/dau",
    "Revenue":      "s3://streamlake-gold/revenue",
    "Funnel":       "s3://streamlake-gold/funnel",
    "UserSignals":  "s3://streamlake-gold/user_signals",
}

print("=" * 55)
print("  StreamLake — Gold Delta Tables Verification")
print("=" * 55)

for name, path in TABLES.items():
    print(f"\n── {name} ({'─' * (47 - len(name))})")
    try:
        dt = DeltaTable(path, storage_options=STORAGE_OPTIONS)
        df = dt.to_pandas()
        print(f"  Delta version : {dt.version()}")
        print(f"  Rows          : {len(df):,}")
        print(f"  Columns       : {list(df.columns)}")
        if not df.empty:
            print(df.to_string(index=False, max_rows=10))
    except Exception as e:
        print(f"  NOT FOUND: {e}")
        print(f"  Run: python run_gold_pipeline.py")

print("\n✓ Verification complete\n")
