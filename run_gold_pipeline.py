"""
Local Gold pipeline runner — equivalent to triggering the gold_refresh Airflow DAG.

Reads Silver Delta from MinIO, runs all four DuckDB aggregations, writes Gold
Delta tables back to MinIO. No Airflow required.

Usage:
    source .venv/bin/activate
    python run_gold_pipeline.py
    python run_gold_pipeline.py --silver-path s3://streamlake-silver/events
"""
import argparse
import os
import time
from datetime import datetime, timezone

import pyarrow as pa
from deltalake import DeltaTable
from loguru import logger

from orchestration.gold_aggregations import run_all
from storage.delta_writer import STORAGE_OPTIONS, write_batch
from storage.gold_schema import (
    GOLD_DAU_SCHEMA,
    GOLD_FUNNEL_SCHEMA,
    GOLD_REVENUE_SCHEMA,
    GOLD_USER_SIGNALS_SCHEMA,
)

SILVER_PATH   = os.getenv("DELTA_SILVER_PATH",   "s3://streamlake-silver/events")
GOLD_DAU_PATH = os.getenv("DELTA_GOLD_DAU_PATH", "s3://streamlake-gold/dau")
GOLD_REV_PATH = os.getenv("DELTA_GOLD_REV_PATH", "s3://streamlake-gold/revenue")
GOLD_FNL_PATH = os.getenv("DELTA_GOLD_FNL_PATH", "s3://streamlake-gold/funnel")
GOLD_USR_PATH = os.getenv("DELTA_GOLD_USR_PATH", "s3://streamlake-gold/user_signals")

GOLD_TABLES = [
    ("dau",          GOLD_DAU_PATH,  GOLD_DAU_SCHEMA,          ["event_date"]),
    ("revenue",      GOLD_REV_PATH,  GOLD_REVENUE_SCHEMA,       ["event_date"]),
    ("funnel",       GOLD_FNL_PATH,  GOLD_FUNNEL_SCHEMA,        ["event_date"]),
    ("user_signals", GOLD_USR_PATH,  GOLD_USER_SIGNALS_SCHEMA,  ["signal_date"]),
]


def run(silver_path: str = SILVER_PATH) -> None:
    t0 = time.time()

    logger.info("Loading Silver Delta table...")
    try:
        dt = DeltaTable(silver_path, storage_options=STORAGE_OPTIONS)
        silver_df = dt.to_pandas()
    except Exception as e:
        logger.error(f"Cannot read Silver: {e}")
        logger.error("Run: python -m processing.bronze_to_silver --once")
        return

    logger.info(f"Silver loaded | version={dt.version()} records={len(silver_df):,}")

    logger.info("Running DuckDB aggregations...")
    results = run_all(silver_df)

    for name, path, schema, partition_cols in GOLD_TABLES:
        df = results[name]
        if df.empty:
            logger.warning(f"Skipping {name} — empty result (no matching Silver data)")
            continue
        records = df.to_dict(orient="records")
        write_batch(records, path, schema, partition_cols)
        logger.info(f"Gold/{name} written | rows={len(records):,} | path={path}")

    elapsed = time.time() - t0
    logger.info(
        f"Gold pipeline complete in {elapsed:.1f}s | "
        f"dau={len(results['dau']):,} "
        f"revenue={len(results['revenue']):,} "
        f"funnel={len(results['funnel']):,} "
        f"user_signals={len(results['user_signals']):,}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gold pipeline local runner")
    parser.add_argument("--silver-path", default=SILVER_PATH)
    args = parser.parse_args()
    run(args.silver_path)
