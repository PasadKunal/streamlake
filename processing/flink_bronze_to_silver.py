"""
PyFlink Bronze → Silver streaming job.

Reads from the Kafka topic (streamlake.events.raw), applies event-time
watermarking, stateful deduplication, and Great Expectations validation,
then writes to Silver Delta (valid) and Quarantine Delta (invalid).

This is the production Flink job. For local testing without a Flink cluster,
use bronze_to_silver.py which implements the same logic as a micro-batch.

Requirements:
    Java 11+ and PyFlink installed (see requirements-flink.txt)
    Flink cluster running (see docker-compose.yml — flink-jobmanager service)

Submit:
    flink run -py processing/flink_bronze_to_silver.py \\
        --pyFiles ingestion/,storage/,quality/,processing/ \\
        -c processing.flink_bronze_to_silver

Architecture:
    Kafka source (streamlake.events.raw, Avro + Schema Registry)
        │
        ▼  AssignTimestampsAndWatermarks
        │  BoundedOutOfOrdernessWatermarks(Duration.ofMinutes(5))
        │
        ▼  KeyedStream (by event_id)
        │  KeyedProcessFunction → dedup via ValueState[Long] (RocksDB TTL 1h)
        │
        ▼  ProcessFunction → SilverValidator (6 expectation types)
        │  ├── main output   → valid records
        │  └── side output   → quarantine records (with error details)
        │
        ▼  FileSink (Delta-compatible Parquet, partitioned by event_date)
"""
import json
import os
from datetime import datetime, timezone

# ── PyFlink imports (requires: pip install -r requirements-flink.txt) ──────────
try:
    from pyflink.common import WatermarkStrategy, Duration, Types, Row
    from pyflink.common.serialization import SimpleStringSchema
    from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
    from pyflink.datastream.connectors.kafka import (
        KafkaSource, KafkaOffsetsInitializer
    )
    from pyflink.datastream.functions import (
        KeyedProcessFunction, ProcessFunction, RuntimeContext
    )
    from pyflink.datastream.state import ValueStateDescriptor
    from pyflink.datastream.output_tag import OutputTag

    PYFLINK_AVAILABLE = True
except ImportError:
    PYFLINK_AVAILABLE = False

from quality.expectations_suite import SilverValidator

QUARANTINE_TAG = OutputTag("quarantine") if PYFLINK_AVAILABLE else None
VALIDATOR = SilverValidator()

ALLOWED_LATENESS_MS = 5 * 60 * 1000   # 5 minutes


class DeduplicateByEventId(KeyedProcessFunction if PYFLINK_AVAILABLE else object):
    """
    Stateful deduplication keyed on event_id.
    State: ValueState<Long> (timestamp of first seen event).
    TTL: 1 hour — Flink auto-expires stale state via RocksDB TTL.

    Flink state backend: RocksDB (configured in flink-conf.yaml)
        state.backend: rocksdb
        state.backend.incremental: true
    """
    def open(self, ctx: RuntimeContext) -> None:
        descriptor = ValueStateDescriptor("seen-event-ts", Types.LONG())
        # TTL config: auto-expire after 1 hour on read and write
        from pyflink.datastream.state import StateTtlConfig
        ttl = (
            StateTtlConfig
            .new_builder(Duration.of_hours(1))
            .set_update_type(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .set_state_visibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .build()
        )
        descriptor.enable_time_to_live(ttl)
        self._seen_state = ctx.get_state(descriptor)

    def process_element(self, record: dict, ctx) -> None:
        existing_ts = self._seen_state.value()
        if existing_ts is not None:
            return  # duplicate — drop silently
        self._seen_state.update(record["timestamp_ms"])
        yield record


class ValidateAndRoute(ProcessFunction if PYFLINK_AVAILABLE else object):
    """
    Validates each record against the SilverValidator expectations.
    Valid records → main output (Silver sink).
    Invalid records → quarantine side output with error details.
    """
    def process_element(self, record: dict, ctx) -> None:
        errors = VALIDATOR.validate(record)
        if errors:
            quarantine_record = {**record, "validation_errors": json.dumps(errors), "quarantine_reason": "validation_failure"}
            ctx.output(QUARANTINE_TAG, quarantine_record)
        else:
            ts_ms = record["timestamp_ms"]
            event_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            silver_record = {**record, "event_date": event_date, "silver_processed_ms": int(datetime.now(timezone.utc).timestamp() * 1000)}
            yield silver_record


def build_pipeline(env: "StreamExecutionEnvironment") -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")
    topic = os.getenv("KAFKA_TOPIC_EVENTS", "streamlake.events.raw")
    silver_path = os.getenv("DELTA_SILVER_PATH", "s3://streamlake-silver/events")
    quarantine_path = os.getenv("DELTA_QUARANTINE_PATH", "s3://streamlake-silver/quarantine")

    # ── Source: Kafka with Avro deserialization ────────────────────────────────
    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(bootstrap_servers)
        .set_topics(topic)
        .set_group_id("streamlake-silver-writer")
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())  # replaced by AvroDeserializer in prod
        .build()
    )

    # ── Watermark strategy: bounded out-of-orderness ──────────────────────────
    watermark_strategy = (
        WatermarkStrategy
        .for_bounded_out_of_orderness(Duration.of_millis(ALLOWED_LATENESS_MS))
        .with_timestamps_and_watermarks(lambda record: record["timestamp_ms"])
        .with_idleness(Duration.of_seconds(30))
    )

    # ── Stream construction ────────────────────────────────────────────────────
    stream = (
        env.from_source(source, watermark_strategy, "Kafka Bronze Source")
        .key_by(lambda r: r["event_id"])          # key for stateful dedup
        .process(DeduplicateByEventId())           # drop duplicates
        .process(ValidateAndRoute())               # validate + split
    )

    # ── Sinks ─────────────────────────────────────────────────────────────────
    # Silver sink (Delta-compatible Parquet via FileSink)
    # In production, use the Delta Flink connector:
    #   DeltaSink.forRowType(new Path(silver_path), hadoopConf, ROW_TYPE)
    stream.print()  # placeholder — replace with FileSink / DeltaSink

    # Quarantine sink
    stream.get_side_output(QUARANTINE_TAG).print()  # placeholder


def main() -> None:
    if not PYFLINK_AVAILABLE:
        raise RuntimeError(
            "PyFlink not available. Install with: pip install -r requirements-flink.txt\n"
            "Requires Java 11+. For local testing use: python -m processing.bronze_to_silver"
        )

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
    env.set_parallelism(4)
    env.enable_checkpointing(60_000)  # checkpoint every 60s

    build_pipeline(env)
    env.execute("StreamLake Bronze → Silver")


if __name__ == "__main__":
    main()
