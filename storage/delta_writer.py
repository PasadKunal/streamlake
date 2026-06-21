"""
Delta Lake writer utilities for StreamLake.
Wraps delta-rs write_deltalake with retry logic and MinIO/S3 storage options.
"""
import os

import pyarrow as pa
from deltalake import write_deltalake
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()  # ensure .env is loaded before reading storage config

# Storage options work for both MinIO (local dev) and AWS S3 (cloud).
# When AWS_ENDPOINT_URL is set we're talking to a local MinIO instance.
# When it's absent the standard AWS credential chain is used.
_endpoint = os.getenv("AWS_ENDPOINT_URL")
_region   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
STORAGE_OPTIONS: dict[str, str] = {
    "AWS_ACCESS_KEY_ID":          os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
    "AWS_SECRET_ACCESS_KEY":      os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    "AWS_REGION":                 _region,
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}
if _endpoint:
    # Local MinIO
    STORAGE_OPTIONS["AWS_ENDPOINT_URL"] = _endpoint
    STORAGE_OPTIONS["AWS_ALLOW_HTTP"] = "true"
elif _region != "us-east-1":
    # delta-rs doesn't follow S3 redirects; use the regional endpoint directly
    STORAGE_OPTIONS["AWS_ENDPOINT_URL"] = f"https://s3.{_region}.amazonaws.com"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def write_batch(
    records: list[dict],
    table_path: str,
    schema: pa.Schema,
    partition_by: list[str] | None = None,
) -> int:
    """
    Write a list of records to a Delta table and return the count written.
    Retries up to 3 times on transient storage errors.
    """
    if not records:
        return 0

    arrow_table = pa.Table.from_pylist(records, schema=schema)

    write_deltalake(
        table_path,
        arrow_table,
        mode="append",
        partition_by=partition_by or [],
        storage_options=STORAGE_OPTIONS,
    )

    logger.debug(f"Written {len(records)} records → {table_path}")
    return len(records)
