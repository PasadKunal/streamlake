"""
StreamLake event simulator — produces realistic user events to Kafka.

Simulates: clicks, page views, purchases, add-to-cart, session start/end.
Event type distribution mirrors a real e-commerce platform.
2% of events are intentionally late (up to 10 min) to test watermark handling.

Usage:
    python -m ingestion.kafka_producer --rate 1400
    python -m ingestion.kafka_producer --rate 500 --topic streamlake.events.raw
"""
import argparse
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import SerializingProducer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import StringSerializer
from dotenv import load_dotenv
from loguru import logger

from ingestion.schema_registry import USER_EVENT_SCHEMA_PATH

load_dotenv()

# ── Synthetic data pools ───────────────────────────────────────────────────────
EVENT_TYPES = ["PAGE_VIEW", "CLICK", "ADD_TO_CART", "PURCHASE", "SESSION_START", "SESSION_END"]
EVENT_WEIGHTS = [35, 35, 15, 8, 4, 3]

DEVICE_TYPES = ["DESKTOP", "MOBILE", "TABLET", "UNKNOWN"]
DEVICE_WEIGHTS = [45, 40, 12, 3]

COUNTRY_CODES = ["US", "GB", "IN", "DE", "CA", "FR", "AU", "BR", "JP", "SG"]
PAGES = [
    "/home",
    "/products",
    "/checkout",
    "/cart",
    "/profile",
    "/search",
    "/category/electronics",
    "/category/clothing",
    "/deals",
]
PRODUCTS = [f"PROD-{i:04d}" for i in range(1, 201)]
USERS = [f"USER-{i:06d}" for i in range(1, 10001)]
APP_VERSIONS = ["2.3.1", "2.3.0", "2.2.8", "2.2.7"]
APP_VERSION_WEIGHTS = [60, 25, 10, 5]


def _generate_event(active_sessions: dict[str, str]) -> dict:
    user_id = random.choice(USERS)

    if user_id not in active_sessions:
        active_sessions[user_id] = str(uuid.uuid4())
        event_type = "SESSION_START"
    else:
        # Exclude SESSION_START from ongoing sessions
        event_type = random.choices(EVENT_TYPES[1:-1], weights=EVENT_WEIGHTS[1:-1])[0]

    session_id = active_sessions[user_id]

    # ~0.5% chance to end the session on any event
    if event_type != "SESSION_START" and random.random() < 0.005:
        del active_sessions[user_id]
        event_type = "SESSION_END"

    # Event timestamp — 2% chance of a late event (up to 10 min behind)
    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if random.random() < 0.02:
        ts_ms -= random.randint(60_000, 600_000)

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp_ms": ts_ms,
        "page_url": random.choice(PAGES) if event_type not in ("PURCHASE",) else None,
        "product_id": (
            random.choice(PRODUCTS) if event_type in ("PURCHASE", "ADD_TO_CART", "CLICK") else None
        ),
        "amount_cents": random.randint(499, 49_999) if event_type == "PURCHASE" else None,
        "device_type": random.choices(DEVICE_TYPES, weights=DEVICE_WEIGHTS)[0],
        "country_code": random.choices(COUNTRY_CODES)[0],
        "app_version": random.choices(APP_VERSIONS, weights=APP_VERSION_WEIGHTS)[0],
    }


def _delivery_report(err, msg) -> None:
    if err:
        logger.error(f"Delivery failed | key={msg.key()} error={err}")


def run_producer(
    bootstrap_servers: str,
    schema_registry_url: str,
    topic: str,
    target_rate: int,
    max_events: int = 0,
) -> None:
    schema_str = USER_EVENT_SCHEMA_PATH.read_text()
    registry_client = SchemaRegistryClient({"url": schema_registry_url})
    avro_serializer = AvroSerializer(registry_client, schema_str, lambda obj, ctx: obj)

    producer = SerializingProducer(
        {
            "bootstrap.servers": bootstrap_servers,
            "key.serializer": StringSerializer("utf_8"),
            "value.serializer": avro_serializer,
            # Idempotent producer — prevents duplicates from retries
            "enable.idempotence": True,
            "acks": "all",
            "retries": 5,
            "max.in.flight.requests.per.connection": 5,
            "linger.ms": 5,
            "batch.size": 65536,
        }
    )

    active_sessions: dict[str, str] = {}
    interval = 1.0 / target_rate
    produced = 0
    start = time.monotonic()
    log_every = target_rate * 5  # log throughput every 5 seconds

    logger.info(
        f"Producer started — target={target_rate} events/sec | topic='{topic}'"
        + (f" | max_events={max_events:,}" if max_events else "")
    )

    try:
        while True:
            event = _generate_event(active_sessions)
            producer.produce(
                topic=topic,
                key=event["user_id"],
                value=event,
                on_delivery=_delivery_report,
            )
            produced += 1
            producer.poll(0)

            if produced % log_every == 0:
                elapsed = time.monotonic() - start
                logger.info(
                    f"Produced {produced:,} events | actual={produced / elapsed:.0f} events/sec"
                    f" | active_sessions={len(active_sessions):,}"
                )

            if max_events and produced >= max_events:
                logger.info(f"Reached max_events={max_events:,} — stopping.")
                break

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Shutting down — flushing remaining messages...")
        producer.flush(timeout=30)
        elapsed = time.monotonic() - start
        logger.info(
            f"Done | total={produced:,} events | avg={produced / elapsed:.0f} events/sec"
            f" | duration={elapsed:.1f}s"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StreamLake event producer simulator")
    parser.add_argument(
        "--rate", type=int, default=1400, help="Target events/sec (default: 1400)"
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("KAFKA_TOPIC_EVENTS", "streamlake.events.raw"),
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    )
    parser.add_argument(
        "--schema-registry",
        default=os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081"),
    )
    parser.add_argument(
        "--max-events", type=int, default=0,
        help="Stop after this many events (0 = run forever)",
    )
    args = parser.parse_args()

    run_producer(args.bootstrap_servers, args.schema_registry, args.topic, args.rate, args.max_events)
