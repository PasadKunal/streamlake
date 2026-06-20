"""
Airflow DAG: gold_refresh
Runs nightly at 02:00 UTC — reads Silver Delta Lake, computes four Gold
aggregations via DuckDB, and writes results back to Gold Delta tables on MinIO.

Requires Airflow 2.9+ with the TaskFlow API.
Install: pip install -r requirements-airflow.txt  (separate venv recommended)

Task graph:
    load_silver
        ├── compute_dau         ──► write_dau
        ├── compute_revenue     ──► write_revenue
        ├── compute_funnel      ──► write_funnel
        └── compute_user_signals──► write_user_signals
"""
from __future__ import annotations

import os
from datetime import timedelta

import pendulum
from airflow.decorators import dag, task

STORAGE_OPTIONS = {
    "AWS_ENDPOINT_URL":        os.getenv("AWS_ENDPOINT_URL",        "http://localhost:9002"),
    "AWS_ACCESS_KEY_ID":       os.getenv("AWS_ACCESS_KEY_ID",       "minioadmin"),
    "AWS_SECRET_ACCESS_KEY":   os.getenv("AWS_SECRET_ACCESS_KEY",   "minioadmin"),
    "AWS_REGION":              "us-east-1",
    "AWS_ALLOW_HTTP":          "true",
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}

SILVER_PATH    = os.getenv("DELTA_SILVER_PATH",     "s3://streamlake-silver/events")
GOLD_DAU_PATH  = os.getenv("DELTA_GOLD_DAU_PATH",   "s3://streamlake-gold/dau")
GOLD_REV_PATH  = os.getenv("DELTA_GOLD_REV_PATH",   "s3://streamlake-gold/revenue")
GOLD_FNL_PATH  = os.getenv("DELTA_GOLD_FNL_PATH",   "s3://streamlake-gold/funnel")
GOLD_USR_PATH  = os.getenv("DELTA_GOLD_USR_PATH",   "s3://streamlake-gold/user_signals")


@dag(
    dag_id="gold_refresh",
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    tags=["gold", "streamlake"],
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(hours=1),
    },
    doc_md=__doc__,
)
def gold_refresh():

    @task()
    def load_silver() -> dict:
        """Read Silver Delta and return summary metadata (DataFrames are re-read per task)."""
        from deltalake import DeltaTable
        dt = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS)
        df = dt.to_pandas()
        return {
            "delta_version": dt.version(),
            "record_count":  len(df),
            "dates":         sorted(df["event_date"].unique().tolist()),
        }

    @task()
    def compute_and_write_dau(silver_meta: dict) -> int:
        from deltalake import DeltaTable
        from orchestration.gold_aggregations import compute_dau
        from storage.delta_writer import write_batch
        from storage.gold_schema import GOLD_DAU_SCHEMA

        df = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS).to_pandas()
        gold_df = compute_dau(df)
        write_batch(gold_df.to_dict(orient="records"), GOLD_DAU_PATH, GOLD_DAU_SCHEMA, ["event_date"])
        return len(gold_df)

    @task()
    def compute_and_write_revenue(silver_meta: dict) -> int:
        from deltalake import DeltaTable
        from orchestration.gold_aggregations import compute_revenue
        from storage.delta_writer import write_batch
        from storage.gold_schema import GOLD_REVENUE_SCHEMA

        df = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS).to_pandas()
        gold_df = compute_revenue(df)
        write_batch(gold_df.to_dict(orient="records"), GOLD_REV_PATH, GOLD_REVENUE_SCHEMA, ["event_date"])
        return len(gold_df)

    @task()
    def compute_and_write_funnel(silver_meta: dict) -> int:
        from deltalake import DeltaTable
        from orchestration.gold_aggregations import compute_funnel
        from storage.delta_writer import write_batch
        from storage.gold_schema import GOLD_FUNNEL_SCHEMA

        df = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS).to_pandas()
        gold_df = compute_funnel(df)
        write_batch(gold_df.to_dict(orient="records"), GOLD_FNL_PATH, GOLD_FUNNEL_SCHEMA, ["event_date"])
        return len(gold_df)

    @task()
    def compute_and_write_user_signals(silver_meta: dict) -> int:
        from deltalake import DeltaTable
        from orchestration.gold_aggregations import compute_user_signals
        from storage.delta_writer import write_batch
        from storage.gold_schema import GOLD_USER_SIGNALS_SCHEMA

        df = DeltaTable(SILVER_PATH, storage_options=STORAGE_OPTIONS).to_pandas()
        gold_df = compute_user_signals(df)
        write_batch(gold_df.to_dict(orient="records"), GOLD_USR_PATH, GOLD_USER_SIGNALS_SCHEMA, ["signal_date"])
        return len(gold_df)

    # Wire up the task graph
    meta = load_silver()
    compute_and_write_dau(meta)
    compute_and_write_revenue(meta)
    compute_and_write_funnel(meta)
    compute_and_write_user_signals(meta)


gold_refresh()
