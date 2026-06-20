"""
PyArrow schema for the Bronze Delta Lake table.

Bronze stores raw, immutable events exactly as received from Kafka, plus
ingestion metadata (topic, partition, offset, ingestion timestamp).
Partitioned by ingestion_date for efficient time-range pruning.
"""
import pyarrow as pa

BRONZE_SCHEMA = pa.schema(
    [
        # ── Event fields (from Avro) ───────────────────────────────────
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
        # ── Ingestion metadata (added by kafka_to_bronze.py) ──────────
        pa.field("kafka_topic", pa.string(), nullable=False),
        pa.field("kafka_partition", pa.int32(), nullable=False),
        pa.field("kafka_offset", pa.int64(), nullable=False),
        pa.field("ingestion_timestamp_ms", pa.int64(), nullable=False),
        # Partition key — always YYYY-MM-DD in UTC
        pa.field("ingestion_date", pa.string(), nullable=False),
    ]
)
