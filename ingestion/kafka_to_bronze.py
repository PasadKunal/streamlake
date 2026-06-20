"""
StreamLake Kafka → Bronze Delta Lake writer.

Consumes Avro-encoded user events from Kafka and writes them in micro-batches
to the Bronze Delta Lake table, partitioned by ingestion_date.

Exactly-once guarantee:
  - Producer uses enable.idempotence=True (no duplicate produce on retry)
  - Consumer commits offsets only after a successful Delta write
  - Silver layer deduplicates by event_id for any residual duplicates

Usage:
    python -m ingestion.kafka_to_bronze
    python -m ingestion.kafka_to_bronze --batch-size 1000 --batch-timeout 5
"""
import argparse
import os
import time
from datetime import datetime, timezone

from confluent_kafka import DeserializingConsumer, KafkaError
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer
from dotenv import load_dotenv
from loguru import logger

from ingestion.schema_registry import get_avro_deserializer, get_client
from storage.bronze_schema import BRONZE_SCHEMA
from storage.delta_writer import write_batch

load_dotenv()


def _build_record(msg, now_ms: int, ingestion_date: str) -> dict:
    """Merge event payload with ingestion metadata into a Bronze record."""
    event: dict = msg.value()
    return {
        **event,
        "kafka_topic": msg.topic(),
        "kafka_partition": msg.partition(),
        "kafka_offset": msg.offset(),
        "ingestion_timestamp_ms": now_ms,
        "ingestion_date": ingestion_date,
    }


def run_consumer(
    bootstrap_servers: str,
    schema_registry_url: str,
    topic: str,
    group_id: str,
    table_path: str,
    batch_size: int = 500,
    batch_timeout_s: float = 10.0,
) -> None:
    registry_client = get_client(schema_registry_url)
    avro_deserializer = get_avro_deserializer(registry_client)

    consumer = DeserializingConsumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "key.deserializer": StringDeserializer("utf_8"),
            "value.deserializer": avro_deserializer,
            "auto.offset.reset": "earliest",
            # Manual commit — only after a successful Delta write
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])

    buffer: list[dict] = []
    last_flush = time.monotonic()
    total_written = 0
    total_batches = 0

    logger.info(
        f"Consumer started | topic='{topic}' group='{group_id}'"
        f" batch_size={batch_size} batch_timeout={batch_timeout_s}s"
        f" → {table_path}"
    )

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"End of partition {msg.partition()} at offset {msg.offset()}")
                else:
                    logger.error(f"Consumer error: {msg.error()}")
            else:
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                ingestion_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                buffer.append(_build_record(msg, now_ms, ingestion_date))

            elapsed = time.monotonic() - last_flush
            should_flush = len(buffer) >= batch_size or (buffer and elapsed >= batch_timeout_s)

            if should_flush:
                written = write_batch(buffer, table_path, BRONZE_SCHEMA, ["ingestion_date"])
                # Commit offsets only after a successful Delta write
                consumer.commit(asynchronous=False)
                total_written += written
                total_batches += 1
                logger.info(
                    f"Batch #{total_batches} flushed | records={written}"
                    f" | total_written={total_written:,}"
                )
                buffer.clear()
                last_flush = time.monotonic()

    except KeyboardInterrupt:
        logger.info("Shutdown signal received — flushing remaining buffer...")
        if buffer:
            write_batch(buffer, table_path, BRONZE_SCHEMA, ["ingestion_date"])
            consumer.commit(asynchronous=False)
            logger.info(f"Flushed {len(buffer)} remaining records")
    finally:
        consumer.close()
        logger.info(f"Consumer closed | total_written={total_written:,} records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StreamLake Kafka-to-Bronze Delta writer")
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    )
    parser.add_argument(
        "--schema-registry",
        default=os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081"),
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("KAFKA_TOPIC_EVENTS", "streamlake.events.raw"),
    )
    parser.add_argument(
        "--group-id",
        default=os.getenv("KAFKA_CONSUMER_GROUP", "streamlake-bronze-writer"),
    )
    parser.add_argument(
        "--table-path",
        default=os.getenv("DELTA_BRONZE_PATH", "s3://streamlake-bronze/events"),
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--batch-timeout", type=float, default=10.0)
    args = parser.parse_args()

    run_consumer(
        args.bootstrap_servers,
        args.schema_registry,
        args.topic,
        args.group_id,
        args.table_path,
        args.batch_size,
        args.batch_timeout,
    )
