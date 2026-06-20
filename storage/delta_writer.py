"""
Delta Lake writer utilities for StreamLake.
Wraps delta-rs write_deltalake with retry logic and MinIO/S3 storage options.
"""
import os

import pyarrow as pa
from deltalake import write_deltalake
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# Storage options for MinIO (local) or AWS S3 (cloud).
# All values read from environment so the same code works in both environments.
STORAGE_OPTIONS: dict[str, str] = {
    "AWS_ENDPOINT_URL": os.getenv("AWS_ENDPOINT_URL", "http://localhost:9000"),
    "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
    "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
    "AWS_REGION": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    "AWS_ALLOW_HTTP": "true",
    # Required for MinIO — skips the DynamoDB lock table used by real S3
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}


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
