"""
PyArrow schemas for the Silver and Quarantine Delta Lake tables.

Silver: validated, deduplicated, enriched events partitioned by event_date.
Quarantine: records that failed Great Expectations validation, with error details.
"""
import pyarrow as pa

SILVER_SCHEMA = pa.schema(
    [
        # ── Event fields (validated + enriched) ───────────────────────
        pa.field("event_id", pa.string(), nullable=False),
        pa.field("event_type", pa.string(), nullable=False),
        pa.field("user_id", pa.string(), nullable=False),
        pa.field("session_id", pa.string(), nullable=False),
        pa.field("timestamp_ms", pa.int64(), nullable=False),
        pa.field("page_url", pa.string(), nullable=True),
        pa.field("product_id", pa.string(), nullable=True),
        pa.field("amount_cents", pa.int64(), nullable=True),
        pa.field("device_type", pa.string(), nullable=False),
        pa.field("country_code", pa.string(), nullable=False),
        pa.field("app_version", pa.string(), nullable=False),
        # ── Silver metadata ───────────────────────────────────────────
        pa.field("silver_processed_ms", pa.int64(), nullable=False),
        pa.field("watermark_classification", pa.string(), nullable=False),  # on_time | late
        # Partition key — derived from event timestamp (not ingestion time)
        pa.field("event_date", pa.string(), nullable=False),  # YYYY-MM-DD
    ]
)

QUARANTINE_SCHEMA = pa.schema(
    [
        # All Silver fields
        pa.field("event_id", pa.string(), nullable=True),
        pa.field("event_type", pa.string(), nullable=True),
        pa.field("user_id", pa.string(), nullable=True),
        pa.field("session_id", pa.string(), nullable=True),
        pa.field("timestamp_ms", pa.int64(), nullable=True),
        pa.field("page_url", pa.string(), nullable=True),
        pa.field("product_id", pa.string(), nullable=True),
        pa.field("amount_cents", pa.int64(), nullable=True),
        pa.field("device_type", pa.string(), nullable=True),
        pa.field("country_code", pa.string(), nullable=True),
        pa.field("app_version", pa.string(), nullable=True),
        # Quarantine-specific fields
        pa.field("quarantine_reason", pa.string(), nullable=False),
        pa.field("validation_errors", pa.string(), nullable=False),   # JSON list
        pa.field("silver_processed_ms", pa.int64(), nullable=False),
        pa.field("ingestion_date", pa.string(), nullable=True),
    ]
)

LATE_EVENTS_SCHEMA = SILVER_SCHEMA
